import { describe, expect, it } from 'vitest'
import { currentMonth, dayLabel, fromLocalInput, shiftMonth, toLocalInput } from './dates'

describe('months', () => {
  it('formats the current month', () => {
    expect(currentMonth(new Date(2026, 0, 31))).toBe('2026-01')
  })
  it.each([
    ['2026-01', -1, '2025-12'],
    ['2026-12', 1, '2027-01'],
    ['2026-05', 0, '2026-05'],
    ['2026-03', -14, '2025-01'],
  ])('%s %+i -> %s', (month, delta, expected) => {
    expect(shiftMonth(month, delta)).toBe(expected)
  })
})

describe('datetime-local round trip', () => {
  it('keeps the same instant', () => {
    const iso = '2026-09-15T12:34:00.000Z'
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso)
  })
})

describe('dayLabel', () => {
  const today = new Date(2026, 8, 15)
  it('names today and yesterday', () => {
    expect(dayLabel('2026-09-15', today)).toBe('Today')
    expect(dayLabel('2026-09-14', today)).toBe('Yesterday')
  })
})
