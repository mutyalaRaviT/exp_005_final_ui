import type { ReactNode } from 'react'

export default function Banner({ kind, children }: { kind: 'error' | 'info'; children: ReactNode }) {
  return (
    <div className={`banner banner-${kind}`} role={kind === 'error' ? 'alert' : 'status'} data-cid="banner">
      {children}
    </div>
  )
}
