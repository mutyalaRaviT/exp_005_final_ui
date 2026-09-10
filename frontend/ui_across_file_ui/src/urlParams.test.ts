import { describe, expect, it } from 'vitest'
import { readParams, writeParams } from './urlParams'

describe('urlParams', () => {
  it('reads the 5173 deep link', () => {
    expect(readParams('?file=ankitha_1%2F04_build_accounts.sas&up=1&down=1')).toEqual({
      file: 'ankitha_1/04_build_accounts.sas', up: 1, down: 1,
    })
  })
  it('defaults up/down to 1 and clamps to 0..3', () => {
    expect(readParams('?table=work.accounts')).toEqual({ table: 'work.accounts', up: 1, down: 1 })
    expect(readParams('?file=a&up=9&down=-2')).toEqual({ file: 'a', up: 3, down: 0 })
  })
  it('writes a round-trippable query', () => {
    const p = { file: 'ankitha_1/04_build_accounts.sas', up: 2, down: 0 }
    expect(writeParams(p)).toBe('?file=ankitha_1%2F04_build_accounts.sas&up=2&down=0')
    expect(readParams(writeParams(p))).toEqual(p)
  })
})
