import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { api, type AuthOptions } from './api'

type Mode = 'signin' | 'signup'

/** Errors from the Google redirect arrive as ?auth_error=...; show once, then tidy the URL. */
function takeRedirectError(): string {
  const params = new URLSearchParams(window.location.search)
  const error = params.get('auth_error') ?? ''
  if (error) {
    params.delete('auth_error')
    const query = params.toString()
    window.history.replaceState(null, '', window.location.pathname + (query ? `?${query}` : ''))
  }
  return error
}

export default function Login() {
  const queryClient = useQueryClient()
  const options = useQuery({ queryKey: ['auth-options'], queryFn: () => api.get<AuthOptions>('/auth/options') })
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [redirectError] = useState(takeRedirectError)

  const submit = useMutation({
    mutationFn: () =>
      mode === 'signin'
        ? api.post('/auth/login', { email, password })
        : api.post('/auth/signup', { email, password, name: name || null }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['me'] }),
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    submit.mutate()
  }

  const canSignUp = options.data?.signup ?? false

  return (
    <section className="card login">
      {canSignUp && (
        <div className="segmented" role="tablist" aria-label="Sign in or create an account">
          {(['signin', 'signup'] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              className={mode === m ? 'active' : ''}
              onClick={() => {
                setMode(m)
                submit.reset()
              }}
            >
              {m === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          ))}
        </div>
      )}

      {options.data?.google && (
        <>
          <a className="button google" href="/api/auth/google/start">
            Continue with Google
          </a>
          <p className="divider muted small">or with email</p>
        </>
      )}

      <form className="form" onSubmit={onSubmit}>
        {mode === 'signup' && (
          <label className="field">
            <span>Name (optional)</span>
            <input autoComplete="name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
          </label>
        )}
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            autoComplete="email"
            autoFocus
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            required
            minLength={mode === 'signup' ? 10 : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {mode === 'signup' && <p className="muted small">At least 10 characters. A few random words works well.</p>}
        <button type="submit" disabled={submit.isPending || !email || !password}>
          {submit.isPending ? 'Please wait…' : mode === 'signin' ? 'Sign in' : 'Create account'}
        </button>
      </form>

      {(submit.error || redirectError) && <p className="error">{submit.error?.message ?? redirectError}</p>}
      {mode === 'signin' && (
        <p className="muted small">Forgot your password? Ask the admin for a reset link.</p>
      )}
    </section>
  )
}
