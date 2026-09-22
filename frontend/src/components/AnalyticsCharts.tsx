// ─── Analytics Charts: Volume, Sentiment, Source — matching Figma wireframe ──
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, ReferenceLine,
} from 'recharts'
import type { ChartsResponse } from '../types'

interface AnalyticsChartsProps {
  data: ChartsResponse | null
  isLoading: boolean
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 p-5 rounded-xl bg-surface border border-surface-border">
      <div>
        <p className="text-sm font-semibold text-white">{title}</p>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  )
}

function LoadingChart() {
  return (
    <div className="h-52 w-full bg-surface-hover rounded-lg animate-pulse" />
  )
}

const CUSTOM_TOOLTIP_VOLUME = ({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string }[]; label?: string }) => {
  if (active && payload?.length) {
    return (
      <div className="rounded-lg border border-surface-border bg-surface-card px-3 py-2 shadow-xl text-xs">
        <p className="text-gray-400 mb-1">{label}</p>
        {payload.map((p) =>
          p.name !== 'baseline' ? (
            <p key={p.name} className="text-white font-semibold">{p.value} reports</p>
          ) : (
            <p key={p.name} className="text-gray-500">Avg: {p.value}</p>
          )
        )}
      </div>
    )
  }
  return null
}

const CUSTOM_TOOLTIP_SENTIMENT = ({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) => {
  if (active && payload?.length) {
    const d = payload[0]
    return (
      <div className="rounded-lg border border-surface-border bg-surface-card px-3 py-2 shadow-xl text-xs">
        <p className="text-gray-400 mb-0.5">{d.name}</p>
        <p className="text-white font-semibold">{d.value} reports</p>
      </div>
    )
  }
  return null
}

const SENTIMENT_COLORS: Record<string, string> = {
  Negative: '#EF4444',
  Neutral: '#F59E0B',
  Positive: '#22C55E',
}

function VolumeChart({ data }: { data: ChartsResponse }) {
  const { volume_timeline: rows, spike_annotation: spike } = data

  if (!rows.length) return <div className="h-52 flex items-center justify-center text-gray-500 text-xs">No data for this window</div>

  const spikeTime = spike?.peak_time

  return (
    <div className="h-52">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="spikeGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#EF4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#EF4444" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip content={<CUSTOM_TOOLTIP_VOLUME />} />
          {/* Baseline dashed line */}
          {rows.length > 0 && (
            <ReferenceLine
              y={rows[0].baseline}
              stroke="#4B5563"
              strokeDasharray="4 4"
              label={{ value: 'Avg', fill: '#6B7280', fontSize: 9, position: 'insideTopRight' }}
            />
          )}
          {/* Spike reference vertical marker */}
          {spikeTime && (
            <ReferenceLine
              x={spikeTime}
              stroke="#EF4444"
              strokeDasharray="3 3"
              label={{ value: '⚠️ Spike', fill: '#EF4444', fontSize: 9, position: 'insideTopLeft' }}
            />
          )}
          <Area
            type="monotone"
            dataKey="count"
            stroke="#3B82F6"
            strokeWidth={2}
            fill="url(#volGrad)"
            dot={false}
            activeDot={{ r: 4, fill: '#3B82F6', stroke: '#111827', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
      {spike && (
        <p className="mt-2 text-xs text-severity-critical">
          🔺 {spike.label}
        </p>
      )}
    </div>
  )
}

function SentimentChart({ data }: { data: ChartsResponse }) {
  const rows = data.sentiment_distribution
  if (!rows.length) return <div className="h-52 flex items-center justify-center text-gray-500 text-xs">No data</div>

  return (
    <div className="h-52">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" vertical={false} />
          <XAxis dataKey="sentiment" tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#6B7280', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip content={<CUSTOM_TOOLTIP_SENTIMENT />} />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={48}>
            {rows.map((entry) => (
              <Cell key={entry.sentiment} fill={SENTIMENT_COLORS[entry.sentiment] ?? '#6B7280'} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function SourceChart({ data }: { data: ChartsResponse }) {
  const rows = data.source_breakdown
  if (!rows.length) return <div className="h-52 flex items-center justify-center text-gray-500 text-xs">No data</div>
  const max = Math.max(...rows.map((r) => r.count), 1)

  return (
    <div className="flex flex-col gap-2.5 h-52 justify-center">
      {rows.map((r) => (
        <div key={r.source_key} className="flex items-center gap-3">
          <span className="w-24 text-right text-xs text-gray-400 truncate shrink-0">{r.source}</span>
          <div className="flex-1 h-5 bg-surface-inset rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-brand-primary/70 transition-all"
              style={{ width: `${(r.count / max) * 100}%` }}
            />
          </div>
          <span className="w-8 text-xs text-gray-400 text-right shrink-0">{r.count}</span>
        </div>
      ))}
    </div>
  )
}

export function AnalyticsCharts({ data, isLoading }: AnalyticsChartsProps) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <ChartCard title="Feedback Volume" subtitle="Hourly report count vs rolling average">
        {isLoading || !data ? <LoadingChart /> : <VolumeChart data={data} />}
      </ChartCard>

      <ChartCard title="Sentiment Distribution" subtitle="Breakdown by AI-classified sentiment">
        {isLoading || !data ? <LoadingChart /> : <SentimentChart data={data} />}
      </ChartCard>

      <ChartCard title="Source Breakdown" subtitle="Volume by feedback channel">
        {isLoading || !data ? <LoadingChart /> : <SourceChart data={data} />}
      </ChartCard>
    </div>
  )
}
