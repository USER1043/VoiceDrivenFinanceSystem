import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { api } from './api'

/** Opened from an admin's reset link: /reset#<token>. The token never reaches server logs. */
export default function ResetPassword() {
  const [token] = useState(() => window.location.hash.slice(1))
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const reset = useMutation({
    mutationFn: () => api.post('/auth/reset', { token, new_password: password }),
    // Full reload to the app: the new session cookie is already set.
    onSuccess: () => window.location.replace('/'),
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (password === repeat) reset.mutate()
  }

  return (
    <main className="shell">
      <header className="brand">
        <h1>VoxFin</h1>
        <p className="muted">Choose a new password</p>
      </header>
      {!token ? (
        <section className="card">
          <p className="error">This link is incomplete. Ask the admin for a new one.</p>
        </section>
      ) : (
        <form className="card form" onSubmit={submit}>
          <label className="field">
            <span>New password</span>
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={10}
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Type it again</span>
            <input
              type="password"
              autoComplete="new-password"
              required
              value={repeat}
              aria-invalid={repeat !== '' && repeat !== password}
              onChange={(e) => setRepeat(e.target.value)}
            />
          </label>
          {repeat !== '' && repeat !== password && <p className="error">The passwords don't match.</p>}
          {reset.isError && <p className="error">{reset.error.message}</p>}
          <button type="submit" disabled={reset.isPending || password.length < 10 || password !== repeat}>
            {reset.isPending ? 'Saving…' : 'Save and sign in'}
          </button>
        </form>
      )}
    </main>
  )
}
