import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { Transaction } from '../api'
import MonthPicker from '../components/MonthPicker'
import TransactionList from '../components/TransactionList'
import { formatINR } from '../money'
import { groupedCategories, useCategories, useTransactions } from '../queries'

const PAGE = 50

export default function Transactions({
  month: appMonth,
  setMonth: setAppMonth,
  onEdit,
}: {
  month: string
  setMonth: (m: string) => void
  onEdit: (t: Transaction) => void
}) {
  const [params, setParams] = useSearchParams()
  const [limit, setLimit] = useState(PAGE)
  const categories = useCategories()
  const category = params.get('category') ?? ''
  const q = params.get('q') ?? ''
  // The URL's ?month= (from dashboard links or the picker) wins; otherwise the shared month.
  const month = params.get('month') ?? appMonth

  function changeMonth(next: string) {
    setAppMonth(next) // keep the dashboard on the same month
    setParam('month', next)
  }
  const list = useTransactions({ month, category_id: category ? Number(category) : undefined, q, limit })

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
    setLimit(PAGE)
  }

  const items = list.data?.items ?? []
  const spent = items.filter((t) => t.kind === 'expense').reduce((sum, t) => sum + t.amount_paise, 0)

  return (
    <>
      <MonthPicker month={month} onChange={changeMonth} />
      <div className="filters">
        <select aria-label="Category" value={category} onChange={(e) => setParam('category', e.target.value)}>
          <option value="">All categories</option>
          {(['expense', 'income'] as const).map((kind) =>
            groupedCategories(categories.data ?? [], kind).map(({ parent, children }) => [
              <option key={parent.id} value={parent.id}>
                {parent.name}
              </option>,
              ...children.map((c) => (
                <option key={c.id} value={c.id}>
                  {'  '}
                  {c.name}
                </option>
              )),
            ]),
          )}
        </select>
        <input type="search" placeholder="Search merchant or note" aria-label="Search" value={q} onChange={(e) => setParam('q', e.target.value)} />
      </div>

      {list.isError && <p className="error">{list.error.message}</p>}
      {list.data && (
        <p className="muted small">
          {list.data.total} transaction{list.data.total === 1 ? '' : 's'}
          {list.data.total <= items.length && spent > 0 ? ` · ${formatINR(spent)} spent` : ''}
        </p>
      )}
      {items.length > 0 && (
        <section className="card flush">
          <TransactionList transactions={items} onSelect={onEdit} />
        </section>
      )}
      {list.data && list.data.total > items.length && (
        <button type="button" className="secondary wide" onClick={() => setLimit(limit + PAGE)} disabled={list.isFetching}>
          {list.isFetching ? 'Loading…' : 'Show more'}
        </button>
      )}
    </>
  )
}
