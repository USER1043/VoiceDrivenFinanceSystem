import type { Transaction } from '../api'
import { dayKey, dayLabel, timeLabel } from '../dates'
import { formatINR } from '../money'
import { categoryLabel, useAccounts, useCategories } from '../queries'

export default function TransactionList({
  transactions,
  onSelect,
}: {
  transactions: Transaction[]
  onSelect: (t: Transaction) => void
}) {
  const categories = useCategories()
  const accounts = useAccounts()
  const accountName = (id: number) => accounts.data?.find((a) => a.id === id)?.name ?? ''

  const days: [string, Transaction[]][] = []
  for (const t of transactions) {
    const key = dayKey(t.occurred_at)
    const last = days[days.length - 1]
    if (last && last[0] === key) last[1].push(t)
    else days.push([key, [t]])
  }

  return (
    <div className="txn-list">
      {days.map(([key, items]) => (
        <section key={key}>
          <h3 className="day-head">{dayLabel(key)}</h3>
          <ul>
            {items.map((t) => (
              <li key={t.id}>
                <button type="button" className="txn" onClick={() => onSelect(t)}>
                  <span className="txn-main">
                    <span className="txn-title">{t.merchant || categoryLabel(categories.data, t.category_id)}</span>
                    <span className="txn-sub">
                      {t.merchant ? `${categoryLabel(categories.data, t.category_id)} · ` : ''}
                      {accountName(t.account_id)} · {timeLabel(t.occurred_at)}
                    </span>
                  </span>
                  <span className={t.kind === 'income' ? 'txn-amount income' : 'txn-amount'}>
                    {t.kind === 'income' ? '+' : '−'}
                    {formatINR(t.amount_paise)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
