import { type FormEvent, useState } from 'react'
import type { Category } from '../api'
import { budgetStatus } from '../budget'
import { currentMonth } from '../dates'
import { formatINR, paiseToInput, parseRupees } from '../money'
import { groupedCategories, useBudgets, useCategories, useSetBudget, useSummary } from '../queries'

function BudgetRow({
  category,
  amount,
  spent,
  nested,
}: {
  category: Category
  amount?: number
  spent?: number
  nested?: boolean
}) {
  const setBudget = useSetBudget()
  const [value, setValue] = useState(amount ? paiseToInput(amount) : '')
  const parsed = parseRupees(value)
  const dirty = value !== (amount ? paiseToInput(amount) : '')
  const status = amount && spent !== undefined ? budgetStatus(spent, amount) : null

  function submit(event: FormEvent) {
    event.preventDefault()
    if (value.trim() === '') setBudget.mutate({ categoryId: category.id, amount: null })
    else if (parsed !== null) setBudget.mutate({ categoryId: category.id, amount: parsed })
  }

  return (
    <form className={nested ? 'budget-row nested' : 'budget-row'} onSubmit={submit}>
      <div className="budget-name">
        <span>{category.name}</span>
        <span className="muted small">
          {spent !== undefined && (amount || spent > 0) && `${formatINR(spent, { whole: true })} spent this month`}
          {status && (
            <span className={`status ${status.tone}`}>
              {' '}
              · <span aria-hidden="true">{status.icon}</span> {status.text}
            </span>
          )}
        </span>
      </div>
      <input
        inputMode="decimal"
        placeholder="No budget"
        aria-label={`${category.name} monthly budget in rupees`}
        value={value}
        aria-invalid={value !== '' && parsed === null}
        onChange={(e) => setValue(e.target.value)}
      />
      <button type="submit" className="secondary" disabled={!dirty || (value !== '' && parsed === null) || setBudget.isPending}>
        Save
      </button>
      {setBudget.isError && <p className="error">{setBudget.error.message}</p>}
    </form>
  )
}

export default function Budgets() {
  const categories = useCategories()
  const budgets = useBudgets()
  const summary = useSummary(currentMonth())
  if (!categories.data || !budgets.data) return null

  const amountFor = new Map(budgets.data.map((b) => [b.category_id, b.amount_paise]))
  const spentFor = new Map(summary.data?.by_category.map((c) => [c.category_id, c.spent_paise]))
  const budgetSpent = new Map(summary.data?.budgets.map((b) => [b.category_id, b.spent_paise]))
  const total = budgets.data.reduce((sum, b) => sum + b.amount_paise, 0)

  return (
    <>
      <p className="muted small">
        Monthly limits. A budget on a group (like Food) covers everything inside it. Leave a box empty to remove a budget.
        {total > 0 && ` Total budgeted: ${formatINR(total, { whole: true })}.`}
      </p>
      <section className="card">
        {groupedCategories(categories.data, 'expense').map(({ parent, children }) => (
          <div key={parent.id} className="budget-group">
            <BudgetRow
              category={parent}
              amount={amountFor.get(parent.id)}
              spent={budgetSpent.get(parent.id) ?? spentFor.get(parent.id) ?? 0}
            />
            {children.map((c) => (
              <BudgetRow key={c.id} nested category={c} amount={amountFor.get(c.id)} spent={budgetSpent.get(c.id)} />
            ))}
          </div>
        ))}
      </section>
    </>
  )
}
