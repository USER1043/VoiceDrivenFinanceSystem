// Amounts are integer paise end to end. These are the only rupee <-> paise conversions,
// and they work on strings so no float ever touches money.

const MAX_PAISE = 100_000_000_00

/** "180" -> 18000, "1,250.5" -> 125050, "₹ 99.99" -> 9999. Returns null if invalid. */
export function parseRupees(input: string): number | null {
  const cleaned = input.replace(/[₹,\s]/g, '')
  const match = /^(\d+)(?:\.(\d{0,2}))?$/.exec(cleaned)
  if (!match) return null
  const paise = Number(match[1]) * 100 + Number((match[2] ?? '').padEnd(2, '0'))
  return paise > 0 && paise <= MAX_PAISE ? paise : null
}

/** 18000 -> "180", 125050 -> "1250.50": the value to put back in an input box. */
export function paiseToInput(paise: number): string {
  const rupees = Math.trunc(paise / 100)
  const rest = paise % 100
  return rest === 0 ? String(rupees) : `${rupees}.${String(rest).padStart(2, '0')}`
}

const withPaise = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const wholeRupees = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

/** 12345650 -> "₹1,23,456.50"; whole rupees drop the ".00". Indian digit grouping. */
export function formatINR(paise: number, opts: { whole?: boolean } = {}): string {
  const integral = paise % 100 === 0
  if (opts.whole || integral) return wholeRupees.format(Math.round(paise / 100))
  return withPaise.format(paise / 100)
}
