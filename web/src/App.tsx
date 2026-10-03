import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { BrowserRouter, NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { ApiError, api, type Me, type Transaction } from './api'
import TransactionForm from './components/TransactionForm'
import VoiceSheet from './components/VoiceSheet'
import { currentMonth } from './dates'
import Login from './Login'
import Budgets from './pages/Budgets'
import ResetPassword from './ResetPassword'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import Transactions from './pages/Transactions'

type Editing = { transaction?: Transaction } | null

function Shell({ me }: { me: Me }) {
  const [month, setMonth] = useState(currentMonth())
  const [editing, setEditing] = useState<Editing>(null)
  const [voice, setVoice] = useState(false)
  const edit = (transaction: Transaction) => setEditing({ transaction })

  return (
    <>
      <main className="shell">
        <Routes>
          <Route path="/" element={<Dashboard month={month} setMonth={setMonth} onEdit={edit} />} />
          <Route path="/transactions" element={<Transactions month={month} setMonth={setMonth} onEdit={edit} />} />
          <Route path="/budgets" element={<Budgets />} />
          <Route path="/settings" element={<Settings me={me} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <div className="fabs">
        <button type="button" className="fab-small" aria-label="Add transaction manually" onClick={() => setEditing({})}>
          +
        </button>
        <button type="button" className="fab" aria-label="Speak a transaction" onClick={() => setVoice(true)}>
          🎙
        </button>
      </div>

      <nav className="tabbar" aria-label="Main">
        <NavLink to="/" end>
          Home
        </NavLink>
        <NavLink to="/transactions">Transactions</NavLink>
        <NavLink to="/budgets">Budgets</NavLink>
        <NavLink to="/settings">Settings</NavLink>
      </nav>

      {voice && <VoiceSheet onClose={() => setVoice(false)} />}
      {editing && <TransactionForm transaction={editing.transaction} onClose={() => setEditing(null)} />}
    </>
  )
}

export default function App() {
  if (window.location.pathname === '/reset') return <ResetPassword />
  return <Authenticated />
}

function Authenticated() {
  const me = useQuery({
    queryKey: ['me'],
    queryFn: () => api.get<Me>('/me'),
    retry: (count, error) => !(error instanceof ApiError && error.status === 401) && count < 2,
  })
  const needsLogin = me.error instanceof ApiError && me.error.status === 401

  if (me.isSuccess) {
    return (
      <BrowserRouter>
        <Shell me={me.data} />
      </BrowserRouter>
    )
  }

  return (
    <main className="shell">
      <header className="brand">
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
    </main>
  )
}
