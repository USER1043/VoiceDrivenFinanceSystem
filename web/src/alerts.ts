// Budget alerts shown after a save, from wherever the save happened. A tiny shared store.
import { useSyncExternalStore } from 'react'
import type { BudgetAlert } from './api'

let current: BudgetAlert[] = []
const listeners = new Set<() => void>()

function set(next: BudgetAlert[]) {
  current = next
  listeners.forEach((listener) => listener())
}

export function showAlerts(alerts: BudgetAlert[]) {
  if (alerts.length) set(alerts)
}

export function dismissAlerts() {
  set([])
}

export function useAlerts(): BudgetAlert[] {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => current,
  )
}
