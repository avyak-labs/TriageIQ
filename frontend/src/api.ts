// ─── Centralised API fetch helpers ───────────────────────────────────────────
import type {
  KpiResponse,
  ChartsResponse,
  AnomaliesResponse,
  FeedbackResponse,
  MetadataResponse,
} from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

export const api = {
  metadata: () => get<MetadataResponse>('/metadata'),
  kpis: (hours: number) => get<KpiResponse>(`/kpis?hours=${hours}`),
  charts: (hours: number) => get<ChartsResponse>(`/charts?hours=${hours}`),
  anomalies: () => get<AnomaliesResponse>('/anomalies'),
  feedback: (params: {
    category?: string
    sentiment?: string
    source?: string
    search?: string
    page?: number
    limit?: number
  }) => {
    const q = new URLSearchParams()
    if (params.category) q.set('category', params.category)
    if (params.sentiment) q.set('sentiment', params.sentiment)
    if (params.source) q.set('source', params.source)
    if (params.search) q.set('search', params.search)
    if (params.page) q.set('page', String(params.page))
    if (params.limit) q.set('limit', String(params.limit))
    return get<FeedbackResponse>(`/feedback?${q}`)
  },
  createJira: (ticketId: string) =>
    post<{ success: boolean; ticket_id: string }>(`/anomalies/${ticketId}/jira`),
  exportCsvUrl: (params: {
    category?: string
    sentiment?: string
    source?: string
    search?: string
  }) => {
    const q = new URLSearchParams()
    if (params.category) q.set('category', params.category)
    if (params.sentiment) q.set('sentiment', params.sentiment)
    if (params.source) q.set('source', params.source)
    if (params.search) q.set('search', params.search)
    return `${BASE}/export-csv?${q}`
  },
}
