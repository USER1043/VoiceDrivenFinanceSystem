import { useEffect } from 'react'
import type { BudgetAlert } from '../api'
import { dismissAlerts, useAlerts } from '../alerts'

/** Status colour never stands alone: icon and words carry the same meaning. */
export function AlertList({ alerts }: { alerts: BudgetAlert[] }) {
  return (
    <ul className="alerts">
      {alerts.map((a) => {
        const tone = a.level === 'over' ? 'critical' : 'warning'
        return (
          <li key={a.category_id} className={`status ${tone}`}>
            <span aria-hidden="true" className="status-icon">
              {a.level === 'over' ? '✕' : '!'}
            </span>
            {a.message}
          </li>
        )
      })}
    </ul>
  )
}

export default function AlertToast() {
  const alerts = useAlerts()
  useEffect(() => {
    if (!alerts.length) return
    const timer = window.setTimeout(dismissAlerts, 10_000)
    return () => window.clearTimeout(timer)
  }, [alerts])
  if (!alerts.length) return null
  return (
    <div className="toast" role="status">
      <AlertList alerts={alerts} />
      <button type="button" className="secondary" aria-label="Dismiss" onClick={dismissAlerts}>
        ✕
      </button>
    </div>
  )
}
