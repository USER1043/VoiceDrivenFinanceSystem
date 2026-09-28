import { useQuery } from '@tanstack/react-query'
import { apiGet, type Me } from './api'

export default function App() {
  const me = useQuery({ queryKey: ['me'], queryFn: () => apiGet<Me>('/me') })

  return (
    <main className="shell">
      <header>
        <h1>VoxFin</h1>
        <p className="muted">Voice-first personal finance</p>
      </header>

      <section className="card">
        {me.isPending && <p className="muted">Connecting…</p>}
        {me.isError && <p className="error">Can't reach the API: {me.error.message}</p>}
        {me.isSuccess && (
          <p>
            Signed in as <strong>{me.data.email}</strong>
          </p>
        )}
      </section>

      <p className="muted small">
        M0 foundation. Transactions, budgets and voice entry arrive in M1–M2.
      </p>
    </main>
  )
}
