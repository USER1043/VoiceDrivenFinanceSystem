export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  // Same origin in production (Cloudflare Access cookie is sent automatically);
  // proxied to the API by Vite in development.
  const response = await fetch(`/api${path}`, { credentials: 'same-origin' })
  if (!response.ok) {
    throw new ApiError(response.status, `${response.status} ${response.statusText}`)
  }
  return (await response.json()) as T
}

export interface Me {
  email: string
  timezone: string
}
