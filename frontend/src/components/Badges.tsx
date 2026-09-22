// ─── Category/Sentiment badge pill ───────────────────────────────────────────
const CATEGORY_STYLES: Record<string, string> = {
  Bug: 'bg-severity-criticalBg text-severity-critical border-severity-criticalBorder',
  Complaint: 'bg-severity-highBg text-severity-high',
  'Feature Request': 'bg-blue-900/30 text-blue-400 border-blue-800/40',
  Praise: 'bg-severity-positiveBg text-severity-positive',
  Spam: 'bg-gray-800/60 text-gray-500 border-gray-700/50',
  Uncategorized: 'bg-gray-800/60 text-gray-500 border-gray-700/50',
}
const SENTIMENT_DOT: Record<string, string> = {
  Negative: 'bg-severity-critical',
  Neutral: 'bg-severity-high',
  Positive: 'bg-severity-positive',
}

export function CategoryPill({ category }: { category: string }) {
  const cls = CATEGORY_STYLES[category] ?? CATEGORY_STYLES.Uncategorized
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold border border-transparent ${cls}`}>
      {category}
    </span>
  )
}

export function SentimentDot({ sentiment }: { sentiment: string }) {
  const dot = SENTIMENT_DOT[sentiment] ?? 'bg-gray-500'
  return (
    <span className="flex items-center gap-1.5 text-xs text-gray-300">
      <span className={`w-2 h-2 rounded-full shrink-0 ${dot}`} />
      {sentiment}
    </span>
  )
}
