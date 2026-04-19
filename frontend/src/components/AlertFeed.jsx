/**
 * AlertFeed.jsx
 * Smart grouped accordion — one card per unique underperforming panel.
 * Clicking a card expands it to show the full reading history for that install.
 */

import React, { useState, useMemo } from 'react'
import { formatDistanceToNow } from 'date-fns'

/** Rule-based root cause diagnosis using Scripps irradiance + delta */
function diagnose(delta_pct, solar_wm2) {
  const d = Number(delta_pct), s = Number(solar_wm2)
  if (s > 500 && d > 25) return {
    icon: '🔧', label: 'Hardware fault likely',
    detail: 'Strong Scripps irradiance but large output gap — likely inverter or panel failure.',
    color: 'text-red-400', bg: 'bg-red-950/40 border-red-800/50',
  }
  if (s > 300 && d > 15) return {
    icon: '🧹', label: 'Possible soiling or shading',
    detail: 'Good irradiance but unexpected drop — panel surface may need cleaning or a nearby obstruction appeared.',
    color: 'text-orange-400', bg: 'bg-orange-950/40 border-orange-800/50',
  }
  if (s < 150) return {
    icon: '☁️', label: 'Low irradiance — re-check at peak sun',
    detail: 'Scripps sensor shows limited sunlight right now. This flag may be weather-related, not a fault.',
    color: 'text-yellow-400', bg: 'bg-yellow-950/40 border-yellow-800/50',
  }
  return {
    icon: '⚠️', label: 'Performance anomaly',
    detail: 'Output is below the model\'s weather-corrected prediction. Further inspection recommended.',
    color: 'text-orange-400', bg: 'bg-orange-950/40 border-orange-800/50',
  }
}

const ELECTRICITY_RATE = 0.28
const PEAK_SUN_HOURS   = 5.5
const WINDOWS_PER_HOUR = 12

function estAnnualLoss(delta_pct, expected_kwh) {
  if (!expected_kwh || !delta_pct) return 0
  return (delta_pct / 100) * expected_kwh * WINDOWS_PER_HOUR * PEAK_SUN_HOURS * 365 * ELECTRICITY_RATE
}

function timeAgo(ts) {
  try { return formatDistanceToNow(new Date(ts), { addSuffix: true }) }
  catch { return ts?.slice(0, 19) || '—' }
}

export default function AlertFeed({ alerts }) {
  const [expanded, setExpanded] = useState(null)

  // Group alerts by permit_id, sorted worst-first
  const groups = useMemo(() => {
    const map = {}
    for (const alert of alerts) {
      const id = alert.permit_id
      if (!map[id]) map[id] = []
      map[id].push(alert)
    }
    return Object.entries(map)
      .map(([id, readings]) => {
        const worst = readings.reduce((m, r) =>
          Number(r.delta_pct) > Number(m.delta_pct) ? r : m
        )
        return { id, readings, worst, count: readings.length }
      })
      .sort((a, b) => Number(b.worst.delta_pct) - Number(a.worst.delta_pct))
  }, [alerts])

  const toggle = (id) => setExpanded(prev => prev === id ? null : id)

  return (
    <div className="flex flex-col h-full">

      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="px-5 py-4 border-b border-slate-700 sticky top-0 bg-[#0a0f1e] z-10">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-slate-200 flex items-center gap-2">
            🚨 Underperforming Panels
            {groups.length > 0 && (
              <span className="bg-red-600 text-white text-xs font-bold px-2 py-0.5 rounded-full animate-pulse">
                {groups.length}
              </span>
            )}
          </h2>
          <span className="text-xs text-slate-600">live updates</span>
        </div>
        <p className="text-xs text-slate-600 mt-1">
          Fires when output drops 15%+ below the AI's prediction · click to expand history
        </p>
      </div>

      {/* ── Empty state ─────────────────────────────────────────── */}
      {groups.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center text-center px-6 py-12">
          <div className="text-5xl mb-4">📡</div>
          <p className="text-slate-400 text-sm font-medium">All systems normal</p>
          <p className="text-slate-600 text-xs mt-2 leading-relaxed">
            Alerts appear here when a panel produces significantly less power than expected.
          </p>
          <p className="text-slate-600 text-xs mt-3">
            Press <strong className="text-amber-400">▶ Start Replay</strong> to run the demo
          </p>
        </div>
      )}

      {/* ── Grouped accordion list ───────────────────────────────── */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
        {groups.map(({ id, readings, worst, count }) => {
          const isOpen    = expanded === id
          const delta     = Number(worst.delta_pct || 0)
          const loss      = estAnnualLoss(delta, Number(worst.expected_kwh || 0))
          const severity  = delta > 25 ? 'critically' : delta > 15 ? 'significantly' : 'slightly'
          const dx        = diagnose(delta, worst.solar_wm2)

          return (
            <div key={id} className="transition-colors">

              {/* ── Summary card (always visible) ──────────────── */}
              <button
                onClick={() => toggle(id)}
                className="w-full text-left px-5 py-4 hover:bg-slate-800/40
                           transition-colors focus:outline-none"
              >
                {/* Top row */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-base">🔴</span>
                    <div>
                      <p className="font-mono font-bold text-sm text-red-300">{id}</p>
                      <p className="text-xs text-slate-500 truncate max-w-[180px]">
                        {worst.address || 'San Diego, CA'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-sm font-bold px-2 py-0.5 rounded
                      ${delta > 25 ? 'bg-red-900/60 text-red-300'
                        : delta > 15 ? 'bg-orange-900/60 text-orange-300'
                        : 'bg-yellow-900/60 text-yellow-300'}`}>
                      ↓{delta.toFixed(1)}%
                    </span>
                    <span className="text-slate-500 text-sm select-none">
                      {isOpen ? '▲' : '▼'}
                    </span>
                  </div>
                </div>

                {/* Plain-English summary */}
                <p className="text-xs text-slate-500 mt-2 leading-relaxed text-left">
                  Producing <span className="text-red-400 font-medium">{severity} less</span> power
                  than predicted · {count} reading{count !== 1 ? 's' : ''} flagged
                </p>

                {/* Stats row */}
                <div className="mt-2 grid grid-cols-3 gap-2">
                  <MiniStat label="AI predicted"  value={Number(worst.expected_kwh || 0).toFixed(3)} unit="kWh" />
                  <MiniStat label="Actual output" value={Number(worst.actual_kwh   || 0).toFixed(3)} unit="kWh" color="text-red-400" />
                  <MiniStat label="Sunlight"      value={Number(worst.solar_wm2    || 0).toFixed(0)} unit="W/m²" />
                </div>

                {/* Root cause diagnosis */}
                <div className={`mt-2 border rounded-lg px-3 py-2 ${dx.bg}`}>
                  <p className={`text-xs font-semibold ${dx.color}`}>
                    {dx.icon} {dx.label}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{dx.detail}</p>
                </div>

                {/* Dollar loss */}
                {loss > 0 && (
                  <div className="mt-2 bg-red-950/40 border border-red-800/50 rounded-lg
                                  px-3 py-2 flex justify-between items-center">
                    <span className="text-xs text-red-400">Est. annual revenue loss</span>
                    <span className="text-sm font-bold text-red-300">
                      ${Math.round(loss).toLocaleString()}
                      <span className="text-xs font-normal text-red-500">/yr</span>
                    </span>
                  </div>
                )}
              </button>

              {/* ── Expanded history ─────────────────────────────── */}
              {isOpen && (
                <div className="bg-slate-900/60 border-t border-slate-800 px-5 py-3">
                  <DispatchButton permit_id={id} address={worst.address} delta={delta} loss={loss} />
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 mt-3">
                    Reading history · {count} entries
                  </p>
                  <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                    {readings.map((r, i) => {
                      const d = Number(r.delta_pct || 0)
                      return (
                        <div
                          key={i}
                          className="flex items-center justify-between py-1.5 px-2
                                     rounded-lg hover:bg-slate-800/60 transition-colors"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-slate-600 text-xs font-mono shrink-0">
                              {r.timestamp?.slice(11, 16) || '—'}
                            </span>
                            <span className="text-xs text-slate-500 truncate">
                              {Number(r.solar_wm2 || 0).toFixed(0)} W/m²
                            </span>
                          </div>
                          <div className="flex items-center gap-3 shrink-0">
                            <span className="text-xs text-slate-500 font-mono">
                              {Number(r.actual_kwh || 0).toFixed(4)} kWh
                            </span>
                            <span className={`text-xs font-bold w-16 text-right
                              ${d > 25 ? 'text-red-400' : d > 15 ? 'text-orange-400' : 'text-yellow-400'}`}>
                              ↓{d.toFixed(1)}%
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  <p className="text-xs text-slate-600 mt-2 text-right">
                    Latest: {timeAgo(readings[0]?.timestamp)}
                  </p>
                </div>
              )}

            </div>
          )
        })}
      </div>
    </div>
  )
}

function DispatchButton({ permit_id, address, delta, loss }) {
  const [status, setStatus] = useState('idle') // idle | sent

  if (status === 'sent') return (
    <div className="bg-green-900/30 border border-green-700 rounded-xl px-4 py-3">
      <p className="text-xs font-bold text-green-300 mb-2">✅ Technician Alert Sent</p>
      <div className="text-xs text-slate-400 space-y-1 font-mono">
        <p><span className="text-slate-600">To:</span> ZenPower Field Operations</p>
        <p><span className="text-slate-600">Install:</span> {permit_id} · {address || 'San Diego, CA'}</p>
        <p><span className="text-slate-600">Issue:</span> Output ↓{Number(delta).toFixed(1)}% below AI baseline</p>
        <p><span className="text-slate-600">Est. loss:</span> ${Math.round(loss).toLocaleString()}/yr</p>
        <p><span className="text-slate-600">Action:</span> Inspect inverter &amp; panel connections</p>
      </div>
      <button
        onClick={() => setStatus('idle')}
        className="mt-2 text-xs text-slate-600 hover:text-slate-400 transition-colors"
      >
        Dismiss
      </button>
    </div>
  )

  return (
    <button
      onClick={() => setStatus('sent')}
      className="w-full flex items-center justify-center gap-2 bg-blue-600/20
                 hover:bg-blue-600/30 border border-blue-600/50 hover:border-blue-500
                 text-blue-300 text-sm font-semibold rounded-xl px-4 py-2.5
                 transition-all"
    >
      📲 Dispatch Technician
    </button>
  )
}

function MiniStat({ label, value, unit, color = 'text-slate-200' }) {
  return (
    <div className="bg-slate-800/60 rounded-lg px-2 py-1.5">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-xs font-semibold ${color}`}>
        {value} <span className="text-slate-600 font-normal">{unit}</span>
      </p>
    </div>
  )
}
