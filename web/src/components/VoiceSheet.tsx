import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useRef, useState } from 'react'
import { type AnswerItem, api, type CommandOut, type ConfirmOut, type PendingAction, type VoiceStatus } from '../api'
import { fromLocalInput, toLocalInput } from '../dates'
import { formatINR, paiseToInput, parseRupees } from '../money'
import { groupedCategories, useAccounts, useCategories } from '../queries'
import {
  browserRecognitionAvailable,
  type Listening,
  listenInBrowser,
  type Recording,
  recordingAvailable,
  speak,
  startRecording,
} from '../voice'
import { AlertList } from './AlertToast'
import BudgetMeter from './BudgetMeter'
import Modal from './Modal'

type Phase = 'idle' | 'listening' | 'thinking' | 'answered' | 'saved'

const EXAMPLES = [
  'paid 180 for auto',
  'swiggy 450 yesterday',
  'set food budget to 6000',
  'how much did I spend on food this month?',
  'where did my money go last month?',
]

/** The spoken answer, with the numbers behind it: bars, or budget meters. */
function AnswerCard({ message, items }: { message: string; items: AnswerItem[] }) {
  const max = Math.max(...items.map((i) => i.amount_paise), 1)
  return (
    <div className="answer">
      <p className="proposal-message">{message}</p>
      {items.length > 0 && (
        <ul className="cat-bars">
          {items.map((i) =>
            i.limit_paise ? (
              <li key={i.label}>
                <BudgetMeter name={i.label} spent={i.amount_paise} amount={i.limit_paise} />
              </li>
            ) : (
              <li key={i.label} className="cat-link">
                <span className="cat-row">
                  <span>{i.label}</span>
                  <span>{formatINR(i.amount_paise, { whole: true })}</span>
                </span>
                <span className="track">
                  <span className="fill" style={{ width: `${Math.max((i.amount_paise / max) * 100, 1)}%` }} />
                </span>
              </li>
            ),
          )}
        </ul>
      )}
    </div>
  )
}

/** The confirm card: every field the parser filled can be corrected before saving. */
function ProposalCard({
  action,
  message,
  onDone,
  onCancel,
}: {
  action: PendingAction
  message: string
  onDone: (out: ConfirmOut) => void
  onCancel: () => void
}) {
  const categories = useCategories()
  const accounts = useAccounts()
  const isTxn = action.tool === 'add_transaction'
  const [amount, setAmount] = useState(paiseToInput(action.data.amount_paise))
  const [categoryId, setCategoryId] = useState(action.data.category_id?.toString() ?? '')
  const [accountId, setAccountId] = useState(isTxn ? action.data.account_id.toString() : '')
  const [when, setWhen] = useState(() => (isTxn ? toLocalInput(action.data.occurred_at) : ''))
  const paise = parseRupees(amount)

  const confirm = useMutation({
    mutationFn: () => {
      const overrides: Record<string, unknown> = {}
      if (paise !== null && paise !== action.data.amount_paise) overrides.amount_paise = paise
      const category = categoryId ? Number(categoryId) : null
      if (category !== action.data.category_id) overrides.category_id = category
      if (isTxn) {
        if (Number(accountId) !== action.data.account_id) overrides.account_id = Number(accountId)
        if (when !== toLocalInput(action.data.occurred_at)) overrides.occurred_at = fromLocalInput(when)
      }
      return api.post<ConfirmOut>(`/pending-actions/${action.id}/confirm`, overrides)
    },
    onSuccess: onDone,
  })
  const cancel = useMutation({
    mutationFn: () => api.post(`/pending-actions/${action.id}/cancel`),
    onSettled: onCancel,
  })

  const kind = isTxn ? action.data.kind : 'expense'
  const groups = groupedCategories(categories.data ?? [], kind)

  function submit(event: FormEvent) {
    event.preventDefault()
    confirm.mutate()
  }

  return (
    <form className="form proposal" onSubmit={submit}>
      <p className="proposal-message">{message}</p>
      <div className="field-row">
        <label className="field">
          <span>{isTxn && kind === 'income' ? 'Received (₹)' : isTxn ? 'Amount (₹)' : 'Monthly budget (₹)'}</span>
          <input inputMode="decimal" value={amount} aria-invalid={paise === null} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <label className="field">
          <span>Category</span>
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} required={!isTxn}>
            {isTxn && <option value="">Uncategorised</option>}
            {groups.map(({ parent, children }) => [
              <option key={parent.id} value={parent.id}>
                {parent.name}
              </option>,
              ...children.map((c) => (
                <option key={c.id} value={c.id}>
                  {'  '}
                  {c.name}
                </option>
              )),
            ])}
          </select>
        </label>
      </div>
      {isTxn && (
        <div className="field-row">
          <label className="field">
            <span>Account</span>
            <select value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              {accounts.data
                ?.filter((a) => !a.archived)
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="field">
            <span>When</span>
            <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
          </label>
        </div>
      )}
      {isTxn && action.data.merchant && <p className="muted small">At {action.data.merchant}</p>}
      {confirm.isError && <p className="error">{confirm.error.message}</p>}
      <div className="field-row">
        <button type="button" className="secondary" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
          Cancel
        </button>
        <button type="submit" disabled={paise === null || confirm.isPending}>
          {confirm.isPending ? 'Saving…' : 'Confirm'}
        </button>
      </div>
    </form>
  )
}

export default function VoiceSheet({ onClose }: { onClose: () => void }) {
  const client = useQueryClient()
  const status = useQuery({ queryKey: ['voice-status'], queryFn: () => api.get<VoiceStatus>('/voice/status'), staleTime: 300_000 })
  const [phase, setPhase] = useState<Phase>('idle')
  const [interim, setInterim] = useState('')
  const [result, setResult] = useState<CommandOut | null>(null)
  const [saved, setSaved] = useState<ConfirmOut | null>(null)
  const [error, setError] = useState('')
  const [typed, setTyped] = useState('')
  // When the app asked a follow-up, the next utterance is combined with the earlier one.
  const previous = useRef<string | null>(null)
  const recording = useRef<Recording | null>(null)
  const listening = useRef<Listening | null>(null)

  const serverStt = status.data?.server_stt ?? false
  const canSpeak = status.isSuccess && (serverStt ? recordingAvailable() : browserRecognitionAvailable())

  useEffect(
    () => () => {
      recording.current?.cancel()
      listening.current?.cancel()
    },
    [],
  )

  function handle(out: CommandOut) {
    setResult(out)
    setPhase('answered')
    if (out.status === 'clarify') {
      previous.current = [previous.current, out.transcript].filter(Boolean).join(' ')
    } else {
      previous.current = null
    }
    speak(out.message)
  }

  function fail(message: string) {
    setError(message)
    setPhase('idle')
  }

  async function sendText(text: string, via: 'voice' | 'text' = 'text') {
    if (!text.trim()) {
      fail("I didn't catch that. Try again or type it.")
      return
    }
    setPhase('thinking')
    try {
      handle(await api.post<CommandOut>('/commands', { text, previous: previous.current, via }))
    } catch (e) {
      fail((e as Error).message)
    }
  }

  async function sendAudio(blob: Blob, filename: string) {
    setPhase('thinking')
    const form = new FormData()
    form.append('audio', blob, filename)
    if (previous.current) form.append('previous', previous.current)
    try {
      handle(await api.upload<CommandOut>('/voice', form))
    } catch (e) {
      fail((e as Error).message)
    }
  }

  async function stopListening() {
    if (recording.current) {
      const current = recording.current
      recording.current = null
      const { blob, filename } = await current.stop()
      await sendAudio(blob, filename)
    } else {
      listening.current?.stop()
    }
  }

  async function startListening() {
    setError('')
    setInterim('')
    setResult(null)
    window.speechSynthesis?.cancel()
    try {
      if (serverStt) {
        recording.current = await startRecording(() => void stopListening())
      } else {
        listening.current = listenInBrowser({
          onInterim: setInterim,
          onFinal: (text) => {
            listening.current = null
            setInterim(text)
            void sendText(text, 'voice')
          },
          onError: (message) => {
            listening.current = null
            fail(message)
          },
        })
      }
      setPhase('listening')
    } catch (e) {
      const denied = e instanceof DOMException && e.name === 'NotAllowedError'
      fail(denied ? 'Microphone permission was denied. You can type instead.' : (e as Error).message)
    }
  }

  function submitTyped(event: FormEvent) {
    event.preventDefault()
    const text = typed
    setTyped('')
    setInterim(text)
    void sendText(text)
  }

  async function undo() {
    if (!saved?.transaction) return
    await api.delete(`/transactions/${saved.transaction.id}`)
    await client.invalidateQueries()
    setSaved(null)
    setPhase('idle')
    speak('Undone.')
  }

  function onSaved(out: ConfirmOut) {
    setSaved(out)
    setResult(null)
    setPhase('saved')
    speak(out.message)
    void client.invalidateQueries()
  }

  const showMic = phase !== 'thinking' && !(phase === 'answered' && result?.status === 'proposal')

  return (
    <Modal title="Say it" onClose={onClose}>
      <div className="voice">
        {phase === 'answered' && result?.status === 'proposal' && result.action ? (
          <ProposalCard
            action={result.action}
            message={result.message}
            onDone={onSaved}
            onCancel={() => {
              setResult(null)
              setPhase('idle')
            }}
          />
        ) : (
          <>
            {interim && <p className="transcript">“{interim}”</p>}
            {phase === 'thinking' && <p className="muted">Understanding…</p>}
            {phase === 'answered' && result?.status === 'answer' && (
              <AnswerCard message={result.message} items={result.answer?.items ?? []} />
            )}
            {phase === 'answered' && result && result.status !== 'answer' && (
              <p className={result.status === 'clarify' ? 'voice-question' : 'muted'}>{result.message}</p>
            )}
            {phase === 'saved' && saved && (
              <>
                <div className="saved">
                  {/* The spoken message also reads the alerts; they are listed below instead. */}
                  <p>✓ {saved.transaction ? `Saved ${formatINR(saved.transaction.amount_paise)}.` : saved.message}</p>
                  {saved.transaction && (
                    <button type="button" className="secondary" onClick={() => void undo()}>
                      Undo
                    </button>
                  )}
                </div>
                {saved.alerts.length > 0 && <AlertList alerts={saved.alerts} />}
              </>
            )}
            {error && <p className="error">{error}</p>}

            {showMic && canSpeak && (
              <button
                type="button"
                className={phase === 'listening' ? 'mic mic-on' : 'mic'}
                aria-label={phase === 'listening' ? 'Stop and send' : 'Start speaking'}
                onClick={() => void (phase === 'listening' ? stopListening() : startListening())}
              >
                {phase === 'listening' ? '■' : '🎙'}
              </button>
            )}
            {showMic && canSpeak && (
              <p className="muted small center">
                {phase === 'listening'
                  ? serverStt
                    ? 'Listening… tap to send'
                    : 'Listening…'
                  : result?.status === 'clarify'
                    ? 'Tap and answer'
                    : 'Tap and say something like:'}
              </p>
            )}
            {phase === 'idle' && !result && (
              <ul className="examples">
                {EXAMPLES.map((e) => (
                  <li key={e}>“{e}”</li>
                ))}
              </ul>
            )}
            {status.isSuccess && !canSpeak && (
              <p className="muted small">Voice input isn't available in this browser; type instead.</p>
            )}

            {phase !== 'listening' && phase !== 'thinking' && (
              <form className="type-row" onSubmit={submitTyped}>
                <input
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  placeholder={result?.status === 'clarify' ? 'Type the answer' : 'Or type it'}
                  aria-label="Type a command"
                  maxLength={500}
                />
                <button type="submit" disabled={!typed.trim()}>
                  Send
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </Modal>
  )
}
