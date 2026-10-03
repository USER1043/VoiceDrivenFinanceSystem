import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  api,
  type Account,
  type Budget,
  type Category,
  type Summary,
  type Transaction,
  type TransactionInput,
  type TransactionPage,
  type TransactionSaved,
} from './api'
import { showAlerts } from './alerts'

export const keys = {
  accounts: ['accounts'] as const,
  categories: ['categories'] as const,
  budgets: ['budgets'] as const,
  summary: (month: string) => ['summary', month] as const,
  transactions: (params: string) => ['transactions', params] as const,
}

export const useAccounts = () =>
  useQuery({ queryKey: keys.accounts, queryFn: () => api.get<Account[]>('/accounts') })

export const useCategories = () =>
  useQuery({ queryKey: keys.categories, queryFn: () => api.get<Category[]>('/categories') })

export const useBudgets = () =>
  useQuery({ queryKey: keys.budgets, queryFn: () => api.get<Budget[]>('/budgets') })

export const useSummary = (month: string) =>
  useQuery({ queryKey: keys.summary(month), queryFn: () => api.get<Summary>(`/summary?month=${month}`) })

export interface TransactionFilters {
  month?: string
  category_id?: number
  q?: string
  limit?: number
}

export function useTransactions(filters: TransactionFilters) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const qs = params.toString()
  return useQuery({
    queryKey: keys.transactions(qs),
    queryFn: () => api.get<TransactionPage>(`/transactions?${qs}`),
  })
}

/** Anything that changes money data refreshes every view of it. */
function useInvalidateMoney() {
  const client = useQueryClient()
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: ['transactions'] }),
      client.invalidateQueries({ queryKey: ['summary'] }),
    ])
}

export function useSaveTransaction() {
  const invalidate = useInvalidateMoney()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: TransactionInput }) =>
      id === undefined
        ? api.post<TransactionSaved>('/transactions', data)
        : api.patch<Transaction>(`/transactions/${id}`, data),
    onSuccess: (saved) => {
      if ('alerts' in saved) showAlerts((saved as TransactionSaved).alerts)
      return invalidate()
    },
  })
}

export function useDeleteTransaction() {
  const invalidate = useInvalidateMoney()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/transactions/${id}`),
    onSuccess: invalidate,
  })
}

export function useSetBudget() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ categoryId, amount }: { categoryId: number; amount: number | null }) =>
      amount === null
        ? api.delete(`/budgets/${categoryId}`)
        : api.put(`/budgets/${categoryId}`, { amount_paise: amount }),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.budgets }),
        client.invalidateQueries({ queryKey: ['summary'] }),
      ]),
  })
}

export function useSaveAccount() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: Partial<Account> }) =>
      id === undefined ? api.post<Account>('/accounts', data) : api.patch<Account>(`/accounts/${id}`, data),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.accounts }),
  })
}

export function useSaveCategory() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: Partial<Category> }) =>
      id === undefined
        ? api.post<Category>('/categories', data)
        : api.patch<Category>(`/categories/${id}`, data),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.categories }),
        client.invalidateQueries({ queryKey: ['summary'] }),
      ]),
  })
}

/** Category display helpers: "Food › Groceries", grouped options for selects. */
export function categoryLabel(categories: Category[] | undefined, id: number | null): string {
  if (id === null) return 'Uncategorised'
  const byId = new Map(categories?.map((c) => [c.id, c]))
  const category = byId.get(id)
  if (!category) return '…'
  const parent = category.parent_id === null ? undefined : byId.get(category.parent_id)
  return parent ? `${parent.name} › ${category.name}` : category.name
}

export function groupedCategories(categories: Category[], kind: Category['kind'], includeId?: number | null) {
  const visible = categories.filter((c) => c.kind === kind && (!c.archived || c.id === includeId))
  const parents = visible.filter((c) => c.parent_id === null)
  return parents.map((parent) => ({
    parent,
    children: visible.filter((c) => c.parent_id === parent.id),
  }))
}
