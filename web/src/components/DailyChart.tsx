import { useState } from 'react'
import type { Summary } from '../api'
import { formatINR } from '../money'

const HEIGHT = 120
const BAR_GAP = 2
const RADIUS = 4

/** Rounded top, square bottom anchored to the baseline. */
function barPath(x: number, w: number, h: number): string {
  const r = Math.min(RADIUS, w / 2, h)
  const y = HEIGHT - h
  return `M${x},${HEIGHT} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${HEIGHT} Z`
}

export default function DailyChart({ daily }: { daily: Summary['daily'] }) {
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(...daily.map((d) => d.expense_paise), 0)
  const slot = 10
  const width = daily.length * slot
  const label = (day: string) => new Date(`${day}T00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

  if (max === 0) return <p className="muted small">No spending this month yet.</p>
  const active = hover === null ? null : daily[hover]

  return (
    <figure className="chart">
      <div className="chart-tooltip" aria-live="polite">
        {active ? (
          <>
            <strong>{formatINR(active.expense_paise)}</strong> <span className="muted">on {label(active.day)}</span>
          </>
        ) : (
          <span className="muted">Highest day {formatINR(max, { whole: true })} · tap a bar</span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${width} ${HEIGHT}`}
        preserveAspectRatio="none"
        className="chart-svg"
        role="img"
        aria-label="Spending per day this month"
        onMouseLeave={() => setHover(null)}
      >
        {daily.map((d, i) => {
          const h = (d.expense_paise / max) * (HEIGHT - 4)
          return (
            <g key={d.day} onMouseEnter={() => setHover(i)} onClick={() => setHover(i)}>
              {/* Hit target spans the full column, wider than the mark. */}
              <rect x={i * slot} y={0} width={slot} height={HEIGHT} fill="transparent" />
              {h > 0 && (
                <path
                  d={barPath(i * slot + BAR_GAP / 2, slot - BAR_GAP, Math.max(h, 1.5))}
                  className={hover === i ? 'bar bar-active' : 'bar'}
                />
              )}
            </g>
          )
        })}
        <line x1={0} x2={width} y1={HEIGHT - 0.5} y2={HEIGHT - 0.5} className="baseline" />
      </svg>
      <div className="chart-axis">
        <span>{label(daily[0].day)}</span>
        <span>{label(daily[daily.length - 1].day)}</span>
      </div>
      <details className="table-view">
        <summary>Show as table</summary>
        <table>
          <thead>
            <tr>
              <th>Day</th>
              <th>Spent</th>
            </tr>
          </thead>
          <tbody>
            {daily
              .filter((d) => d.expense_paise > 0)
              .map((d) => (
                <tr key={d.day}>
                  <td>{label(d.day)}</td>
                  <td>{formatINR(d.expense_paise)}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </details>
    </figure>
  )
}
