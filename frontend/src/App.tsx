// ─── App.tsx: Root component, orchestrates all data fetching ─────────────────
import { useState, useEffect, useCallback } from 'react'
import { api } from './api'
import { Navbar } from './components/Navbar'
import { KpiCards } from './components/KpiCards'
import { AnalyticsCharts } from './components/AnalyticsCharts'
import { AnomalyAlerts } from './components/AnomalyAlerts'
import { FeedbackTable } from './components/FeedbackTable'
import type { KpiResponse, ChartsResponse, AnomaliesResponse, MetadataResponse, TimeWindow } from './types'
import './App.css'

const DEFAULT_WINDOW: TimeWindow = { label: 'Last 24 Hours', hours: 24 }

export default function App() {
  const [metadata, setMetadata] = useState<MetadataResponse | null>(null)
  const [kpis, setKpis] = useState<KpiResponse | null>(null)
  const [charts, setCharts] = useState<ChartsResponse | null>(null)
  const [anomalies, setAnomalies] = useState<AnomaliesResponse | null>(null)

  const [selectedWindow, setSelectedWindow] = useState<TimeWindow>(DEFAULT_WINDOW)

  const [loadingMeta, setLoadingMeta] = useState(true)
  const [loadingKpis, setLoadingKpis] = useState(true)
  const [loadingCharts, setLoadingCharts] = useState(true)
  const [loadingAnomalies, setLoadingAnomalies] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Fetch metadata once
  useEffect(() => {
    setLoadingMeta(true)
    api.metadata()
      .then(setMetadata)
      .catch(() => setMetadata(null))
      .finally(() => setLoadingMeta(false))
  }, [])

  const loadWindowData = useCallback(async (hours: number) => {
    setLoadingKpis(true)
    setLoadingCharts(true)
    try {
      const [k, c] = await Promise.all([api.kpis(hours), api.charts(hours)])
      setKpis(k)
      setCharts(c)
    } catch {
      setKpis(null)
      setCharts(null)
    } finally {
      setLoadingKpis(false)
      setLoadingCharts(false)
    }
  }, [])

  const loadAnomalies = useCallback(async () => {
    setLoadingAnomalies(true)
    try {
      const a = await api.anomalies()
      setAnomalies(a)
    } catch {
      setAnomalies(null)
    } finally {
      setLoadingAnomalies(false)
    }
  }, [])

  // Initial load
  useEffect(() => { loadWindowData(selectedWindow.hours) }, [selectedWindow, loadWindowData])
  useEffect(() => { loadAnomalies() }, [loadAnomalies])

  async function handleRefresh() {
    setIsRefreshing(true)
    await Promise.all([
      loadWindowData(selectedWindow.hours),
      loadAnomalies(),
    ])
    setIsRefreshing(false)
  }

  function handleWindowChange(w: TimeWindow) {
    setSelectedWindow(w)
  }

  const timeWindows = metadata?.time_windows ?? [
    { label: 'Last 24 Hours', hours: 24 },
    { label: 'Last 7 Days', hours: 168 },
  ]

  return (
    <div className="min-h-screen bg-obsidian flex flex-col">
      {/* Navbar */}
      <Navbar
        lastSynced={metadata?.last_synced ?? '…'}
        targetApp={metadata?.target_app ?? 'TriageIQ'}
        selectedWindow={selectedWindow}
        timeWindows={timeWindows}
        onWindowChange={handleWindowChange}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      {/* Main content */}
      <main className="flex-1 w-full max-w-screen-2xl mx-auto px-6 py-6 flex flex-col gap-6">

        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-white">Feedback Intelligence Dashboard</h1>
          <p className="text-xs text-gray-500 mt-1">
            {loadingMeta ? 'Loading…' : (metadata?.subtitle ?? 'Aggregated from App Store, Play Store, Twitter & Support Tickets')}
          </p>
        </div>

        {/* KPI Cards */}
        <KpiCards data={kpis} isLoading={loadingKpis} />

        {/* Divider */}
        <div className="h-px w-full bg-surface-border" />

        {/* Analytics charts */}
        <AnalyticsCharts data={charts} isLoading={loadingCharts} />

        {/* Divider */}
        <div className="h-px w-full bg-surface-border" />

        {/* Anomaly alerts */}
        <AnomalyAlerts
          data={anomalies}
          isLoading={loadingAnomalies}
          onJiraCreated={() => {
            // Refresh anomalies to sync jira_created state
            loadAnomalies()
          }}
        />

        {/* Divider */}
        <div className="h-px w-full bg-surface-border" />

        {/* Feedback table */}
        <FeedbackTable
          categories={metadata?.categories ?? []}
          sentiments={metadata?.sentiments ?? ['Negative', 'Neutral', 'Positive']}
          sources={metadata?.sources ?? []}
        />

        {/* Footer */}
        <footer className="pt-2 pb-4 text-center text-xs text-gray-700">
          TriageIQ · Digital Product Feedback Intelligence · Ideathon 2K26
        </footer>
      </main>
    </div>
  )
}
