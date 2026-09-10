# ======================================================================
# lineageQ SAS -> PySpark runtime shim. Pasted verbatim at the top of every
# generated program by BOTH code generators (codegen/sas_pyspark.pl in
# Prolog, rust_engine/src/emit.rs in Rust) so the two outputs can be diffed
# byte for byte. It knows nothing about any particular SAS program.
# ======================================================================
import csv
import datetime
import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

OUT_DIR = os.environ.get("LINEAGEQ_OUT", "out/pyspark_ravi")

ds = {}        # "lib.name" -> DataFrame
ORDER = []     # datasets in creation order (SAS log order)
FORMATS = {}   # variable name -> SAS format name (formats travel with the variable)
LIBS = {}      # libref -> the path SAS was given (documentation only)


def make_spark():
    spark = (SparkSession.builder.appName("lineageq_sas2pyspark").master("local[1]")
             .config("spark.sql.shuffle.partitions", "1").config("spark.ui.enabled", "false")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def put(name, df):
    """Register a dataset the way a SAS step creates it: replace if it exists."""
    ds[name] = df
    if name not in ORDER:
        ORDER.append(name)
    return df


def _informat_date(tok, informat):
    f = informat.lower()
    if f.startswith("mmddyy"):
        return datetime.datetime.strptime(tok, "%m/%d/%Y").date()
    if f.startswith("ddmmyy"):
        return datetime.datetime.strptime(tok, "%d/%m/%Y").date()
    if f.startswith("yymmdd"):
        return datetime.datetime.strptime(tok, "%Y-%m-%d").date()
    if f.startswith("date"):
        return datetime.datetime.strptime(tok, "%d%b%Y").date()
    raise ValueError("informat not supported: " + informat)


def sas_datalines(spark, columns, rows):
    """SAS list INPUT over DATALINES. columns: [(name, kind, informat)], kind
    'char' | 'num'; a blank line holds no values, so SAS moves to the next
    line (it is skipped); a lone '.' is a missing number (None)."""
    fields, data = [], []
    for name, kind, informat in columns:
        if kind == "char":
            fields.append(T.StructField(name, T.StringType(), True))
        elif informat:
            fields.append(T.StructField(name, T.DateType(), True))
        else:
            fields.append(T.StructField(name, T.DoubleType(), True))
    for line in rows.splitlines():
        toks = line.split()
        if not toks:
            continue
        rec = []
        for (name, kind, informat), tok in zip(columns, toks):
            if kind == "char":
                rec.append(tok)
            elif informat:
                rec.append(_informat_date(tok, informat))
            else:
                rec.append(None if tok == "." else float(tok))
        while len(rec) < len(columns):
            rec.append(None)
        data.append(tuple(rec))
    return spark.createDataFrame(data, T.StructType(fields))


def sas_load_csv(spark, csv_path, schema_path):
    """exp_42 loop 3 (2026-09-07): read one dataset the interpreters' CSV convention wrote —
    header row, integers bare, dates as mm/dd/yyyy when the column has a mmddyy format
    (else a day count from 1960-01-01), missing as `.`. The schema JSON names the
    types and formats; formats are registered so sas_print prints the same way."""
    import json as _json
    schema = _json.load(open(schema_path))["columns"]
    fields, data = [], []
    for c in schema:
        t = {"char": T.StringType(), "num": T.DoubleType(), "date": T.DateType()}[c["type"]]
        fields.append(T.StructField(c["name"], t, True))
        if c.get("format"):
            FORMATS[c["name"]] = c["format"]
    with open(csv_path, newline="") as fh:
        rows = list(csv.reader(fh))
    for raw in rows[1:]:
        rec = []
        for c, tok in zip(schema, raw):
            if tok == ".":
                rec.append(None)
            elif c["type"] == "char":
                rec.append(tok)
            elif c["type"] == "date":
                rec.append(_informat_date(tok, "mmddyy10") if "/" in tok else datetime.date(1960, 1, 1) + datetime.timedelta(days=int(tok)))
            else:
                rec.append(float(tok))
        data.append(tuple(rec))
    return spark.createDataFrame(data, T.StructType(fields))


def sas_merge(spark, sources, by):
    """DATA step MERGE ... BY: a full outer join on the BY variables, output
    columns in first-seen order, IN= flags dropped (they are temporary in
    SAS). If a BY variable is missing on any source, SAS logs
    'ERROR: BY variable X is not on input data set ...', stops the step, and
    leaves an EMPTY dataset with the union of the variables — reproduced
    here rather than raising, so the program runs to the end like SAS does."""
    cols = []
    for name, df in sources:
        for c in df.columns:
            if c not in cols:
                cols.append(c)
    missing = [(name, k) for name, df in sources for k in by if k not in df.columns]
    if missing:
        for name, k in missing:
            print("ERROR: BY variable %s is not on input data set %s." % (k.upper(), name.upper()))
        print("NOTE: The SAS System stopped processing this step because of errors. "
              "The data set is created with 0 observations.")
        fields = []
        for c in cols:
            for name, df in sources:
                if c in df.columns:
                    fields.append(T.StructField(c, df.schema[c].dataType, True))
                    break
        return spark.createDataFrame([], T.StructType(fields))
    out = None
    for name, df in sources:
        out = df if out is None else out.join(df, on=by, how="full")
    return out.select(*cols).orderBy(*by)


def sas_attach_first_row(main, lookup):
    """IF _N_ = 1 THEN SET lookup; SET main;  — the lookup's first row is read
    once and retained, so its variables ride along on every row of main."""
    return main.crossJoin(lookup.limit(1))


def fmt_value(col, v):
    if v is None:
        return "."
    f = FORMATS.get(col, "")
    if isinstance(v, (datetime.date, datetime.datetime)):
        if f.lower().startswith("mmddyy"):
            return v.strftime("%m/%d/%Y")
        if f.lower().startswith("ddmmyy"):
            return v.strftime("%d/%m/%Y")
        if f.lower().startswith("date"):
            return v.strftime("%d%b%Y").upper()
        return str((v - datetime.date(1960, 1, 1)).days)  # unformatted SAS date = day count
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return ("%.12g" % v)
    return str(v)


def sas_print(name):
    """PROC PRINT-like listing of one dataset, plus a CSV copy under OUT_DIR."""
    df = ds[name]
    rows = df.collect()
    cols = df.columns
    print("")
    print("==== %s  (%d obs) ====" % (name, len(rows)))
    table = [["Obs"] + cols]
    for i, r in enumerate(rows, 1):
        table.append([str(i)] + [fmt_value(c, r[c]) for c in cols])
    widths = [max(len(row[j]) for row in table) for j in range(len(cols) + 1)]
    for row in table:
        print("  ".join(cell.rjust(widths[j]) for j, cell in enumerate(row)))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, name + ".csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([fmt_value(c, r[c]) for c in cols])


def scalar(df):
    """A scalar subquery: the single value of a one-row, one-column result."""
    rows = df.collect()
    return None if not rows else rows[0][0]
# ======================================================================

spark = make_spark()

# ---- work.cust_summary  (PROC SQL, SAS lines 10-24) ------------------------
#   proc sql;
#   create table work.cust_summary as select c.cust_id, c.cust_name, c.segment, c.country, c.risk_score, count(a.acct_id) as acct_cnt, sum(a.open_bal) as total_open_bal
#   from work.customers c left join work.accounts a on c.cust_id = a.cust_id
#   group by c.cust_id, c.cust_name, c.segment, c.country, c.risk_score;
#   quit;
cust_summary = (
    customers.alias("c")
    .groupBy(F.col("c.cust_id"), F.col("c.cust_name"), F.col("c.segment"), F.col("c.country"), F.col("c.risk_score"))
    .agg(
        F.count(F.col("a.acct_id")).alias("acct_cnt"),
        F.sum(F.col("a.open_bal")).alias("total_open_bal"),
    )
)

# ---- every dataset the program created, in SAS log order -------------------
show("work.cust_summary", cust_summary)
spark.stop()
