import { describe, expect, it } from 'vitest'
import { formatINR, paiseToInput, parseRupees } from './money'

describe('parseRupees', () => {
  it.each([
    ['180', 18000],
    ['180.5', 18050],
    ['180.05', 18005],
    ['1,250.50', 125050],
    ['₹ 99.99', 9999],
    ['0.01', 1],
    ['0.1', 10],
    ['  42 ', 4200],
  ])('%s -> %i paise', (input, paise) => {
    expect(parseRupees(input)).toBe(paise)
  })

  it.each(['', '0', '0.00', '-5', 'abc', '1.234', '1e3', '12.3.4', '1000000001'])(
    'rejects %j',
    (input) => {
      expect(parseRupees(input)).toBeNull()
    },
  )

  it('never loses a paisa to float rounding', () => {
    // 0.29 * 100 = 28.999999999999996 in floating point
    expect(parseRupees('0.29')).toBe(29)
    expect(parseRupees('1.15')).toBe(115)
  })
})

describe('paiseToInput', () => {
  it.each([
    [18000, '180'],
    [18050, '180.50'],
    [5, '0.05'],
  ])('%i -> %s', (paise, text) => {
    expect(paiseToInput(paise)).toBe(text)
    expect(parseRupees(text)).toBe(paise)
  })
})

describe('formatINR', () => {
  it('uses Indian digit grouping', () => {
    expect(formatINR(1234565000)).toBe('₹1,23,45,650')
    expect(formatINR(12345650)).toBe('₹1,23,456.50')
  })
  it('can round to whole rupees', () => {
    expect(formatINR(12345650, { whole: true })).toBe('₹1,23,457')
  })
})
