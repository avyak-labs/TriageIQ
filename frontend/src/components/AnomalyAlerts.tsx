// ─── Anomaly Alert Cards: Jira-style incident cards matching Figma wireframe ──
import { useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react'
import { api } from '../api'
import type { AnomaliesResponse, IncidentTicket } from '../types'

interface AnomalyAlertsProps {
  data: AnomaliesResponse | null
  isLoading: boolean
  onJiraCreated: (ticketId: string) => void
}

function SeverityBadge({ severity }: { severity: string }) {
  const isCritical = severity === 'Critical'
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${
        isCritical
          ? 'bg-severity-criticalBg text-severity-critical border border-severity-criticalBorder'
          : 'bg-severity-highBg text-severity-high border border-severity-highBorder'
      }`}
      style={
        !isCritical
          ? { borderColor: 'rgba(245, 158, 11, 0.35)' }
          : {}
      }
    >
      {severity}
    </span>
  )
}

function SourceChip({ source, count }: { source: string; count: number }) {
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs text-gray-400 bg-surface-inset border border-surface-border">
      {source}
      <span className="font-semibold text-gray-300">· {count}</span>
    </span>
  )
}

function TicketCard({ ticket, onJiraCreated }: { ticket: IncidentTicket; onJiraCreated: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const [jiraCreated, setJiraCreated] = useState(ticket.jira_created)
  const [creatingJira, setCreatingJira] = useState(false)

  async function handleCreateJira() {
    setCreatingJira(true)
    try {
      await api.createJira(ticket.ticket_id)
      setJiraCreated(true)
      onJiraCreated(ticket.ticket_id)
    } catch {
      // silent fail – UI still shows error state
    } finally {
      setCreatingJira(false)
    }
  }

  const pctText = ticket.pct_above_baseline != null
    ? `(+${ticket.pct_above_baseline}% above baseline)`
    : ''

  return (
    <div className="rounded-xl border border-surface-border bg-surface overflow-hidden">
      {/* Top accent bar for critical severity */}
      {ticket.severity === 'Critical' && (
        <div className="h-0.5 w-full bg-gradient-to-r from-severity-critical/80 to-severity-critical/10" />
      )}

      <div className="p-5">
        <div className="flex gap-4">
          {/* Main content */}
          <div className="flex-1 min-w-0">
            {/* Header row */}
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="text-xs font-mono text-gray-500">{ticket.ticket_id}</span>
              <SeverityBadge severity={ticket.severity} />
              <span className="text-[10px] text-gray-600 uppercase tracking-wider font-medium">AI-Generated Summary</span>
            </div>

            {/* Title */}
            <h3 className="text-lg font-bold text-white leading-snug mb-1">{ticket.title}</h3>

            {/* Impact line */}
            <p className="text-sm text-severity-critical mb-3">
              {ticket.affected_count} users impacted in the last {ticket.window_minutes} minutes {pctText}
            </p>

            {/* Source chips */}
            <div className="flex flex-wrap gap-2 mb-3">
              {ticket.source_counts.map((sc) => (
                <SourceChip key={sc.source} source={sc.source} count={sc.count} />
              ))}
            </div>

            {/* Sample review quotes */}
            {ticket.sample_reviews.slice(0, expanded ? undefined : 2).map((r, i) => (
              <div
                key={i}
                className="flex items-start gap-2 px-4 py-2.5 rounded-lg bg-surface-inset border border-surface-border mb-2"
              >
                <span className="shrink-0 mt-0.5 px-2 py-0.5 rounded text-[10px] text-gray-500 bg-surface-hover border border-surface-border font-medium">
                  {r.source}
                </span>
                <p className="text-xs text-gray-300 italic leading-relaxed">"{r.text}"</p>
              </div>
            ))}

            {ticket.sample_reviews.length > 2 && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 mt-1 transition-colors"
              >
                {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                {expanded ? 'Show less' : `Show ${ticket.sample_reviews.length - 2} more`}
              </button>
            )}
          </div>

          {/* Right action column */}
          <div className="flex flex-col gap-2 shrink-0 w-40">
            {jiraCreated ? (
              <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-severity-positiveBg border border-severity-positive/30 text-severity-positive text-xs font-semibold">
                <CheckCircle2 size={13} />
                {ticket.ticket_id} created
              </div>
            ) : (
              <button
                onClick={handleCreateJira}
                disabled={creatingJira}
                className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-brand-primary hover:bg-brand-hover text-white text-xs font-semibold transition-colors disabled:opacity-60 w-full"
              >
                {creatingJira ? (
                  <span className="animate-pulse">Creating…</span>
                ) : (
                  'Create Jira Ticket'
                )}
              </button>
            )}

            {/* Detail expansion */}
            <details className="group">
              <summary className="flex items-center gap-1 px-3 py-2 rounded-lg border border-surface-border text-xs text-gray-400 hover:text-white hover:border-surface-borderLight cursor-pointer transition-colors list-none">
                <ChevronDown size={11} className="group-open:rotate-180 transition-transform" />
                View Details
              </summary>
              <div className="mt-2 p-3 rounded-lg bg-surface-inset border border-surface-border text-xs text-gray-400 space-y-1.5">
                <div><span className="text-gray-500">Category:</span> <span className="text-gray-300">{ticket.category}</span></div>
                <div><span className="text-gray-500">Avg Urgency:</span> <span className="text-gray-300">{ticket.avg_urgency} / 5</span></div>
                <div><span className="text-gray-500">Window:</span></div>
                <div className="pl-2 text-gray-500 leading-relaxed">
                  {ticket.window_start}<br />→ {ticket.window_end}
                </div>
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>
  )
}

export function AnomalyAlerts({ data, isLoading, onJiraCreated }: AnomalyAlertsProps) {
  const activeCount = data?.active_count ?? 0

  return (
    <section>
      {/* Section header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <AlertTriangle size={16} className="text-severity-critical" />
          <h2 className="text-base font-semibold text-white">Actionable Anomaly Alerts</h2>
          {activeCount > 0 && (
            <span className="flex items-center justify-center min-w-[22px] h-5 px-1.5 rounded-full text-[11px] font-bold bg-severity-criticalBg text-severity-critical border border-severity-criticalBorder">
              {activeCount}
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500">
          {activeCount} active anomal{activeCount === 1 ? 'y' : 'ies'} requiring attention
        </p>
      </div>

      {isLoading && (
        <div className="flex flex-col gap-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-40 rounded-xl bg-surface border border-surface-border animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && (!data || data.tickets.length === 0) && (
        <div className="flex items-center justify-center py-10 rounded-xl bg-surface border border-surface-border">
          <p className="text-sm text-gray-500">✅ No anomalies detected in the current dataset</p>
        </div>
      )}

      {!isLoading && data && data.tickets.length > 0 && (
        <div className="flex flex-col gap-3">
          {data.tickets.map((t) => (
            <TicketCard key={t.ticket_id} ticket={t} onJiraCreated={onJiraCreated} />
          ))}
        </div>
      )}
    </section>
  )
}
