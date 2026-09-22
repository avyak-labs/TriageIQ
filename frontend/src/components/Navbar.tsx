// ─── Navbar: Top bar matching Figma wireframe ─────────────────────────────────
import { Activity } from 'lucide-react'
import type { TimeWindow } from '../types'

interface NavbarProps {
  lastSynced: string
  targetApp: string
  selectedWindow: TimeWindow
  timeWindows: TimeWindow[]
  onWindowChange: (w: TimeWindow) => void
  onRefresh: () => void
  isRefreshing: boolean
}

export function Navbar({
  lastSynced,
  targetApp,
  selectedWindow,
  timeWindows,
  onWindowChange,
  onRefresh,
  isRefreshing,
}: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 flex items-center justify-between px-6 py-3 border-b border-surface-border bg-surface">
      {/* Left: Logo + app selector */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-brand-primary/20 text-brand-primary">
            <Activity size={15} strokeWidth={2.5} />
          </span>
          <span className="text-sm font-semibold text-white tracking-tight">TriageIQ</span>
        </div>

        <div className="h-4 w-px bg-surface-border" />

        <div className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-inset border border-surface-border text-gray-300 text-xs cursor-default">
          <span>{targetApp}</span>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" className="opacity-50 mt-px">
            <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
          </svg>
        </div>
      </div>

      {/* Right: sync indicator + time picker */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-500">
          Last synced: {lastSynced}
        </span>

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-gray-400 hover:text-white hover:bg-surface-hover border border-surface-border transition-colors disabled:opacity-50"
        >
          <svg
            width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
            className={isRefreshing ? 'animate-spin' : ''}
          >
            <path d="M23 4v6h-6M1 20v-6h6" /><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
          Refresh
        </button>

        {/* Time range selector */}
        <div className="flex items-center rounded-lg border border-surface-border bg-surface-inset p-0.5 gap-0.5">
          {timeWindows.map((w) => (
            <button
              key={w.hours}
              onClick={() => onWindowChange(w)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                selectedWindow.hours === w.hours
                  ? 'bg-brand-primary text-white shadow-sm'
                  : 'text-gray-400 hover:text-white hover:bg-surface-hover'
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>
    </header>
  )
}
