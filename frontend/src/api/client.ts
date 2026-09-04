/* Centralized API client. The ONLY network layer — every call goes through
   the FastAPI backend via the dev proxy. No DB/LLM direct access, no secrets. */

export const API_BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 120000): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(API_BASE + path, {
      ...init,
      signal: ctrl.signal,
      headers: { ...(init?.headers || {}), ...(init?.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}) },
    })
    if (!res.ok) {
      let detail = ''
      try { const j = await res.json(); detail = j.detail || JSON.stringify(j).slice(0, 180) } catch { /* ignore */ }
      throw new ApiError(detail || `Request failed (${res.status})`, res.status)
    }
    return (await res.json()) as T
  } catch (e: any) {
    if (e.name === 'AbortError') throw new ApiError('The request timed out. Please try again.', 0)
    if (e instanceof ApiError) throw e
    throw new ApiError('BIS Assistant service is temporarily unavailable.', 0)
  } finally {
    clearTimeout(timer)
  }
}

export const get = <T>(path: string, timeoutMs?: number) => request<T>(path, { method: 'GET' }, timeoutMs)
export const post = <T>(path: string, body?: any, timeoutMs?: number) =>
  request<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }, timeoutMs)
export const postForm = <T>(path: string, form: FormData, timeoutMs?: number) =>
  request<T>(path, { method: 'POST', body: form }, timeoutMs)

export function qs(params: Record<string, string | number | undefined | null>): string {
  const u = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') u.set(k, String(v))
  }
  const s = u.toString()
  return s ? `?${s}` : ''
}
