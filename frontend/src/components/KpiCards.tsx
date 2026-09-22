// ─── KPI Cards: 4-column metric cards matching Figma wireframe ───────────────
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { KpiResponse } from '../types'

interface KpiCardsProps {
  data: KpiResponse | null
  isLoading: boolean
}

function DeltaBadge({ pct }: { pct: number | null }) {
  if (pct === null) return null
  const isPositive = pct > 0
  const isNeutral = pct === 0
  const abs = Math.abs(pct)

  if (isNeutral) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-700/60 text-gray-400">
        <Minus size={10} />0%
      </span>
    )
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
        isPositive
          ? 'bg-severity-criticalBg text-severity-critical'
          : 'bg-severity-positiveBg text-severity-positive'
      }`}
    >
      {isPositive ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
      {isPositive ? '+' : '-'}{abs}%
    </span>
  )
}

function KpiCard({
  label,
  value,
  unit,
  delta_pct,
  subtext,
  accentColor,
  isLoading,
}: {
  label: string
  value: number | string
  unit?: string
  delta_pct: number | null
  subtext: string
  accentColor: string
  isLoading: boolean
}) {
  return (
    <div className="flex flex-col gap-3 p-5 rounded-xl bg-surface border border-surface-border hover:border-surface-borderLight transition-colors">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</span>
        <DeltaBadge pct={delta_pct} />
      </div>

      <div className="flex items-end gap-1">
        {isLoading ? (
          <div className="h-9 w-24 bg-surface-hover rounded-lg animate-pulse" />
        ) : (
          <>
            <span className={`text-4xl font-bold leading-none tabular-nums ${accentColor}`}>
              {typeof value === 'number' ? value.toLocaleString() : value}
            </span>
            {unit && <span className="text-gray-500 text-lg mb-0.5">{unit}</span>}
          </>
        )}
      </div>

      <div className="text-xs text-gray-500">{subtext}</div>
    </div>
  )
}

export function KpiCards({ data, isLoading }: KpiCardsProps) {
  const cards = [
    {
      label: 'Total Feedback Processed',
      value: data?.total_feedback.value ?? 0,
      delta_pct: data?.total_feedback.delta_pct ?? null,
      subtext: data?.total_feedback.subtext ?? 'vs previous period',
      accentColor: 'text-white',
    },
    {
      label: 'Bugs Reported',
      value: data?.bugs_reported.value ?? 0,
      delta_pct: data?.bugs_reported.delta_pct ?? null,
      subtext: data?.bugs_reported.subtext ?? 'spike',
      accentColor: 'text-severity-critical',
    },
    {
      label: 'Negative Sentiment Rate',
      value: `${data?.negative_rate.value ?? 0}%`,
      delta_pct: data?.negative_rate.delta_pct ?? null,
      subtext: data?.negative_rate.subtext ?? 'vs baseline',
      accentColor: 'text-severity-high',
    },
    {
      label: 'Average Urgency Score',
      value: data?.avg_urgency.value ?? 0,
      unit: '/ 5',
      delta_pct: data?.avg_urgency.delta_pct ?? null,
      subtext: data?.avg_urgency.subtext ?? '/ 5 vs baseline',
      accentColor: 'text-brand-primary',
    },
  ]

  return (
    <div className="grid grid-cols-4 gap-4">
      {cards.map((c) => (
        <KpiCard key={c.label} {...c} isLoading={isLoading} />
      ))}
    </div>
  )
}
