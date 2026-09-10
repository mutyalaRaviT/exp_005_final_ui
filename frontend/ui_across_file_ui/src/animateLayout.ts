// d3 on top of React Flow: when a new layout arrives, nodes that already
// existed glide from where they were to where ELK now wants them (d3-interpolate
// + d3-ease for the math; a setTimeout loop for the clock — not d3-timer, whose
// global queue React Flow's d3-zoom also drives, and not rAF, which a background
// tab freezes); new nodes fade in. React Flow
// only ever sees plain `setNodes` calls, so nothing in it changes.
//
// Edges need no special handling: ElkEdge draws its ELK route only while both
// handles sit on their anchors, and falls back to a smooth-step path while a
// node is in flight — so edges follow the animation and snap to the routed
// path on the last frame.
import type { Node } from '@xyflow/react'
import { interpolateNumber } from 'd3-interpolate'
import { easeCubicInOut } from 'd3-ease'

export interface TweenOptions {
  /** ms for the glide; 0 applies the target immediately */
  duration?: number
}

/** The node set at progress `t` in [0,1]: moving nodes interpolated, new nodes fading in. Pure. */
export function interpolateNodes<T extends Node>(prev: T[], next: T[], t: number): T[] {
  const prevById = new Map(prev.map((n) => [n.id, n]))
  const e = easeCubicInOut(Math.max(0, Math.min(1, t)))
  return next.map((n) => {
    const p = prevById.get(n.id)
    if (!p || p.parentId !== n.parentId) {
      // new here (or re-parented): appear in place
      return e >= 1 ? n : { ...n, style: { ...n.style, opacity: e } }
    }
    if (p.position.x === n.position.x && p.position.y === n.position.y) return n
    return {
      ...n,
      position: { x: interpolateNumber(p.position.x, n.position.x)(e), y: interpolateNumber(p.position.y, n.position.y)(e) },
    }
  })
}

/**
 * React Flow (12.x) keeps a node's measured size ONLY on the node object the app
 * hands it; a node handed over without `measured` is hidden until re-measured, and
 * when that wipe and React Flow's own size update land in the same render the
 * re-measure never fires (the node stays invisible — the rapid +/- bug). So every
 * node set we push carries `measured` over from the nodes React Flow holds now.
 */
export function keepMeasured<T extends Node>(next: T[], current: T[]): T[] {
  const measured = new Map(current.filter((n) => n.measured).map((n) => [n.id, n.measured]))
  return next.map((n) => {
    if (n.measured) return n
    const m = measured.get(n.id)
    return m ? { ...n, measured: m } : n
  })
}

/** Drive `apply` from prev to next over `duration` ms. Returns a stop function. */
export function tweenNodes<T extends Node>(prev: T[], next: T[], apply: (nodes: T[]) => void, opts: TweenOptions = {}): () => void {
  const duration = opts.duration ?? 450
  if (duration <= 0 || prev.length === 0) {
    apply(next)
    return () => {}
  }
  // setTimeout, not requestAnimationFrame: a background tab freezes rAF, and the
  // layout must still be applied there — animation is never allowed to gate correctness
  const FRAME_MS = 16
  let stopped = false
  let frame: ReturnType<typeof setTimeout> | null = null
  const start = performance.now()
  const step = () => {
    if (stopped) return
    const t = (performance.now() - start) / duration
    if (t >= 1) {
      stopped = true
      apply(next)
      return
    }
    apply(interpolateNodes(prev, next, t))
    frame = setTimeout(step, FRAME_MS)
  }
  frame = setTimeout(step, 0)
  return () => {
    if (!stopped) {
      stopped = true
      if (frame !== null) clearTimeout(frame)
    }
  }
}
