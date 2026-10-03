import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { api } from './api'

export default function Login() {
  const queryClient = useQueryClient()
  const [password, setPassword] = useState('')
  const login = useMutation({
    mutationFn: () => api.post('/auth/login', { password }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['me'] }),
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    login.mutate()
  }

  return (
    <form className="card login" onSubmit={submit}>
      <label htmlFor="password">Password</label>
      <input
        id="password"
        type="password"
        autoComplete="current-password"
        autoFocus
        required
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <button type="submit" disabled={login.isPending || !password}>
        {login.isPending ? 'Signing in…' : 'Sign in'}
      </button>
      {login.isError && <p className="error">{login.error.message}</p>}
    </form>
  )
}
