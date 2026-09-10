// THROWAWAY MOCK — not part of the app, not imported by src/.
// Question it answers: if a table on the UI1 canvas can be opened to show its
// columns, what does the space between two tables look like? Answer: one edge
// per column pair, each carrying the transform that made the target column.
// Shape borrowed from lineage_ux/explorer/index_v3.html (program > block >
// table > column, column-level edges with a transform string).
// Serve: npx vite --port 5188  ->  /mock/column-lineage.html
import { StrictMode, useCallback, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Background, Controls, Handle, Position, ReactFlow, ReactFlowProvider } from '@xyflow/react'
import type { Edge, Node, NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import '../src/theme.css'
import './mock.css'

const ROW_H = 26
const HEAD_H = 30

type Col = { key: string; type: string; pk?: boolean }
type TableData = { name: string; cols: Col[]; role: 'read' | 'write' }

/** the one new node type: a table you can see inside. Every column row is its
 *  own React Flow handle, which is what lets an edge land on a column. */
function TableNode({ id, data }: NodeProps) {
  const d = data as unknown as TableData & { lit: Set<string>; onCol: (c: string) => void; dim: boolean }
  return (
    <div className={`mk-tbl role-${d.role}${d.dim ? ' off' : ''}`}>
      <div className="mk-tbl-hd">
        <span className="mk-dot" />
        {d.name}
        <span className="mk-kind">{d.role === 'read' ? 'reads' : 'writes'}</span>
      </div>
      {d.cols.map((c) => {
        const lit = d.lit.has(`${id}.${c.key}`)
        return (
          <div
            key={c.key}
            className={`mk-col${lit ? ' lit' : ''}`}
            style={{ height: ROW_H }}
            onClick={(e) => { e.stopPropagation(); d.onCol(`${id}.${c.key}`) }}
          >
            <Handle type="target" position={Position.Left} id={c.key} className="mk-h" />
            <span className="mk-cn">{c.key}</span>
            {c.pk && <span className="mk-pk">pk</span>}
            <span className="mk-ct">{c.type}</span>
            <Handle type="source" position={Position.Right} id={c.key} className="mk-h" />
          </div>
        )
      })}
    </div>
  )
}

/** the block that owns both tables — UI1 already draws this, it just gains depth */
function BlockNode({ data }: NodeProps) {
  const d = data as unknown as { label: string; kind: string }
  return (
    <div className="mk-blk">
      <div className="mk-blk-hd"><span className="mk-blk-kind">{d.kind}</span>{d.label}</div>
    </div>
  )
}

const SRC: Col[] = [
  { key: 'account_id', type: 'str', pk: true },
  { key: 'customer_id', type: 'str' },
  { key: 'currency', type: 'str' },
  { key: 'balance', type: 'num' },
  { key: 'open_date', type: 'date' },
]
const TGT: Col[] = [
  { key: 'account_id', type: 'str', pk: true },
  { key: 'customer_id', type: 'str' },
  { key: 'balance_usd', type: 'num' },
  { key: 'opened_at', type: 'ts' },
]

/** the whole point of the mock: what sits between two columns */
const LINKS = [
  { from: 'account_id', to: 'account_id', tx: 'passthrough', kind: 'copy' },
  { from: 'customer_id', to: 'customer_id', tx: 'passthrough', kind: 'copy' },
  { from: 'open_date', to: 'opened_at', tx: 'cast → timestamp', kind: 'cast' },
  { from: 'balance', to: 'balance_usd', tx: 'balance × rate_to_usd', kind: 'expr' },
  { from: 'currency', to: 'balance_usd', tx: 'join on currency', kind: 'join' },
]

const nodeTypes = { table: TableNode, block: BlockNode }

function Mock() {
  const [picked, setPicked] = useState<string | null>(null)
  const [showTx, setShowTx] = useState(true)

  // a picked column lights its own row, the rows it reaches, and those edges
  const { lit, litEdges } = useMemo(() => {
    const litSet = new Set<string>()
    const edgeSet = new Set<string>()
    if (picked) {
      litSet.add(picked)
      for (const l of LINKS) {
        const a = `raw_accounts.${l.from}`
        const b = `stg_accounts.${l.to}`
        if (picked === a || picked === b) { litSet.add(a); litSet.add(b); edgeSet.add(`${l.from}->${l.to}`) }
      }
    }
    return { lit: litSet, litEdges: edgeSet }
  }, [picked])

  const onCol = useCallback((full: string) => setPicked((p) => (p === full ? null : full)), [])

  const nodes: Node[] = [
    { id: 'block', type: 'block', position: { x: 0, y: 0 }, data: { label: 'stage_accounts', kind: 'proc sql' },
      style: { width: 920, height: HEAD_H + 24 + Math.max(SRC.length, TGT.length) * ROW_H + HEAD_H + 34 }, draggable: false, selectable: false },
    { id: 'raw_accounts', type: 'table', parentId: 'block', extent: 'parent' as const, position: { x: 26, y: 52 },
      data: { name: 'raw_accounts', cols: SRC, role: 'read', lit, onCol, dim: Boolean(picked) && !SRC.some((c) => lit.has(`raw_accounts.${c.key}`)) },
      style: { width: 250 } },
    { id: 'stg_accounts', type: 'table', parentId: 'block', extent: 'parent' as const, position: { x: 644, y: 52 },
      data: { name: 'stg_accounts', cols: TGT, role: 'write', lit, onCol, dim: Boolean(picked) && !TGT.some((c) => lit.has(`stg_accounts.${c.key}`)) },
      style: { width: 250 } },
  ]

  const edges: Edge[] = LINKS.map((l) => {
    const on = litEdges.has(`${l.from}->${l.to}`)
    const dim = Boolean(picked) && !on
    return {
      id: `${l.from}->${l.to}`,
      source: 'raw_accounts', sourceHandle: l.from,
      target: 'stg_accounts', targetHandle: l.to,
      type: 'smoothstep',
      label: showTx ? l.tx : undefined,
      labelShowBg: true,
      className: `mk-edge kind-${l.kind}${on ? ' on' : ''}${dim ? ' off' : ''}`,
      style: { strokeWidth: on ? 2 : 1.2 },
    }
  })

  const pickedLinks = picked
    ? LINKS.filter((l) => picked === `raw_accounts.${l.from}` || picked === `stg_accounts.${l.to}`)
    : []

  return (
    <div id="app" className="mk-app">
      <div id="top">
        <div className="brand">lineage<span>Q</span> Graph</div>
        <span className="tag ir">mock</span>
        <div className="file"><span className="mk-note">a table on the UI1 canvas, opened: 1 block · 2 tables · 5 columns</span></div>
        <div className="receipts">
          <span className="pill idle"><i />{LINKS.length} column edges</span>
        </div>
        <div className="engine">
          <button className={showTx ? 'on' : undefined} onClick={() => setShowTx(true)}>transforms</button>
          <button className={showTx ? undefined : 'on'} onClick={() => setShowTx(false)}>edges only</button>
        </div>
        <button className="theme" title="theme" onClick={() => {
          const r = document.documentElement
          r.setAttribute('data-theme', r.getAttribute('data-theme') === 'dark' ? 'light' : 'dark')
        }}>◐</button>
      </div>

      <div className="mk-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onPaneClick={() => setPicked(null)}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          minZoom={0.3}
          nodesConnectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={18} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <div className="mk-inspect">
        <div className="mk-ih">
          <span className="tag py">column</span>
          <b>{picked ? picked.split('.').slice(-1)[0] : '—'}</b>
          <span className="mk-note">{picked ? picked.replace('.', ' · ') : 'click a column row to trace it'}</span>
          <span className="mk-count">{picked ? `${pickedLinks.length} edge(s)` : `${LINKS.length} total`}</span>
        </div>
        <div className="mk-ib">
          {(picked ? pickedLinks : LINKS).map((l) => (
            <div className={`mk-row kind-${l.kind}`} key={`${l.from}->${l.to}`}>
              <span className="mk-from">raw_accounts.{l.from}</span>
              <span className="mk-arrow">→</span>
              <span className="mk-to">stg_accounts.{l.to}</span>
              <span className="mk-tx">{l.tx}</span>
              <span className="mk-kindchip">{l.kind}</span>
            </div>
          ))}
        </div>
      </div>

      <div id="status">
        <span className="mode">MOCK</span>
        <span className="mono">the transform is the answer to "what happens between two columns"</span>
        <div className="keys"><span>click a column · click the pane to clear</span></div>
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode><ReactFlowProvider><Mock /></ReactFlowProvider></StrictMode>,
)
