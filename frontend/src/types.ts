// ─── API Response Types matching server.py exactly ───────────────────────────

export interface KpiValue {
  value: number
  delta_pct: number | null
  subtext: string
}

export interface KpiResponse {
  total_feedback: KpiValue
  bugs_reported: KpiValue
  negative_rate: KpiValue
  avg_urgency: KpiValue
}

export interface VolumeDataPoint {
  time: string
  iso_time: string
  count: number
  baseline: number
}

export interface SpikeAnnotation {
  peak_time: string
  peak_count: number
  pct_above_baseline: number
  label: string
}

export interface SentimentDataPoint {
  sentiment: 'Negative' | 'Neutral' | 'Positive'
  count: number
  percentage: number
}

export interface SourceDataPoint {
  source_key: string
  source: string
  count: number
}

export interface ChartsResponse {
  volume_timeline: VolumeDataPoint[]
  spike_annotation: SpikeAnnotation | null
  sentiment_distribution: SentimentDataPoint[]
  source_breakdown: SourceDataPoint[]
}

export interface SourceCount {
  source: string
  count: number
}

export interface SampleReview {
  source: string
  text: string
}

export interface IncidentTicket {
  ticket_id: string
  title: string
  original_title: string
  severity: 'Critical' | 'High'
  affected_count: number
  window_minutes: number
  pct_above_baseline: number | null
  source_counts: SourceCount[]
  sample_reviews: SampleReview[]
  jira_created: boolean
  category: string
  window_start: string
  window_end: string
  avg_urgency: number
}

export interface AnomaliesResponse {
  tickets: IncidentTicket[]
  active_count: number
}

export interface FeedbackItem {
  id: number | null
  priority_score: number
  category: string
  sentiment: 'Positive' | 'Neutral' | 'Negative'
  urgency_score: number
  source: string
  raw_source: string
  clean_text: string
  created_at: string
}

export interface FeedbackResponse {
  items: FeedbackItem[]
  total: number
  page: number
  limit: number
  total_pages: number
}

export interface MetadataResponse {
  app_name: string
  target_app: string
  subtitle: string
  last_synced: string
  time_windows: { label: string; hours: number }[]
  categories: string[]
  sentiments: string[]
  sources: string[]
  total_records: number
}

export type TimeWindow = { label: string; hours: number }
