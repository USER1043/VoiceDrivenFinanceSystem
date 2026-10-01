import { type FormEvent, useState } from 'react'
import type { Kind, Transaction } from '../api'
import { fromLocalInput, toLocalInput } from '../dates'
import { paiseToInput, parseRupees } from '../money'
import {
  groupedCategories,
  useAccounts,
  useCategories,
  useDeleteTransaction,
  useSaveTransaction,
} from '../queries'
import Modal from './Modal'

export default function TransactionForm({
  transaction,
  onClose,
}: {
  transaction?: Transaction
  onClose: () => void
}) {
  const accounts = useAccounts()
  const categories = useCategories()
  const save = useSaveTransaction()
  const remove = useDeleteTransaction()

  const defaultAccount = accounts.data?.find((a) => a.is_default && !a.archived)
  const [kind, setKind] = useState<Kind>(transaction?.kind ?? 'expense')
  const [amount, setAmount] = useState(transaction ? paiseToInput(transaction.amount_paise) : '')
  const [categoryId, setCategoryId] = useState<string>(transaction?.category_id?.toString() ?? '')
  const [accountId, setAccountId] = useState<string>(transaction?.account_id.toString() ?? '')
  const [when, setWhen] = useState(() => toLocalInput(transaction?.occurred_at ?? new Date()))
  const [merchant, setMerchant] = useState(transaction?.merchant ?? '')
  const [note, setNote] = useState(transaction?.note ?? '')
  const [confirmDelete, setConfirmDelete] = useState(false)

  const paise = parseRupees(amount)
  const effectiveAccount = accountId || defaultAccount?.id.toString() || ''
  const groups = groupedCategories(categories.data ?? [], kind, transaction?.category_id)
  const visibleAccounts = accounts.data?.filter((a) => !a.archived || a.id === transaction?.account_id)

  function switchKind(next: Kind) {
    setKind(next)
    setCategoryId('') // categories are per kind
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (paise === null || !effectiveAccount) return
    save.mutate(
      {
        id: transaction?.id,
        data: {
          kind,
          amount_paise: paise,
          occurred_at: fromLocalInput(when),
          account_id: Number(effectiveAccount),
          category_id: categoryId ? Number(categoryId) : null,
          merchant: merchant.trim() || null,
          note: note.trim() || null,
        },
      },
      { onSuccess: onClose },
    )
  }

  return (
    <Modal title={transaction ? 'Edit transaction' : 'Add transaction'} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <div className="segmented" role="radiogroup" aria-label="Type">
          {(['expense', 'income'] as const).map((k) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={kind === k}
              className={kind === k ? 'active' : ''}
              onClick={() => switchKind(k)}
            >
              {k === 'expense' ? 'Expense' : 'Income'}
            </button>
          ))}
        </div>

        <label className="field">
          <span>Amount (₹)</span>
          <input
            className="amount-input"
            inputMode="decimal"
            autoComplete="off"
            placeholder="0"
            autoFocus={!transaction}
            required
            value={amount}
            aria-invalid={amount !== '' && paise === null}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>

        <label className="field">
          <span>Category</span>
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Uncategorised</option>
            {groups.map(({ parent, children }) =>
              children.length ? (
                <optgroup key={parent.id} label={parent.name}>
                  <option value={parent.id}>{parent.name} (general)</option>
                  {children.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </optgroup>
              ) : (
                <option key={parent.id} value={parent.id}>
                  {parent.name}
                </option>
              ),
            )}
          </select>
        </label>

        <div className="field-row">
          <label className="field">
            <span>Account</span>
            <select value={effectiveAccount} onChange={(e) => setAccountId(e.target.value)} required>
              {visibleAccounts?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>When</span>
            <input type="datetime-local" required value={when} onChange={(e) => setWhen(e.target.value)} />
          </label>
        </div>

        <label className="field">
          <span>{kind === 'expense' ? 'Paid to' : 'From'} (optional)</span>
          <input value={merchant} maxLength={120} onChange={(e) => setMerchant(e.target.value)} />
        </label>
        <label className="field">
          <span>Note (optional)</span>
          <input value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />
        </label>

        {save.isError && <p className="error">{save.error.message}</p>}
        {remove.isError && <p className="error">{remove.error.message}</p>}

        <button type="submit" disabled={paise === null || !effectiveAccount || save.isPending}>
          {save.isPending ? 'Saving…' : 'Save'}
        </button>

        {transaction &&
          (confirmDelete ? (
            <button
              type="button"
              className="danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate(transaction.id, { onSuccess: onClose })}
            >
              Really delete?
            </button>
          ) : (
            <button type="button" className="secondary" onClick={() => setConfirmDelete(true)}>
              Delete
            </button>
          ))}
      </form>
    </Modal>
  )
}
