// The columns of a table occurrence, read off the block's own SAS text.
//
// The :8000 API knows tables, not columns (BlockInfo.occurrences is id/name/role),
// and the Bench's node/4 is not wired into UI1 yet. Until it is, this reads the
// column names a BA can see in the code: a PROC SQL select list for the table it
// writes, the qualified `alias.col` references for each table it reads, and the
// INPUT / LENGTH lists of a DATA step. Anything else → [] (the node says "no
// columns known" rather than guessing). Pure; no DOM, no fetch.
import type { BlockInfo, Occurrence } from './api'

const IDENT = '[A-Za-z_][A-Za-z0-9_]*'

/** The block's lines, comments stripped, one string. */
function blockText(code: string, block: BlockInfo): string {
  const lines = code.split('\n').slice(Math.max(0, block.line_start - 1), block.line_end)
  return lines.join('\n').replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\*[^;]*;/gm, ' ')
}

/** Split on top-level commas (not inside parentheses). */
function splitTop(s: string): string[] {
  const out: string[] = []
  let depth = 0, cur = ''
  for (const ch of s) {
    if (ch === '(') depth++
    else if (ch === ')') depth--
    if (ch === ',' && depth === 0) { out.push(cur); cur = '' } else cur += ch
  }
  if (cur.trim()) out.push(cur)
  return out.map((x) => x.trim()).filter(Boolean)
}

/** alias → table for every `from`/`join` clause: `from work.a t inner join work.b as x on …` */
function aliasesOf(sql: string): Map<string, string> {
  const m = new Map<string, string>()
  const re = new RegExp(`\\b(?:from|join)\\s+(${IDENT}(?:\\.${IDENT})?)(?:\\s+as)?\\s+(${IDENT})?`, 'gi')
  for (const hit of sql.matchAll(re)) {
    const [, table, alias] = hit
    const a = alias && !/^(on|where|inner|left|right|full|outer|join|group|order|having)$/i.test(alias) ? alias : table
    m.set(a.toLowerCase(), table.toLowerCase())
  }
  return m
}

/** The name a select item lands as: `x as y` → y, `t.col` → col, `t.*` → *, `sum(x) as s` → s. */
function selectName(item: string): string {
  item = stripAttrs(item)
  const as = item.match(new RegExp(`\\bas\\s+(${IDENT})\\s*$`, 'i'))
  if (as) return as[1]
  const dotted = item.match(new RegExp(`^(${IDENT})\\.(${IDENT}|\\*)\\s*$`))
  if (dotted) return dotted[2]
  const plain = item.match(new RegExp(`^(${IDENT}|\\*)\\s*$`))
  return plain ? plain[1] : item.replace(/\s+/g, ' ')
}

const SQL_WORDS = new Set(['as', 'case', 'when', 'then', 'else', 'end', 'and', 'or', 'not', 'is', 'null', 'in', 'like', 'between', 'distinct', 'calculated', 'desc', 'asc', 'length', 'format', 'label'])
/** Unqualified column names in an expression: identifiers that are not a function call, a keyword, or inside quotes. */
function bareIdents(expr: string): string[] {
  const noStr = expr.replace(/'[^']*'|"[^"]*"/g, ' ')
  return uniq([...noStr.matchAll(new RegExp(`(?<![.\\w])(${IDENT})\\b(?!\\s*\\()`, 'g'))].map((m) => m[1]).filter((w) => !SQL_WORDS.has(w.toLowerCase()) && !/^\d/.test(w)))
}

function procSqlColumns(sql: string, occ: Occurrence): string[] {
  const sel = sql.match(/\bselect\b([\s\S]*?)\bfrom\b/i)
  if (!sel) return []
  const items = splitTop(sel[1])
  if (occ.role === 'write') return uniq(items.map(selectName))
  // a read table: every `alias.col` mention anywhere in the block that resolves to it
  const aliases = aliasesOf(sql)
  const table = occ.name.toLowerCase()
  const cols: string[] = []
  for (const hit of sql.matchAll(new RegExp(`\\b(${IDENT})\\.(${IDENT}|\\*)`, 'g'))) {
    const [, a, col] = hit
    if (aliases.get(a.toLowerCase()) === table) cols.push(col)
  }
  // the only table in the query: every bare column name the query mentions is one of its columns
  if (cols.length === 0 && new Set(aliases.values()).size === 1 && [...aliases.values()][0] === table) {
    const clauses = sql.replace(/\b(from|join)\s+[\w.]+(\s+as)?(\s+\w+)?/gi, ' ').replace(/\bcreate\s+table\s+[\w.]+\s+as\b/i, ' ')
    return bareIdents(clauses.replace(/\b(proc\s+sql|select|where|group\s+by|order\s+by|having|quit|on|inner|left|right|full|outer|union|all)\b/gi, ' ')).filter((c) => !items.some((it) => new RegExp(`\\bas\\s+${c}\\s*$`, 'i').test(it)))
  }
  return uniq(cols)
}

function dataStepColumns(text: string, occ: Occurrence): string[] {
  if (occ.role !== 'write') return []
  const cols: string[] = []
  for (const hit of text.matchAll(/\b(?:input|length)\s+([^;]+);/gi)) {
    for (const tok of hit[1].split(/\s+/)) {
      if (/^\$?\d/.test(tok) || tok.startsWith('$') || tok.startsWith('@') || tok.startsWith('&')) continue
      if (new RegExp(`^${IDENT}$`).test(tok)) cols.push(tok)
    }
  }
  return uniq(cols)
}

const uniq = (xs: string[]) => [...new Set(xs)]
/** drop SAS column attributes after a select item: `length=12`, `format=8.2`, `label='x'` */
const stripAttrs = (item: string) => item.replace(/\s+(length|format|informat|label)\s*=\s*('[^']*'|\S+)/gi, '').trim()

/** Column names of `occ` inside `block`, in code order; [] when the code does not say. */
export function columnsOf(code: string, block: BlockInfo, occ: Occurrence): string[] {
  const text = blockText(code, block)
  const kind = (block.kind ?? '').toLowerCase()
  if (kind.startsWith('proc sql')) return procSqlColumns(text, occ)
  if (kind === 'data') return dataStepColumns(text, occ)
  return []
}

/** Why a read table flows into the written table of the same block, in BA words:
 *  "from · 4 cols", "inner join on acct_id · 4 cols", "… · filter amt_usd_sum >= 1000".
 *  Empty when the code does not say (the edge then stays unlabelled). */
export function reasonOf(code: string, block: BlockInfo, from: Occurrence, to: Occurrence): string {
  const text = blockText(code, block)
  const kind = (block.kind ?? '').toLowerCase()
  const cols = columnsOf(code, block, from)
  const nCols = cols.length ? `${cols.length} col${cols.length === 1 ? '' : 's'}` : ''
  if (kind === 'data') {
    if (new RegExp(`\\b(set|merge)\\s+[^;]*\\b${from.name.replace('.', '\\.')}\\b`, 'i').test(text)) return 'set'
    return ''
  }
  if (!kind.startsWith('proc sql')) return ''
  const aliases = aliasesOf(text)
  const table = from.name.toLowerCase()
  const alias = [...aliases.entries()].find(([, t]) => t === table)?.[0]
  if (!alias) return ''
  const parts: string[] = []
  // the clause this table enters through: `from work.x t` or `<kind> join work.x t on …`
  const join = text.match(new RegExp(`\\b((?:inner|left|right|full)?\\s*(?:outer\\s+)?join)\\s+${table.replace('.', '\\.')}(?:\\s+as)?\\s+${alias}\\b\\s+on\\s+([^;]*?)(?=\\b(?:inner|left|right|full|join|where|group|order|having)\\b|;|$)`, 'i'))
  if (join) {
    const onCols = uniq([...join[2].matchAll(new RegExp(`\\b${alias}\\.(${IDENT})`, 'gi'))].map((m) => m[1]))
    parts.push(`${join[1].replace(/\s+/g, ' ').toLowerCase()} on ${onCols.join(', ') || '…'}`)
  } else parts.push(/\bunion\b/i.test(text) ? 'union' : 'from')
  const where = text.match(/\bwhere\b([\s\S]*?)(?=\b(?:group|order|having)\b|;|$)/i)
  if (where && new RegExp(`\\b${alias}\\.`, 'i').test(where[1])) {
    const cond = where[1].replace(new RegExp(`\\b${alias}\\.`, 'gi'), '').replace(/\s+/g, ' ').trim()
    parts.push(`filter ${cond.length > 28 ? cond.slice(0, 26) + '…' : cond}`)
  }
  if (nCols) parts.push(nCols)
  return parts.join(' · ')
}

export interface ColumnFlow { from: string; to: string; why: string }

/** Column → column flows from a read table into the written table of the same
 *  PROC SQL block, each with why: `carried` (same name), `renamed x`, or
 *  `computed <expr>`. `a.*` carries every known column. [] when the code does not say. */
export function columnFlows(code: string, block: BlockInfo, from: Occurrence, to: Occurrence): ColumnFlow[] {
  if (!(block.kind ?? '').toLowerCase().startsWith('proc sql') || to.role !== 'write') return []
  const text = blockText(code, block)
  // a union: one select list per branch; the first names the target columns, the rest are positional
  const branches = text.split(/\bunion(?:\s+all)?\b/i).map((b) => b.match(/\bselect\b([\s\S]*?)\bfrom\b/i)?.[1]).filter((b): b is string => Boolean(b))
  if (!branches.length) return []
  const targets = splitTop(branches[0]).map(selectName)
  const aliases = aliasesOf(text)
  const table = from.name.toLowerCase()
  const mine = new Set([...aliases.entries()].filter(([, t]) => t === table).map(([a]) => a))
  const single = new Set(aliases.values()).size === 1 && aliases.has([...aliases.keys()][0]) && [...aliases.values()][0] === table
  const out: ColumnFlow[] = []
  for (const branch of branches) for (const [i, raw] of splitTop(branch).entries()) {
    const item = stripAttrs(raw)
    const asM = item.match(new RegExp(`^([\\s\\S]*?)\\s+as\\s+(${IDENT})\\s*$`, 'i'))
    const expr = (asM ? asM[1] : item).trim()
    const target = targets[i] ?? (asM ? asM[2] : selectName(item))
    const star = expr.match(new RegExp(`^(${IDENT})\\.\\*$`))
    if (star) {
      if (mine.has(star[1].toLowerCase())) for (const c of columnsOf(code, block, from).filter((c) => c !== '*')) out.push({ from: c, to: c, why: 'carried' })
      continue
    }
    const qualified = [...expr.matchAll(new RegExp(`\\b(${IDENT})\\.(${IDENT})\\b`, 'g'))].filter((m) => mine.has(m[1].toLowerCase())).map((m) => m[2])
    const refs = qualified.length || !single ? qualified : bareIdents(expr)
    const plain = expr.match(new RegExp(`^(${IDENT})$`))
    if (refs.length === 0) continue
    const isRef = new RegExp(`^${IDENT}\\.${IDENT}$`).test(expr) || (single && plain)
    const src = isRef ? (plain ? plain[1] : refs[0]) : null
    if (src && target === src) out.push({ from: src, to: target, why: 'carried' })
    else if (src) out.push({ from: src, to: target, why: `renamed ${src}` })
    else for (const r of uniq(refs)) out.push({ from: r, to: target, why: `computed ${expr.replace(/\s+/g, ' ').slice(0, 30)}` })
  }
  return out
}
