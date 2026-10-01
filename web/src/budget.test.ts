import { describe, expect, it } from 'vitest'
import { budgetStatus } from './budget'

describe('budgetStatus', () => {
  it.each([
    [0, 1000_00, 'good', '₹1,000 left'],
    [79_99, 100_00, 'good', '₹20 left'],
    [80_00, 100_00, 'warning', '80% used'],
    [100_00, 100_00, 'warning', '100% used'],
    [125_00, 100_00, 'critical', 'Over by ₹25'],
  ])('spent %i of %i -> %s', (spent, amount, tone, text) => {
    expect(budgetStatus(spent, amount)).toMatchObject({ tone, text })
  })
})
