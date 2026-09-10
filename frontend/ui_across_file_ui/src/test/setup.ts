import '@testing-library/jest-dom/vitest'

class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = RO
// @ts-expect-error jsdom has no DOMMatrixReadOnly
globalThis.DOMMatrixReadOnly = class {
  m22 = 1
  constructor(_t?: string) {}
}
Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, get: () => 800 })
Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, get: () => 600 })
