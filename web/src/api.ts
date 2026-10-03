export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type Detail = string | { msg: string; loc?: (string | number)[] }[]

function describe(detail: Detail | undefined, fallback: string): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    // FastAPI validation errors: [{loc: ["body", "amount_paise"], msg: "..."}]
    return detail.map((d) => `${d.loc?.slice(-1)[0] ?? 'value'}: ${d.msg}`).join('; ')
  }
  return fallback
}

// Same origin in production (the session cookie is sent automatically);
// proxied to the API by Vite in development.
async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: 'same-origin',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      message = describe(((await response.json()) as { detail?: Detail }).detail, message)
    } catch {
      // not JSON; keep the status text
    }
    throw new ApiError(response.status, message)
  }
  return (response.status === 204 ? undefined : await response.json()) as T
}

async function upload<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`/api${path}`, { method: 'POST', credentials: 'same-origin', body: form })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      message = describe(((await response.json()) as { detail?: Detail }).detail, message)
    } catch {
      // not JSON
    }
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

export const api = {
  upload,
  get: <T>(path: string) => request<T>('GET', path),
  post: <T = void>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T = void>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T = void>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: (path: string) => request<void>('DELETE', path),
}

export interface Me {
  email: string
  name: string | null
  timezone: string
  is_admin: boolean
  has_password: boolean
  has_google: boolean
}

export interface AuthOptions {
  signup: boolean
  google: boolean
}

export interface AdminUserRow {
  id: number
  email: string
  name: string | null
  is_admin: boolean
  disabled: boolean
  has_password: boolean
  has_google: boolean
  created_at: string
  last_seen_at: string | null
  transactions: number
  last_transaction_at: string | null
  commands_last_30_days: number
}

export type AccountKind = 'upi' | 'cash' | 'card' | 'bank'
export type Kind = 'expense' | 'income'

export interface Account {
  id: number
  name: string
  kind: AccountKind
  is_default: boolean
  archived: boolean
}

export interface Category {
  id: number
  name: string
  kind: Kind
  parent_id: number | null
  aliases: string[]
  archived: boolean
}

export interface Transaction {
  id: number
  kind: Kind
  amount_paise: number
  occurred_at: string
  account_id: number
  category_id: number | null
  merchant: string | null
  note: string | null
  source: 'voice' | 'text' | 'manual' | 'import'
}

export type TransactionInput = Omit<Transaction, 'id' | 'source'>

export interface TransactionPage {
  items: Transaction[]
  total: number
}

export interface Budget {
  category_id: number
  amount_paise: number
}

export interface Summary {
  month: string
  income_paise: number
  expense_paise: number
  previous_expense_paise: number
  by_category: { category_id: number | null; name: string; spent_paise: number }[]
  budgets: { category_id: number; name: string; amount_paise: number; spent_paise: number }[]
  daily: { day: string; expense_paise: number }[]
}

export interface VoiceStatus {
  server_stt: boolean
  llm: string[]
}

export interface TransactionDraft {
  kind: Kind
  amount_paise: number
  category_id: number | null
  account_id: number
  occurred_at: string
  merchant: string | null
  note: string | null
}

export interface BudgetDraft {
  category_id: number
  amount_paise: number
}

export type PendingAction =
  | { id: number; tool: 'add_transaction'; data: TransactionDraft; expires_at: string }
  | { id: number; tool: 'set_budget'; data: BudgetDraft; expires_at: string }

export interface BudgetAlert {
  category_id: number
  name: string
  level: 'warning' | 'over'
  spent_paise: number
  amount_paise: number
  message: string
}

export interface TransactionSaved extends Transaction {
  alerts: BudgetAlert[]
}

export interface AnswerItem {
  label: string
  amount_paise: number
  limit_paise: number | null
}

export interface CommandOut {
  status: 'proposal' | 'answer' | 'clarify' | 'unsupported'
  transcript: string
  message: string
  parser: string
  action: PendingAction | null
  answer: { total_paise: number | null; items: AnswerItem[] } | null
}

export interface ConfirmOut {
  tool: 'add_transaction' | 'set_budget'
  message: string
  transaction: Transaction | null
  budget: Budget | null
  alerts: BudgetAlert[]
}
