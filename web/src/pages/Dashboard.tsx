import { Link } from 'react-router-dom'
import type { Transaction } from '../api'
import BudgetMeter from '../components/BudgetMeter'
import CategoryBars from '../components/CategoryBars'
import DailyChart from '../components/DailyChart'
import MonthPicker from '../components/MonthPicker'
import TransactionList from '../components/TransactionList'
import { formatINR } from '../money'
import { useSummary, useTransactions } from '../queries'

export default function Dashboard({
  month,
  setMonth,
  onEdit,
}: {
  month: string
  setMonth: (m: string) => void
  onEdit: (t: Transaction) => void
}) {
  const summary = useSummary(month)
  const recent = useTransactions({ month, limit: 5 })
  const s = summary.data

  const change = s && s.previous_expense_paise > 0 ? s.expense_paise / s.previous_expense_paise - 1 : null

  return (
    <>
      <MonthPicker month={month} onChange={setMonth} />
      {summary.isError && <p className="error">{summary.error.message}</p>}
      {s && (
        <>
          <section className="tiles">
            <div className="tile">
              <span className="tile-label">Spent</span>
              <span className="tile-value">{formatINR(s.expense_paise, { whole: true })}</span>
              {change !== null && (
                <span className="tile-delta">
                  {change >= 0 ? '▲' : '▼'} {Math.abs(Math.round(change * 100))}% vs last month
                </span>
              )}
            </div>
            <div className="tile">
              <span className="tile-label">Income</span>
              <span className="tile-value">{formatINR(s.income_paise, { whole: true })}</span>
              {s.income_paise > 0 && (
                <span className="tile-delta">Net {formatINR(s.income_paise - s.expense_paise, { whole: true })}</span>
              )}
            </div>
          </section>

          {s.budgets.length > 0 && (
            <section className="card">
              <h2>Budgets</h2>
              {s.budgets.map((b) => (
                <BudgetMeter key={b.category_id} name={b.name} spent={b.spent_paise} amount={b.amount_paise} />
              ))}
            </section>
          )}

          <section className="card">
            <h2>Where it went</h2>
            <CategoryBars items={s.by_category} month={month} />
          </section>

          <section className="card">
            <h2>Day by day</h2>
            <DailyChart daily={s.daily} />
          </section>
        </>
      )}

      <section className="card">
        <div className="card-head">
          <h2>Recent</h2>
          <Link to={`/transactions?month=${month}`}>See all</Link>
        </div>
        {recent.data?.items.length === 0 && <p className="muted small">No transactions this month. Tap + to add one.</p>}
        {recent.data && <TransactionList transactions={recent.data.items} onSelect={onEdit} />}
      </section>
    </>
  )
}
