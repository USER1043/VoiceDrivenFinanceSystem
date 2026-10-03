import { Link } from 'react-router-dom'
import type { Summary } from '../api'
import { formatINR } from '../money'

/** One hue for magnitude; name and amount are direct labels in text ink. */
export default function CategoryBars({ items, month }: { items: Summary['by_category']; month: string }) {
  if (!items.length) return <p className="muted small">Nothing spent yet.</p>
  const max = items[0].spent_paise
  const total = items.reduce((sum, c) => sum + c.spent_paise, 0)
  return (
    <ul className="cat-bars">
      {items.map((c) => {
        const content = (
          <>
            <span className="cat-row">
              <span>{c.name}</span>
              <span>
                {formatINR(c.spent_paise, { whole: true })}{' '}
                <span className="muted">{Math.round((c.spent_paise / total) * 100)}%</span>
              </span>
            </span>
            <span className="track">
              <span className="fill" style={{ width: `${Math.max((c.spent_paise / max) * 100, 1)}%` }} />
            </span>
          </>
        )
        return (
          <li key={c.category_id ?? 'none'}>
            {c.category_id === null ? (
              <div className="cat-link">{content}</div>
            ) : (
              <Link className="cat-link" to={`/transactions?month=${month}&category=${c.category_id}`}>
                {content}
              </Link>
            )}
          </li>
        )
      })}
    </ul>
  )
}
