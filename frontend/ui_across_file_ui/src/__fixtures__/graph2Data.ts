// Shared block-graph-v2 fixtures — same shapes as graph2.test.ts's inline
// data, exported here so GraphCanvasV2's component tests (and V2-6's
// stories) can reuse them without duplicating the fixture by hand.
//
// Two fixtures live here:
//   - `hood`/`B1`/`detailA`/`links`: the original 2-file pair from V2-5,
//     kept as-is because GraphCanvasV2.test.tsx already imports them.
//   - `hood3`/`detailLoader`/`detailBuilder`/`links3` (below): the richer
//     3-file pipeline (loader -> builder -> report) V2-6's stories need —
//     a macro-wrapped block and a same-pair link merge.
import type { BlockLink, FileDetail, Neighborhood } from '../api'

export const hood: Neighborhood = {
  nodes: [
    { id: 'a.sas', label: 'a.sas', folder: 'f', score: 0, cyclic: false },
    { id: 'b.sas', label: 'b.sas', folder: 'f', score: 1, cyclic: false },
  ],
  edges: [{ src: 'a.sas', dst: 'b.sas', tables: ['work.t', 'work.u'], level: 'project', provenance: 'inferred' }],
  story: [],
  order: {},
}

export const B1 = 'b_1_aaaa1111'

export const detailA: FileDetail = {
  fileid: 'a.sas',
  name: 'a.sas',
  folder: 'f',
  code: '',
  blocks: [
    {
      id: B1, status: 'PARSED', reads: 1, writes: 1, line_start: 1, line_end: 1,
      occurrences: [
        { id: `${B1}:t_1`, name: 'raw.x', role: 'read' },
        { id: `${B1}:t_2`, name: 'work.t', role: 'write' },
      ],
    },
  ],
  block_edges: [
    {
      src: 'raw.x', dst: 'work.t', tables: ['work.t'], level: 'block', provenance: 'fact',
      src_ref: `${B1}:t_1`, dst_ref: `${B1}:t_2`, block: B1,
    },
  ],
  file_edges: [],
  macro_calls: [],
  includes: [],
  missing_includes: [],
}

export const links: BlockLink[] = [
  {
    src_file: 'a.sas', src_block: B1, src_ref: `${B1}:t_2`,
    dst_file: 'b.sas', dst_block: B1, dst_ref: `${B1}:t_1`, table: 'work.t',
  },
  {
    src_file: 'a.sas', src_block: B1, src_ref: `${B1}:t_2`,
    dst_file: 'b.sas', dst_block: B1, dst_ref: `${B1}:t_1`, table: 'work.u',
  },
]

// --- 3-file pipeline: loader.sas -> builder.sas -> report.sas -------------
// loader writes stage.accounts; builder reads it into a %load_dims-wrapped
// block that builds work.customer_dim, then a second (unwrapped) block joins
// it into work.report_base for report.sas. Only loader and builder have
// FileDetails — report.sas stays a plain collapsed file node in every story,
// exactly like a real neighborhood where you haven't opened every file.

export const LB1 = 'b_1_10101010'
export const BB1 = 'b_1_20202020'
export const BB2 = 'b_2_30303030'

export const hood3: Neighborhood = {
  nodes: [
    { id: 'loader.sas', label: 'loader.sas', folder: 'etl', score: 0, cyclic: false },
    { id: 'builder.sas', label: 'builder.sas', folder: 'etl', score: 1, cyclic: false },
    { id: 'report.sas', label: 'report.sas', folder: 'etl', score: 2, cyclic: false },
  ],
  edges: [
    { src: 'loader.sas', dst: 'builder.sas', tables: ['stage.accounts'], level: 'project', provenance: 'inferred' },
    { src: 'builder.sas', dst: 'report.sas', tables: ['work.report_base'], level: 'project', provenance: 'inferred' },
  ],
  story: [],
  order: {},
}

export const detailLoader: FileDetail = {
  fileid: 'loader.sas',
  name: 'loader.sas',
  folder: 'etl',
  code: '',
  blocks: [
    {
      id: LB1, status: 'PARSED', reads: 1, writes: 1, line_start: 1, line_end: 1,
      occurrences: [
        { id: `${LB1}:t_1`, name: 'raw.accounts', role: 'read' },
        { id: `${LB1}:t_2`, name: 'stage.accounts', role: 'write' },
      ],
    },
  ],
  block_edges: [
    {
      src: 'raw.accounts', dst: 'stage.accounts', tables: ['stage.accounts'], level: 'block', provenance: 'fact',
      src_ref: `${LB1}:t_1`, dst_ref: `${LB1}:t_2`, block: LB1,
    },
  ],
  file_edges: [],
  macro_calls: [],
  includes: [],
  missing_includes: [],
}

export const detailBuilder: FileDetail = {
  fileid: 'builder.sas',
  name: 'builder.sas',
  folder: 'etl',
  code: '',
  blocks: [
    {
      id: BB1, status: 'PARSED', reads: 1, writes: 1, line_start: 1, line_end: 1,
      occurrences: [
        { id: `${BB1}:t_1`, name: 'stage.accounts', role: 'read' },
        { id: `${BB1}:t_2`, name: 'work.customer_dim', role: 'write' },
      ],
    },
    {
      id: BB2, status: 'PARSED', reads: 1, writes: 1, line_start: 2, line_end: 2,
      occurrences: [
        { id: `${BB2}:t_1`, name: 'work.customer_dim', role: 'read' },
        { id: `${BB2}:t_2`, name: 'work.report_base', role: 'write' },
      ],
    },
  ],
  block_edges: [
    {
      src: 'stage.accounts', dst: 'work.customer_dim', tables: ['stage.accounts'], level: 'block', provenance: 'fact',
      src_ref: `${BB1}:t_1`, dst_ref: `${BB1}:t_2`, block: BB1,
    },
    {
      src: 'work.customer_dim', dst: 'work.report_base', tables: ['work.customer_dim'], level: 'block', provenance: 'fact',
      src_ref: `${BB2}:t_1`, dst_ref: `${BB2}:t_2`, block: BB2,
    },
  ],
  file_edges: [
    {
      src: 'work.customer_dim', dst: 'work.customer_dim', tables: ['work.customer_dim'], level: 'file', provenance: 'inferred',
      src_ref: `${BB1}:t_2`, dst_ref: `${BB2}:t_1`, block: BB2,
    },
  ],
  // wraps BB1 only — BB2 stays outside any macro cluster
  macro_calls: [{ name: 'load_dims', instance: 1, block_ids: [BB1] }],
  includes: [],
  missing_includes: [],
}

// Two same-pair links (loader/LB1 -> builder/BB1, on different tables) so
// the label merges ("stage.accounts, stage.audit") once both files are
// expanded; the third link is a different pair (builder/BB2 -> report.sas)
// that stays unmerged.
export const links3: BlockLink[] = [
  {
    src_file: 'loader.sas', src_block: LB1, src_ref: `${LB1}:t_2`,
    dst_file: 'builder.sas', dst_block: BB1, dst_ref: `${BB1}:t_1`, table: 'stage.accounts',
  },
  {
    src_file: 'loader.sas', src_block: LB1, src_ref: `${LB1}:t_2`,
    dst_file: 'builder.sas', dst_block: BB1, dst_ref: `${BB1}:t_1`, table: 'stage.audit',
  },
  {
    src_file: 'builder.sas', src_block: BB2, src_ref: `${BB2}:t_2`,
    dst_file: 'report.sas', dst_block: 'b_1_40404040', dst_ref: 'b_1_40404040:t_1', table: 'work.report_base',
  },
]
