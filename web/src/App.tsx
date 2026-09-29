import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiGet, apiPost, type Me } from './api'
import Login from './Login'

export default function App() {
  const queryClient = useQueryClient()
  const me = useQuery({
    queryKey: ['me'],
    queryFn: () => apiGet<Me>('/me'),
    retry: (count, error) => !(error instanceof ApiError && error.status === 401) && count < 2,
  })
  const logout = useMutation({
    mutationFn: () => apiPost('/auth/logout'),
    onSuccess: () => queryClient.resetQueries({ queryKey: ['me'] }),
  })
  const needsLogin = me.error instanceof ApiError && me.error.status === 401

  return (
    <main className="shell">
      <header>
        <h1>VoxFin</h1>
        <p className="muted">Voice-first personal finance</p>
      </header>

      {me.isPending && (
        <section className="card">
          <p className="muted">Connecting… (the server may take up to a minute to wake up)</p>
        </section>
      )}
      {needsLogin && <Login />}
      {me.isError && !needsLogin && (
        <section className="card">
          <p className="error">Can't reach the API: {me.error.message}</p>
        </section>
      )}
      {me.isSuccess && (
        <section className="card row">
          <p>
            Signed in as <strong>{me.data.email}</strong>
          </p>
          {me.data.can_log_out && (
            <button className="secondary" onClick={() => logout.mutate()}>
              Sign out
            </button>
          )}
        </section>
      )}

      <p className="muted small">
        M0 foundation. Transactions, budgets and voice entry arrive in M1–M2.
      </p>
    </main>
  )
}
