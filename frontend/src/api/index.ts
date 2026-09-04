/* Domain API modules — every backend call the frontend makes. */

import { get, post, postForm, qs } from './client'
import type {
  AgentRunResponse, ChatResponse, HealthResponse,
} from '../types/api'

/* ---- chat (Ask BIS) ---- */
export const chatApi = {
  send: (message: string, conversationId: string, language: string) =>
    post<ChatResponse>('/chat', { message, conversation_id: conversationId, language }, 300000),
}

/* ---- agent ---- */
export const agentApi = {
  run: (message: string, conversationId: string, language: string) =>
    post<AgentRunResponse>('/agent/run', { message, conversation_id: conversationId, language }, 300000),
}

/* ---- health ---- */
export const healthApi = {
  check: () => get<HealthResponse>('/health', 15000),
}

/* ---- standards ---- */
export const standardsApi = {
  detail: (isNumber: string) => get<any>(`/standards/${encodeURIComponent(isNumber)}`),
  qco: (isNumber: string) => get<any>(`/qco/${encodeURIComponent(isNumber)}`),
  scheme: (isNumber: string) => get<any>(`/schemes/${encodeURIComponent(isNumber)}`),
  tests: (isNumber: string) => get<any>(`/tests/${encodeURIComponent(isNumber)}`),
  labs: (isNumber: string) => get<any>(`/labs/${encodeURIComponent(isNumber)}`),
  search: (q: string, limit = 12) => get<any>(`/fe/standards/search${qs({ q, limit })}`),
  evidence: (documentId: string) => get<any>(`/evidence/${encodeURIComponent(documentId)}`),
}

/* ---- products ---- */
export const productsApi = {
  search: (q: string, limit = 12) => get<any>(`/fe/products/search${qs({ q, limit })}`),
  detail: (productId: string) => get<any>(`/fe/products/${encodeURIComponent(productId)}`),
}

/* ---- labs & offices ---- */
export const labsApi = {
  browse: (filters: { state?: string; city?: string; q?: string; limit?: number }) =>
    get<any>(`/fe/labs${qs(filters)}`),
  detail: (labId: string) => get<any>(`/fe/labs/${encodeURIComponent(labId)}`),
}

/* ---- hallmarking ---- */
export const hallmarkApi = {
  centres: (filters: { state?: string; city?: string; q?: string; status?: string; limit?: number }) =>
    get<any>(`/fe/hallmarking/centres${qs(filters)}`),
}

/* ---- browse (QCO / schemes / manuals) ---- */
export const browseApi = {
  qcos: (q = '') => get<any>(`/fe/qcos${qs({ q })}`),
  schemes: () => get<any>('/fe/schemes'),
  manuals: (q = '') => get<any>(`/fe/manuals${qs({ q })}`),
}

/* ---- evidence search ---- */
export const searchApi = {
  evidence: (query: string, topK = 10) =>
    post<any>('/search', { query, top_k: topK }, 300000),
}

/* ---- compliance (Phase 6) ---- */
export const complianceApi = {
  createAudit: (productText: string) =>
    post<any>('/compliance/audit', { product_text: productText }, 120000),
  upload: (auditId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return postForm<any>(`/compliance/audit/${auditId}/upload`, form, 120000)
  },
  process: (auditId: string) =>
    post<any>(`/compliance/audit/${auditId}/process`, { document_ids: [] }, 300000),
  analyze: (auditId: string) =>
    post<any>(`/compliance/audit/${auditId}/analyze`, undefined, 300000),
  result: (auditId: string) => get<any>(`/compliance/audit/${auditId}/result`),
  report: (auditId: string, fmt: 'json' | 'markdown' = 'json') =>
    get<any>(`/compliance/audit/${auditId}/report${qs({ fmt })}`),
  reportMarkdown: async (auditId: string) => {
    const res = await fetch(`/api/compliance/audit/${auditId}/report?fmt=markdown`)
    if (!res.ok) throw new Error('report not available')
    return res.text()
  },
  recheck: (auditId: string) =>
    post<any>(`/compliance/audit/${auditId}/recheck`, undefined, 300000),
  audit: (auditId: string) => get<any>(`/compliance/audit/${auditId}`),
  audits: () => get<any>('/compliance/audits'),
}
