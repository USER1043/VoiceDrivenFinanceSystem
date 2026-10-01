import { currentMonth, monthLabel, shiftMonth } from '../dates'

export default function MonthPicker({ month, onChange }: { month: string; onChange: (m: string) => void }) {
  const isCurrent = month >= currentMonth()
  return (
    <div className="month-picker">
      <button type="button" className="icon-button" aria-label="Previous month" onClick={() => onChange(shiftMonth(month, -1))}>
        ‹
      </button>
      <span>{monthLabel(month)}</span>
      <button
        type="button"
        className="icon-button"
        aria-label="Next month"
        disabled={isCurrent}
        onClick={() => onChange(shiftMonth(month, 1))}
      >
        ›
      </button>
    </div>
  )
}
