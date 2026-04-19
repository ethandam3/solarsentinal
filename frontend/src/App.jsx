import React, { useState, useCallback } from 'react'
import Dashboard from './components/Dashboard.jsx'
import AlertFeed from './components/AlertFeed.jsx'
import AboutPage from './components/AboutPage.jsx'
import { useSolarWebSocket } from './hooks/useWebSocket.js'
import { REST_URL } from './config.js'
import axios from 'axios'

export default function App() {
  const [page, setPage]           = useState('home')   // 'home' | 'dashboard'
  const [alerts, setAlerts]       = useState([])
  const [scoreMap, setScoreMap]   = useState({})       // permit_id → latest score
  const [replayStatus, setReplay] = useState('idle')   // idle | running | done

  // Called whenever the WS pushes a new frame (anomaly or healthy score)
  const handleWsMessage = useCallback((msg) => {
    if (msg.type === 'anomaly') {
      setAlerts(prev => [msg, ...prev].slice(0, 200))
    }
    if (msg.type === 'anomaly' || msg.type === 'score') {
      setScoreMap(prev => ({ ...prev, [msg.permit_id]: msg }))
    }
  }, [])

  const { statusLabel, isLive } = useSolarWebSocket(handleWsMessage)

  const startReplay = async () => {
    // Clear previous run's data so judges see a clean slate
    setAlerts([])
    setScoreMap({})
    setReplay('running')
    try {
      await axios.post(`${REST_URL}/replay`, { delay_seconds: 8 })
      setReplay('done')
    } catch (e) {
      console.error('Replay error', e)
      setReplay('idle')
    }
  }

  const resetDashboard = () => {
    setAlerts([])
    setScoreMap({})
    setReplay('idle')
  }

  const anomalyCount = Object.values(scoreMap).filter(s => s?.is_anomaly).length

  return (
    <div className="min-h-screen bg-[#0a0f1e] text-slate-100 flex flex-col">

      {/* ── Header ──────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-slate-700 shrink-0">
        {/* Logo — always goes home */}
        <button
          onClick={() => setPage('home')}
          className="flex items-center hover:opacity-80 transition-opacity"
        >
          <img
            src="/logo.png"
            alt="SolarSentinel"
            className="h-20 w-auto rounded-xl bg-white px-2 py-1"
            onError={e => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex' }}
          />
          {/* Fallback if logo.png missing */}
          <div className="items-center gap-3 hidden">
            <span className="text-3xl">☀️</span>
            <div className="text-left">
              <h1 className="text-xl font-bold tracking-tight">SolarSentinel</h1>
              <p className="text-xs text-slate-400">Real-time Solar Anomaly Detection</p>
            </div>
          </div>
        </button>

        <div className="flex items-center gap-3">
          {/* Page tabs */}
          <nav className="flex bg-slate-800 border border-slate-700 rounded-lg p-1 gap-1">
            <TabBtn active={page === 'home'}      onClick={() => setPage('home')}>
              About
            </TabBtn>
            <TabBtn active={page === 'dashboard'} onClick={() => setPage('dashboard')}>
              Dashboard
              {anomalyCount > 0 && (
                <span className="ml-1.5 bg-red-500 text-white text-xs font-bold
                                 w-4 h-4 rounded-full inline-flex items-center justify-center">
                  {anomalyCount}
                </span>
              )}
            </TabBtn>
          </nav>

          {/* Live indicator — always visible */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium
            ${isLive
              ? 'bg-green-900/60 text-green-300 border border-green-700'
              : 'bg-slate-700 text-slate-400'}`}>
            <span className={`w-2 h-2 rounded-full ${isLive ? 'bg-green-400 animate-pulse' : 'bg-slate-500'}`} />
            {statusLabel}
          </div>

          {/* Replay + Reset buttons — only on dashboard */}
          {page === 'dashboard' && (
            <>
              {(replayStatus === 'done' || Object.keys(scoreMap).length > 0) && (
                <button
                  onClick={resetDashboard}
                  className="px-3 py-2 rounded-lg text-sm font-medium transition-all
                             text-slate-400 border border-slate-600 hover:border-slate-400
                             hover:text-slate-200"
                  title="Clear all data for a fresh replay"
                >
                  ↺ Reset
                </button>
              )}
              <button
                onClick={startReplay}
                disabled={replayStatus === 'running'}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all
                  ${replayStatus === 'running'
                    ? 'bg-yellow-600/30 text-yellow-300 cursor-not-allowed border border-yellow-700 animate-pulse'
                    : replayStatus === 'done'
                    ? 'bg-green-700/30 text-green-300 border border-green-700'
                    : 'bg-amber-500 hover:bg-amber-400 text-slate-900 border border-amber-400'}`}
              >
                {replayStatus === 'running' ? '⏳ Replaying…' :
                 replayStatus === 'done'    ? '✓ Replay Complete' :
                 '▶ Start Replay'}
              </button>
            </>
          )}
        </div>
      </header>

      {/* ── Page body ───────────────────────────────────────────────── */}
      {page === 'home' ? (
        <main className="flex-1 overflow-y-auto">
          <AboutPage onGoToDashboard={() => setPage('dashboard')} />
        </main>
      ) : (
        <main className="flex flex-1 gap-0 overflow-hidden">
          <div className="flex-1 p-6 overflow-y-auto">
            <Dashboard alerts={alerts} scoreMap={scoreMap} />
          </div>
          <aside className="w-96 border-l border-slate-700 overflow-y-auto">
            <AlertFeed alerts={alerts} />
          </aside>
        </main>
      )}

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <footer className="text-center py-2 text-xs text-slate-600 border-t border-slate-800 shrink-0">
        Data: Scripps Institution of Oceanography AWN Station · ZenPower Solar Permit Registry · DataHacks 2026
      </footer>
    </div>
  )
}

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center px-4 py-1.5 rounded-md text-sm font-medium transition-all
        ${active
          ? 'bg-slate-700 text-slate-100 shadow-sm'
          : 'text-slate-400 hover:text-slate-200'}`}
    >
      {children}
    </button>
  )
}
