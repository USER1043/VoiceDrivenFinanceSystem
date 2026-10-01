import { formatINR } from './money'

export type BudgetStatus = { tone: 'good' | 'warning' | 'critical'; icon: string; text: string }

export function budgetStatus(spent: number, amount: number): BudgetStatus {
  const ratio = spent / amount
  if (ratio > 1) return { tone: 'critical', icon: '✕', text: `Over by ${formatINR(spent - amount, { whole: true })}` }
  if (ratio >= 0.8) return { tone: 'warning', icon: '!', text: `${Math.round(ratio * 100)}% used` }
  return { tone: 'good', icon: '✓', text: `${formatINR(amount - spent, { whole: true })} left` }
}
