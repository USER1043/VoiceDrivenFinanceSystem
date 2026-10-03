import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type AdminUserRow } from '../api'

function ago(iso: string | null): string {
  if (!iso) return 'never'
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days} days ago`
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

function UserRow({ user }: { user: AdminUserRow }) {
  const client = useQueryClient()
  const [link, setLink] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const reset = useMutation({
    mutationFn: () => api.post<{ url: string }>(`/admin/users/${user.id}/reset-link`),
    onSuccess: (out) => {
      setLink(out.url)
      setCopied(false)
    },
  })
  const toggle = useMutation({
    mutationFn: () => api.patch(`/admin/users/${user.id}`, { disabled: !user.disabled }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  async function copy() {
    if (!link) return
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
    } catch {
      setCopied(false) // clipboard blocked; the link is selectable below
    }
  }

  const how = [user.has_password && 'password', user.has_google && 'Google'].filter(Boolean).join(' + ')
  return (
    <li className="admin-user">
      <div className="admin-user-head">
        <span className={user.disabled ? 'muted' : ''}>
          <strong>{user.name || user.email}</strong>
          {user.name && <span className="muted small"> {user.email}</span>}
        </span>
        {user.is_admin ? <span className="badge">Admin</span> : user.disabled && <span className="badge">Disabled</span>}
      </div>
      <p className="muted small">
        Joined {ago(user.created_at)} · seen {ago(user.last_seen_at)} · {plural(user.transactions, 'transaction')}
        {user.last_transaction_at && ` (last ${ago(user.last_transaction_at)})`} ·{' '}
        {plural(user.commands_last_30_days, 'voice/typed command')} in 30 days
        {how && ` · signs in with ${how}`}
      </p>
      {!user.is_admin && (
        <div className="settings-row">
          <button className="secondary" onClick={() => reset.mutate()} disabled={reset.isPending}>
            Reset link
          </button>
          <button className="secondary" onClick={() => toggle.mutate()} disabled={toggle.isPending}>
            {user.disabled ? 'Enable' : 'Disable'}
          </button>
        </div>
      )}
      {link && (
        <div className="reset-link">
          <input readOnly value={link} aria-label="Reset link" onFocus={(e) => e.target.select()} />
          <button className="secondary" onClick={() => void copy()}>
            {copied ? 'Copied' : 'Copy'}
          </button>
          <p className="muted small">Works once, for 24 hours. Send it to them privately.</p>
        </div>
      )}
      {(reset.isError || toggle.isError) && <p className="error">{(reset.error ?? toggle.error)?.message}</p>}
    </li>
  )
}

export default function AdminPanel() {
  const users = useQuery({ queryKey: ['admin-users'], queryFn: () => api.get<AdminUserRow[]>('/admin/users') })
  return (
    <section className="card">
      <h2>People</h2>
      <p className="muted small">
        Only accounts and activity counts are shown here, never anyone's transactions or amounts.
      </p>
      {users.isError && <p className="error">{users.error.message}</p>}
      <ul className="settings-list">{users.data?.map((u) => <UserRow key={u.id} user={u} />)}</ul>
    </section>
  )
}
