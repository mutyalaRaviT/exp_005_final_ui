"""pipeline.codegen — Phase-D: node/4 terms -> generated PySpark scripts.

Sub-modules:
    common.py       shared machinery every language's generator needs:
                     the pig/hive schema-type -> PySpark type map, the
                     StructType code-builder, the program header/footer,
                     the layout-law path helpers, and the subprocess
                     runner used by run_pyspark.py.
    pig_pyspark.py   the term -> PySpark mapping for Pig terms ONLY.
    hive_pyspark.py  (owned elsewhere) the term -> PySpark mapping for
                     Hive terms ONLY.

Codegen law (Phase-D contract): PySpark is generated ONLY from the
node/4 terms, never by re-reading the source file; every emitted block
starts with "# blockid: b_00N"; the term->PySpark mapping carries no
cross-language branching — a pig term is never matched inside
hive_pyspark.py or vice versa, and this file does not import either
language module so neither becomes a hidden dependency of the other.
"""
