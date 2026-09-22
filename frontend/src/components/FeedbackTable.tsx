// ─── Feedback Backlog Table: Prioritized table matching Figma wireframe ───────
import { useState, useEffect, useCallback } from 'react'
import { Search, Download, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '../api'
import { CategoryPill, SentimentDot } from './Badges'
import type { FeedbackResponse } from '../types'

interface FeedbackTableProps {
  categories: string[]
  sentiments: string[]
  sources: string[]
}

const PAGE_SIZE = 25

export function FeedbackTable({ categories, sentiments, sources }: FeedbackTableProps) {
  const [data, setData] = useState<FeedbackResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('')
  const [selectedSentiment, setSelectedSentiment] = useState('')
  const [selectedSource, setSelectedSource] = useState('')
  const [page, setPage] = useState(1)

  // Debounce search input (300ms)
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  // Reset to page 1 when filters change
  useEffect(() => setPage(1), [debouncedSearch, selectedCategory, selectedSentiment, selectedSource])

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await api.feedback({
        category: selectedCategory || undefined,
        sentiment: selectedSentiment || undefined,
        source: selectedSource || undefined,
        search: debouncedSearch || undefined,
        page,
        limit: PAGE_SIZE,
      })
      setData(res)
    } catch {
      setData(null)
    } finally {
      setIsLoading(false)
    }
  }, [selectedCategory, selectedSentiment, selectedSource, debouncedSearch, page])

  useEffect(() => { load() }, [load])

  const exportCsvUrl = api.exportCsvUrl({
    category: selectedCategory || undefined,
    sentiment: selectedSentiment || undefined,
    source: selectedSource || undefined,
    search: debouncedSearch || undefined,
  })

  const friendlySource = (raw: string) =>
    ({
      app_review: 'App Store',
      play_store: 'Play Store',
      tweet: 'Twitter',
      support_ticket: 'Support Ticket',
    }[raw] ?? raw)

  return (
    <section>
      {/* Section header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-white">Prioritized Feedback Backlog</h2>
          {data && (
            <p className="text-xs text-gray-500 mt-0.5">{data.total.toLocaleString()} items · ranked by AI priority score</p>
          )}
        </div>
        <a
          href={exportCsvUrl}
          download="triageiq_prioritized_feedback.csv"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface border border-surface-border text-xs text-gray-400 hover:text-white hover:border-surface-borderLight transition-colors"
        >
          <Download size={12} />
          Export CSV
        </a>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3 mb-4">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Search feedback…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-2 rounded-lg bg-surface border border-surface-border text-xs text-white placeholder-gray-600 focus:outline-none focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/30 transition-colors"
          />
        </div>

        {/* Category dropdown */}
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="px-3 py-2 rounded-lg bg-surface border border-surface-border text-xs text-gray-300 focus:outline-none focus:border-brand-primary hover:border-surface-borderLight transition-colors cursor-pointer"
        >
          <option value="">All Categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        {/* Sentiment dropdown */}
        <select
          value={selectedSentiment}
          onChange={(e) => setSelectedSentiment(e.target.value)}
          className="px-3 py-2 rounded-lg bg-surface border border-surface-border text-xs text-gray-300 focus:outline-none focus:border-brand-primary hover:border-surface-borderLight transition-colors cursor-pointer"
        >
          <option value="">All Sentiments</option>
          {sentiments.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* Source dropdown */}
        <select
          value={selectedSource}
          onChange={(e) => setSelectedSource(e.target.value)}
          className="px-3 py-2 rounded-lg bg-surface border border-surface-border text-xs text-gray-300 focus:outline-none focus:border-brand-primary hover:border-surface-borderLight transition-colors cursor-pointer"
        >
          <option value="">All Sources</option>
          {sources.map((s) => <option key={s} value={s}>{friendlySource(s)}</option>)}
        </select>

        {/* Clear filters */}
        {(selectedCategory || selectedSentiment || selectedSource || debouncedSearch) && (
          <button
            onClick={() => { setSelectedCategory(''); setSelectedSentiment(''); setSelectedSource(''); setSearch('') }}
            className="text-xs text-gray-500 hover:text-gray-300 px-2 py-2 rounded-lg hover:bg-surface-hover transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="rounded-xl border border-surface-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-surface-border bg-surface-card">
                <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider w-20">Priority</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider w-32">Category</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider w-28">Sentiment</th>
                <th className="px-4 py-3 text-center font-medium text-gray-500 uppercase tracking-wider w-20">Urgency</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider w-28">Source</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Feedback</th>
                <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider w-36">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {isLoading && Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="animate-pulse">
                  {Array.from({ length: 7 }).map((__, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-3 bg-surface-hover rounded-full w-3/4" />
                    </td>
                  ))}
                </tr>
              ))}

              {!isLoading && data?.items.map((item, i) => (
                <tr key={item.id ?? i} className="hover:bg-surface-hover/50 transition-colors group">
                  {/* Priority score */}
                  <td className="px-4 py-3 font-bold tabular-nums text-white">
                    {item.priority_score.toFixed(2)}
                  </td>
                  {/* Category */}
                  <td className="px-4 py-3">
                    <CategoryPill category={item.category} />
                  </td>
                  {/* Sentiment */}
                  <td className="px-4 py-3">
                    <SentimentDot sentiment={item.sentiment} />
                  </td>
                  {/* Urgency */}
                  <td className="px-4 py-3 text-center text-gray-300 font-medium">{item.urgency_score}</td>
                  {/* Source */}
                  <td className="px-4 py-3 text-gray-400">{item.source}</td>
                  {/* Feedback text */}
                  <td className="px-4 py-3 text-gray-300 max-w-md">
                    <span className="line-clamp-2 leading-relaxed">{item.clean_text}</span>
                  </td>
                  {/* Date */}
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{item.created_at}</td>
                </tr>
              ))}

              {!isLoading && data?.items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-gray-500">
                    No items match your filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-surface-border bg-surface-card">
            <span className="text-xs text-gray-500">
              Showing {((page - 1) * PAGE_SIZE) + 1}–{Math.min(page * PAGE_SIZE, data.total)} of {data.total.toLocaleString()}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-gray-400 hover:text-white border border-surface-border hover:border-surface-borderLight disabled:opacity-40 transition-colors"
              >
                <ChevronLeft size={12} /> Prev
              </button>
              <span className="text-xs text-gray-500 px-2">
                {page} / {data.total_pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page >= data.total_pages}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-gray-400 hover:text-white border border-surface-border hover:border-surface-borderLight disabled:opacity-40 transition-colors"
              >
                Next <ChevronRight size={12} />
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
