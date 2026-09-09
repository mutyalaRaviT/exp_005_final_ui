# ---------------------------------------------------------------------------
# lineageQ runtime for converted SAS programs (pasted once at the top of every
# generated file). The generated code below it reads like SAS: read_datalines
# for INPUT + DATALINES, merge_by for MERGE ... BY, show for PROC PRINT.
# ---------------------------------------------------------------------------
import csv
import datetime
import os
import textwrap

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

OUT_DIR = os.environ.get("LINEAGEQ_OUT", "out/pyspark_ravi")
LIBREFS = {}          # libref -> the path the SAS program named (documentation only)
DISPLAY_FORMATS = {}  # variable -> SAS format, applied when a dataset is shown


def make_spark():
    spark = (SparkSession.builder.appName("sas_to_pyspark").master("local[1]")
             .config("spark.sql.shuffle.partitions", "1").config("spark.ui.enabled", "false")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def libref(name, path):
    """LIBNAME: datasets live in memory here; the path is kept for the record."""
    LIBREFS[name] = path


def display_format(variable, sas_format):
    """FORMAT var fmt.: how the variable prints, wherever it flows."""
    DISPLAY_FORMATS[variable] = sas_format


# --- INPUT list ------------------------------------------------------------
def char(name):
    return (name, "char", None)


def num(name):
    return (name, "num", None)


def date(name, informat):
    return (name, "date", informat)


def _read_date(token, informat):
    f = informat.lower()
    if f.startswith("mmddyy"):
        return datetime.datetime.strptime(token, "%m/%d/%Y").date()
    if f.startswith("ddmmyy"):
        return datetime.datetime.strptime(token, "%d/%m/%Y").date()
    if f.startswith("yymmdd"):
        return datetime.datetime.strptime(token, "%Y-%m-%d").date()
    if f.startswith("date"):
        return datetime.datetime.strptime(token, "%d%b%Y").date()
    raise ValueError("informat not supported: " + informat)


def read_datalines(spark, schema, rows):
    """SAS list INPUT over DATALINES: values split on blanks, a blank line is
    skipped, a lone '.' is a missing number."""
    fields = []
    for name, kind, _ in schema:
        typ = {"char": T.StringType(), "num": T.DoubleType(), "date": T.DateType()}[kind]
        fields.append(T.StructField(name, typ, True))
    data = []
    for line in textwrap.dedent(rows).splitlines():
        tokens = line.split()
        if not tokens:
            continue
        record = []
        for (name, kind, informat), token in zip(schema, tokens):
            if kind == "char":
                record.append(token)
            elif kind == "date":
                record.append(_read_date(token, informat))
            else:
                record.append(None if token == "." else float(token))
        record += [None] * (len(schema) - len(record))
        data.append(tuple(record))
    return spark.createDataFrame(data, T.StructType(fields))


# --- MERGE ... BY ------------------------------------------------------------
def merge_by(sources, by):
    """DATA step MERGE with BY: a full outer join on the BY variables, columns
    in first-seen order. When a BY variable is missing on a source, SAS logs an
    ERROR, stops the step and leaves an empty dataset with all the variables;
    this does the same instead of raising, so the program runs to its end."""
    spark = sources[0][1].sparkSession
    columns = []
    for _, df in sources:
        columns += [c for c in df.columns if c not in columns]
    missing = [(name, key) for name, df in sources for key in by if key not in df.columns]
    if missing:
        for name, key in missing:
            print("ERROR: BY variable %s is not on input data set %s." % (key.upper(), name.upper()))
        print("NOTE: The SAS System stopped processing this step because of errors. "
              "The data set is created with 0 observations.")
        fields = [T.StructField(c, next(df.schema[c].dataType for _, df in sources if c in df.columns), True)
                  for c in columns]
        return spark.createDataFrame([], T.StructType(fields))
    result = None
    for _, df in sources:
        result = df if result is None else result.join(df, on=by, how="full")
    return result.select(*columns).orderBy(*by)


def attach_first_row(main, lookup):
    """IF _N_ = 1 THEN SET lookup; SET main; — the lookup's first row is read
    once and retained, so its variables ride along on every row of main."""
    return main.crossJoin(lookup.limit(1))


# --- PROC SQL scalar subquery ------------------------------------------------
def scalar(df, column=None):
    """The single value of a one-row result: (select avg_sales from ...)."""
    rows = (df.select(column) if column else df).collect()
    return rows[0][0] if rows else None


# --- PROC PRINT ------------------------------------------------------------------
def _fmt(column, value):
    if value is None:
        return "."
    f = DISPLAY_FORMATS.get(column, "").lower()
    if isinstance(value, (datetime.date, datetime.datetime)):
        if f.startswith("mmddyy"):
            return value.strftime("%m/%d/%Y")
        if f.startswith("ddmmyy"):
            return value.strftime("%d/%m/%Y")
        if f.startswith("date"):
            return value.strftime("%d%b%Y").upper()
        return str((value - datetime.date(1960, 1, 1)).days)
    if isinstance(value, float):
        return str(int(value)) if value == int(value) and abs(value) < 1e15 else "%.12g" % value
    return str(value)


def show(name, df):
    """PROC PRINT-style listing plus a CSV copy under OUT_DIR."""
    rows, cols = df.collect(), df.columns
    print("\n==== %s  (%d obs) ====" % (name, len(rows)))
    table = [["Obs"] + cols] + [[str(i)] + [_fmt(c, r[c]) for c in cols] for i, r in enumerate(rows, 1)]
    widths = [max(len(row[j]) for row in table) for j in range(len(cols) + 1)]
    for row in table:
        print("  ".join(cell.rjust(widths[j]) for j, cell in enumerate(row)))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, name + ".csv"), "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(cols)
        for r in rows:
            writer.writerow([_fmt(c, r[c]) for c in cols])
# ---------------------------------------------------------------------------
