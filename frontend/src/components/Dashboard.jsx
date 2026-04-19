/**
 * Dashboard.jsx
 * Shows:
 *   - Live kWh timeline chart (expected vs actual, per install)
 *   - Summary stat cards (total installs monitored, alerts fired, avg delta)
 *   - Install grid (one tile per permit, colour-coded by health)
 */

import React, { useState, useEffect, useRef } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import axios from 'axios'
import { REST_URL } from '../config.js'

// Colour palette for install lines
const COLOURS = [
  '#60a5fa','#34d399','#f59e0b','#f87171','#a78bfa',
  '#38bdf8','#4ade80','#fb923c','#e879f9','#94a3b8',
]

// SDG&E blended rate ($/kWh) and San Diego peak sun hours
const ELECTRICITY_RATE  = 0.28
const PEAK_SUN_HOURS    = 5.5
const WINDOWS_PER_HOUR  = 12  // one reading every 5 min

/** Estimate annual revenue loss for an anomalous reading.
 *  Formula: loss_per_5min × 12 × peak_sun_hours × 365 × $/kWh
 */
function annualLossUsd(delta_pct, expected_kwh) {
  if (!expected_kwh || !delta_pct) return 0
  const lossPerWindow = (delta_pct / 100) * expected_kwh
  return lossPerWindow * WINDOWS_PER_HOUR * PEAK_SUN_HOURS * 365 * ELECTRICITY_RATE
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg p-3 text-xs">
      <p className="text-slate-300 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {Number(p.value).toFixed(4)} kWh
        </p>
      ))}
    </div>
  )
}

export default function Dashboard({ alerts, scoreMap = {} }) {
  // Chart data: array of { time, [permit_id]_exp, [permit_id]_actual }
  const [chartData,    setChartData] = useState([])
  const [focusInstall, setFocus]     = useState('ZP-0014')

  // Only re-run when the focused install's own score changes, not every install
  const focusedScore = scoreMap[focusInstall]
  useEffect(() => {
    if (!focusedScore) return
    const time = focusedScore.timestamp?.slice(11, 16) || ''
    setChartData(prev => {
      const last = prev[prev.length - 1]
      if (last?.time === time &&
          last[`${focusInstall}_exp`] === focusedScore.expected_kwh) return prev
      return [...prev.slice(-60), {
        time,
        [`${focusInstall}_exp`]:    focusedScore.expected_kwh,
        [`${focusInstall}_actual`]: focusedScore.actual_kwh,
      }]
    })
  }, [focusedScore, focusInstall])

  // All permit IDs that have been scored, sorted
  const scoredIds   = Object.keys(scoreMap).sort()
  const totalScored = scoredIds.length
  const anomalyIds  = scoredIds.filter(id => scoreMap[id]?.is_anomaly)

  const totalAlerts  = alerts.length
  const worstInstall = alerts.length
    ? alerts.reduce((best, a) => (a.delta_pct > best.delta_pct ? a : best))
    : null

  const estAnnualLoss = worstInstall
    ? annualLossUsd(worstInstall.delta_pct, worstInstall.expected_kwh)
    : 0

  return (
    <div className="space-y-6">

      {/* ── Context bar ──────────────────────────────────────────── */}
      <div className="bg-slate-800/40 border border-slate-700/60 rounded-xl px-5 py-3.5
                      flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-200">Live Solar Output Monitor</p>
          <p className="text-xs text-slate-500 mt-0.5">
            Each panel is scored every 5 minutes against the AI's prediction.
            Green = performing normally · Red = output is unexpectedly low.
          </p>
        </div>
        {totalScored > 0 && (
          <div className="text-right shrink-0 ml-6">
            <p className="text-xs text-slate-500">Last update</p>
            <p className="text-xs font-mono text-slate-400">
              {Object.values(scoreMap)[0]?.timestamp?.slice(11, 19) || '—'}
            </p>
          </div>
        )}
      </div>

      {/* ── Stat cards ───────────────────────────────────────────── */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Installs Monitored"
          value={totalScored || '–'}
          sub={totalScored ? `${anomalyIds.length} flagged` : 'waiting for replay'}
          icon="🔭"
        />
        <StatCard
          label="Anomaly Alerts"
          value={totalAlerts || '–'}
          icon="🚨"
          highlight={totalAlerts > 0}
        />
        <StatCard
          label="Worst Install"
          value={worstInstall?.permit_id || '–'}
          sub={worstInstall ? `${worstInstall.delta_pct?.toFixed(1)}% below expected` : 'none yet'}
          icon="⚠️"
          highlight={!!worstInstall}
        />
        <StatCard
          label="Est. Annual Loss"
          value={estAnnualLoss ? `$${Math.round(estAnnualLoss).toLocaleString()}` : '–'}
          sub={estAnnualLoss ? `at $0.28/kWh · SDG&E rate` : 'no anomaly yet'}
          icon="💸"
          highlight={estAnnualLoss > 0}
        />
      </div>

      {/* ── Install selector ─────────────────────────────────────── */}
      {scoredIds.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">
            Select a panel to inspect
          </h2>
          <div className="flex flex-wrap gap-2">
            {scoredIds.map(id => {
              const s = scoreMap[id]
              return (
                <button
                  key={id}
                  onClick={() => setFocus(id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all
                    ${focusInstall === id
                      ? 'bg-amber-500 text-slate-900 font-bold'
                      : s?.is_anomaly
                      ? 'bg-red-900/40 text-red-300 border border-red-700'
                      : 'bg-green-900/30 text-green-400 border border-green-800'}`}
                >
                  {id}
                  {s?.is_anomaly && <span className="ml-1">🔴</span>}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── kWh Chart ─────────────────────────────────────────────── */}
      <div className="bg-slate-800/60 rounded-xl p-5 border border-slate-700">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="font-semibold text-slate-200">{focusInstall} — Power Output Over Time</h2>
            <p className="text-xs text-slate-500">
              Blue line = what the AI expected · Red dashed = what was actually produced
            </p>
          </div>
          {scoreMap[focusInstall] && (
            <div className={`px-3 py-1.5 rounded-lg text-xs font-semibold text-center leading-snug
              ${scoreMap[focusInstall].is_anomaly
                ? 'bg-red-900/50 text-red-300 border border-red-700'
                : 'bg-green-900/50 text-green-300 border border-green-700'}`}>
              {scoreMap[focusInstall].is_anomaly
                ? <>↓ {scoreMap[focusInstall]?.delta_pct?.toFixed(1)}%<br /><span className="font-normal opacity-80">underperforming</span></>
                : <>✓ On track<br /><span className="font-normal opacity-80">{scoreMap[focusInstall]?.delta_pct?.toFixed(1)}% off</span></>
              }
            </div>
          )}
        </div>

        {chartData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-slate-500 text-sm">
            Waiting for data — press <strong className="text-amber-400 mx-1">▶ Start Replay</strong> to begin
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                tickFormatter={v => v.toFixed(3)}
                label={{ value: 'kWh', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 11 }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <ReferenceLine y={0} stroke="#334155" />
              <Line
                type="monotone"
                dataKey={`${focusInstall}_exp`}
                name="Expected kWh"
                stroke="#60a5fa"
                strokeWidth={2}
                dot={false}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey={`${focusInstall}_actual`}
                name="Actual kWh"
                stroke="#f87171"
                strokeWidth={2}
                dot={false}
                connectNulls
                strokeDasharray="4 2"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── Install grid ──────────────────────────────────────────── */}
      <div>
        <div className="flex items-baseline gap-3 mb-3">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
            All Monitored Rooftop Installs
          </h2>
          {totalScored > 0 && (
            <span className="text-xs text-slate-500">
              {totalScored} online · {anomalyIds.length} need attention
            </span>
          )}
        </div>
        {scoredIds.length === 0 ? (
          <div className="h-24 flex items-center justify-center text-slate-600 text-sm">
            Press <strong className="text-amber-400 mx-1">▶ Start Replay</strong> — panels appear here as data streams in
          </div>
        ) : (
          <div className="grid grid-cols-5 gap-3">
            {scoredIds.map(id => {
              const s = scoreMap[id]
              return (
                <div
                  key={id}
                  onClick={() => setFocus(id)}
                  title={s?.address || id}
                  className={`p-3 rounded-xl border cursor-pointer transition-all
                    ${focusInstall === id ? 'ring-2 ring-amber-500' : ''}
                    ${s?.is_anomaly
                      ? 'bg-red-900/30 border-red-700 shadow-red-900/30 shadow-lg'
                      : 'bg-green-900/20 border-green-800'}`}
                >
                  <p className="text-xs font-mono font-bold text-slate-300">{id}</p>
                  <p className={`text-lg font-bold mt-1 ${s?.is_anomaly ? 'text-red-400' : 'text-green-400'}`}>
                    {s?.is_anomaly ? '🔴' : '🟢'}
                  </p>
                  <p className={`text-xs mt-0.5 ${s?.is_anomaly ? 'text-red-400' : 'text-green-600'}`}>
                    {s?.is_anomaly ? `↓ ${Number(s?.delta_pct || 0).toFixed(1)}%` : 'Normal'}
                  </p>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, sub, icon, highlight }) {
  return (
    <div className={`rounded-xl p-4 border transition-all
      ${highlight
        ? 'bg-amber-900/20 border-amber-700'
        : 'bg-slate-800/60 border-slate-700'}`}>
      <div className="flex justify-between items-start">
        <span className="text-xs text-slate-400 uppercase tracking-wider">{label}</span>
        <span className="text-xl">{icon}</span>
      </div>
      <p className={`text-3xl font-bold mt-2 ${highlight ? 'text-amber-300' : 'text-slate-100'}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  )
}
