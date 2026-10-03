import { budgetStatus } from '../budget'
import { formatINR } from '../money'

/** Status colour never stands alone: it always ships with an icon and a text label. */
export default function BudgetMeter({ name, spent, amount }: { name: string; spent: number; amount: number }) {
  const status = budgetStatus(spent, amount)
  return (
    <div className="meter">
      <div className="cat-row">
        <span>{name}</span>
        <span>
          {formatINR(spent, { whole: true })} <span className="muted">/ {formatINR(amount, { whole: true })}</span>
        </span>
      </div>
      <div
        className="track"
        role="meter"
        aria-label={`${name} budget`}
        aria-valuemin={0}
        aria-valuemax={amount}
        aria-valuenow={Math.min(spent, amount)}
        aria-valuetext={status.text}
      >
        <span className={`fill ${status.tone}`} style={{ width: `${Math.min((spent / amount) * 100, 100)}%` }} />
      </div>
      <div className={`status ${status.tone}`}>
        <span aria-hidden="true" className="status-icon">
          {status.icon}
        </span>
        {status.text}
      </div>
    </div>
  )
}
