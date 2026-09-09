"use strict";
/** server/datamatch.ts — DataMatch in TypeScript (exp_42, 2026-09-07).
 *
 * Why: the studio page compares tables in the browser: interpreter vs Spark, engine vs
 * engine, and a pasted SAS PROC PRINT listing vs PySpark. This is a port of
 * pipeline/datamatch.py (normalize_value, compare_rows: the DataMatch law — rows as a
 * multiset, whitespace stripped, numbers rounded to 6 decimals, ints and whole floats
 * unified, NaN/Inf canonical) plus compare_sas_vs_pyspark.py's listing parser.
 * Compiled to datamatch.js by `npx -p typescript tsc -p server/tsconfig.json`
 * (module "None": a plain script; it publishes globalThis.DataMatch).
 */
const FLOAT_DP = 6;
/** normalize_value/1: one field -> its canonical comparable string */
function normalizeValue(v) {
    const s = String(v).trim();
    if (s === "" || s === ".")
        return "";
    if (!/^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(s)) {
        const l = s.toLowerCase();
        if (l === "nan")
            return "nan";
        if (l === "inf" || l === "infinity" || l === "+inf")
            return "inf";
        if (l === "-inf" || l === "-infinity")
            return "-inf";
        return s;
    }
    const f = Number(s);
    if (Number.isNaN(f))
        return "nan";
    if (!Number.isFinite(f))
        return f > 0 ? "inf" : "-inf";
    let r = Math.round(f * 10 ** FLOAT_DP) / 10 ** FLOAT_DP;
    if (r === 0)
        r = 0;
    if (r === Math.trunc(r))
        return String(Math.trunc(r));
    return r.toFixed(FLOAT_DP).replace(/0+$/, "").replace(/\.$/, "");
}
const SEP = "\u001f"; // cells joined with a unit separator so they split back exactly
function normalizeRow(row) {
    return row.map(normalizeValue).join(SEP);
}
function counts(rows) {
    const m = new Map();
    for (const r of rows) {
        const k = normalizeRow(r);
        m.set(k, (m.get(k) ?? 0) + 1);
    }
    return m;
}
/** compare_rows/3: multiset comparison; samples name rows and how often each side has them */
function compareRows(ref, conv, maxSamples = 5) {
    const rc = counts(ref), cc = counts(conv);
    let n = 0;
    const samples = [];
    const keys = new Set([...rc.keys(), ...cc.keys()]);
    for (const k of keys) {
        const a = rc.get(k) ?? 0, b = cc.get(k) ?? 0;
        if (a !== b) {
            n += Math.abs(a - b);
            if (samples.length < maxSamples)
                samples.push({ row: k.split(SEP), ref_count: a, conv_count: b });
        }
    }
    return { verdict: n === 0 ? "PASS" : "FAIL", n_mismatch: n, samples };
}
/** the verdict for one output: columns must agree (case-insensitive), then the rows */
function matchTables(ref, conv) {
    const empty = { n_mismatch: 0, samples: [], cols_equal: false, ref_rows: 0, conv_rows: 0 };
    if (!ref)
        return { ...empty, verdict: "REF_MISSING", note: "no reference table" };
    if (!conv)
        return { ...empty, verdict: "CONV_MISSING", ref_rows: ref.rows.length, note: "no converted table" };
    const lc = (c) => c.map(x => x.trim().toLowerCase());
    const colsEqual = JSON.stringify(lc(ref.cols)) === JSON.stringify(lc(conv.cols));
    if (!colsEqual) {
        return { ...empty, verdict: "FAIL", cols_equal: false, ref_rows: ref.rows.length, conv_rows: conv.rows.length,
            note: "columns differ: " + ref.cols.join(",") + " vs " + conv.cols.join(",") };
    }
    const r = compareRows(ref.rows, conv.rows);
    return { verdict: r.verdict, n_mismatch: r.n_mismatch, samples: r.samples, cols_equal: true,
        ref_rows: ref.rows.length, conv_rows: conv.rows.length,
        note: r.verdict === "PASS" ? ref.rows.length + " rows" : r.n_mismatch + " row instance(s) differ" };
}
/** worst-of: FAIL > REF_MISSING > CONV_MISSING > PASS (datamatch.py's file-level rule) */
function worst(vs) {
    const order = ["FAIL", "REF_MISSING", "CONV_MISSING"];
    for (const v of order)
        if (vs.includes(v))
            return v;
    return "PASS";
}
/** a CSV as the interpreters and sas_print write it: header line, comma cells, optional quotes */
function parseCsv(text) {
    const lines = text.replace(/\r/g, "").split("\n").filter(l => l.length > 0);
    if (lines.length === 0)
        return null;
    const split = (l) => {
        const out = [];
        let cur = "", q = false;
        for (let i = 0; i < l.length; i++) {
            const c = l[i];
            if (q) {
                if (c === '"') {
                    if (l[i + 1] === '"') {
                        cur += '"';
                        i++;
                    }
                    else
                        q = false;
                }
                else
                    cur += c;
            }
            else if (c === '"')
                q = true;
            else if (c === ",") {
                out.push(cur);
                cur = "";
            }
            else
                cur += c;
        }
        out.push(cur);
        return out;
    };
    return { cols: split(lines[0]), rows: lines.slice(1).map(split) };
}
/** parse_sas_listing/1: PROC PRINT output — a title line naming the table, an "Obs ..." header,
 *  rows until a blank line. Returns tables keyed by the lower-cased title. */
function parseSasListing(text, names) {
    const out = {};
    const lines = text.split(/\r?\n/);
    const want = names ? new Set(names.map(n => n.toLowerCase())) : null;
    const isName = (s) => /^[a-z_][a-z0-9_.]*$/.test(s);
    let i = 0;
    while (i < lines.length) {
        const title = lines[i].trim().toLowerCase();
        const short = title.split(".").pop() || title;
        const looksLikeTitle = isName(title) && (!want || want.has(title) || want.has(short));
        if (looksLikeTitle) {
            let j = i + 1;
            while (j < lines.length && !lines[j].trim().toLowerCase().startsWith("obs")) {
                if (lines[j].trim() && isName(lines[j].trim().toLowerCase()))
                    break;
                j++;
            }
            if (j >= lines.length || !lines[j].trim().toLowerCase().startsWith("obs")) {
                i++;
                continue;
            }
            const cols = lines[j].trim().split(/\s+/).slice(1).map(c => c.toLowerCase());
            const rows = [];
            j++;
            while (j < lines.length && lines[j].trim()) {
                const parts = lines[j].trim().split(/\s+/);
                if (/^\d+$/.test(parts[0]))
                    rows.push(parts.slice(1));
                j++;
            }
            out[title] = { cols, rows };
            i = j;
        }
        else
            i++;
    }
    return out;
}
// browser global for the studio page (the compiled file is loaded with a plain <script>)
globalThis.DataMatch = { normalizeValue, compareRows, matchTables, worst, parseCsv, parseSasListing, FLOAT_DP };
