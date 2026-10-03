import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { api, type Account, type AccountKind, type Category, type Kind, type Me } from '../api'
import { useAccounts, useCategories, useSaveAccount, useSaveCategory } from '../queries'
import { setSpeakingEnabled, speakingEnabled } from '../voice'

const ACCOUNT_KINDS: AccountKind[] = ['upi', 'cash', 'card', 'bank']

function AccountRow({ account }: { account: Account }) {
  const save = useSaveAccount()
  const [name, setName] = useState(account.name)
  return (
    <li className="settings-row">
      <input aria-label="Account name" value={name} onChange={(e) => setName(e.target.value)} disabled={account.archived} />
      <span className="muted small">{account.kind.toUpperCase()}</span>
      {name.trim() && name !== account.name && (
        <button className="secondary" onClick={() => save.mutate({ id: account.id, data: { name: name.trim() } })}>
          Rename
        </button>
      )}
      {account.is_default ? (
        <span className="badge">Default</span>
      ) : account.archived ? (
        <button className="secondary" onClick={() => save.mutate({ id: account.id, data: { archived: false } })}>
          Restore
        </button>
      ) : (
        <>
          <button className="secondary" onClick={() => save.mutate({ id: account.id, data: { is_default: true } })}>
            Make default
          </button>
          <button className="secondary" onClick={() => save.mutate({ id: account.id, data: { archived: true } })}>
            Archive
          </button>
        </>
      )}
      {save.isError && <p className="error">{save.error.message}</p>}
    </li>
  )
}

function Accounts() {
  const accounts = useAccounts()
  const save = useSaveAccount()
  const [name, setName] = useState('')
  const [kind, setKind] = useState<AccountKind>('bank')

  function add(event: FormEvent) {
    event.preventDefault()
    save.mutate({ data: { name: name.trim(), kind } }, { onSuccess: () => setName('') })
  }

  return (
    <section className="card">
      <h2>Accounts</h2>
      <ul className="settings-list">
        {accounts.data?.map((a) => <AccountRow key={a.id} account={a} />)}
      </ul>
      <form className="settings-row" onSubmit={add}>
        <input placeholder="New account, e.g. HDFC" value={name} onChange={(e) => setName(e.target.value)} />
        <select aria-label="Account type" value={kind} onChange={(e) => setKind(e.target.value as AccountKind)}>
          {ACCOUNT_KINDS.map((k) => (
            <option key={k} value={k}>
              {k.toUpperCase()}
            </option>
          ))}
        </select>
        <button type="submit" className="secondary" disabled={!name.trim() || save.isPending}>
          Add
        </button>
      </form>
      {save.isError && <p className="error">{save.error.message}</p>}
    </section>
  )
}

function CategoryRow({ category, nested }: { category: Category; nested?: boolean }) {
  const save = useSaveCategory()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(category.name)
  const [aliases, setAliases] = useState(category.aliases.join(', '))

  function submit(event: FormEvent) {
    event.preventDefault()
    const list = aliases.split(',').map((a) => a.trim()).filter(Boolean)
    save.mutate({ id: category.id, data: { name: name.trim(), aliases: list } }, { onSuccess: () => setOpen(false) })
  }

  return (
    <li className={nested ? 'nested' : ''}>
      <button type="button" className="row-button" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className={category.archived ? 'muted' : ''}>
          {category.name}
          {category.archived && ' (archived)'}
        </span>
        <span className="muted small truncate">{category.aliases.join(', ')}</span>
      </button>
      {open && (
        <form className="form inline-form" onSubmit={submit}>
          <label className="field">
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="field">
            <span>Words you say for it (comma separated)</span>
            <input value={aliases} onChange={(e) => setAliases(e.target.value)} placeholder="chai, coffee" />
          </label>
          {save.isError && <p className="error">{save.error.message}</p>}
          <div className="field-row">
            <button type="submit" disabled={save.isPending}>
              Save
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => save.mutate({ id: category.id, data: { archived: !category.archived } })}
            >
              {category.archived ? 'Restore' : 'Archive'}
            </button>
          </div>
        </form>
      )}
    </li>
  )
}

function Categories() {
  const categories = useCategories()
  const save = useSaveCategory()
  const [kind, setKind] = useState<Kind>('expense')
  const [name, setName] = useState('')
  const [parentId, setParentId] = useState('')
  const all = categories.data ?? []
  const parents = all.filter((c) => c.kind === kind && c.parent_id === null)

  function add(event: FormEvent) {
    event.preventDefault()
    save.mutate(
      { data: { name: name.trim(), kind, parent_id: parentId ? Number(parentId) : null } },
      { onSuccess: () => setName('') },
    )
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>Categories</h2>
        <div className="segmented small" role="radiogroup" aria-label="Category type">
          {(['expense', 'income'] as const).map((k) => (
            <button key={k} type="button" role="radio" aria-checked={kind === k} className={kind === k ? 'active' : ''} onClick={() => { setKind(k); setParentId('') }}>
              {k === 'expense' ? 'Expense' : 'Income'}
            </button>
          ))}
        </div>
      </div>
      <ul className="settings-list">
        {parents.map((p) => [
          <CategoryRow key={p.id} category={p} />,
          ...all.filter((c) => c.parent_id === p.id).map((c) => <CategoryRow key={c.id} category={c} nested />),
        ])}
      </ul>
      <form className="settings-row" onSubmit={add}>
        <input placeholder="New category" value={name} onChange={(e) => setName(e.target.value)} />
        <select aria-label="Inside" value={parentId} onChange={(e) => setParentId(e.target.value)}>
          <option value="">Top level</option>
          {parents.filter((p) => !p.archived).map((p) => (
            <option key={p.id} value={p.id}>
              Inside {p.name}
            </option>
          ))}
        </select>
        <button type="submit" className="secondary" disabled={!name.trim() || save.isPending}>
          Add
        </button>
      </form>
      {save.isError && <p className="error">{save.error.message}</p>}
    </section>
  )
}

function VoiceSettings() {
  const [speakOn, setSpeakOn] = useState(speakingEnabled)
  return (
    <section className="card">
      <h2>Voice</h2>
      <label className="toggle">
        <input
          type="checkbox"
          checked={speakOn}
          onChange={(e) => {
            setSpeakingEnabled(e.target.checked)
            setSpeakOn(e.target.checked)
          }}
        />
        Read results aloud
      </label>
      <p className="muted small">
        Voice uses Groq speech-to-text when a key is configured on the server, otherwise your browser's own
        speech recognition. Teach it your words under Categories.
      </p>
    </section>
  )
}

export default function Settings({ me }: { me: Me }) {
  const client = useQueryClient()
  const logout = useMutation({
    mutationFn: () => api.post('/auth/logout'),
    onSuccess: () => client.resetQueries(),
  })
  return (
    <>
      <VoiceSettings />
      <Accounts />
      <Categories />
      <section className="card">
        <h2>Data</h2>
        <p className="muted small">Download every transaction as a spreadsheet-friendly CSV.</p>
        <a className="button secondary" href="/api/export/transactions.csv" download>
          Export CSV
        </a>
      </section>
      <section className="card row">
        <p>
          Signed in as <strong>{me.email}</strong>
        </p>
        {me.can_log_out && (
          <button className="secondary" onClick={() => logout.mutate()}>
            Sign out
          </button>
        )}
      </section>
    </>
  )
}
