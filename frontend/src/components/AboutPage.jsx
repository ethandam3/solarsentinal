/**
 * AboutPage.jsx
 * Landing / about page — explains SolarSentinel in plain English.
 * Readable by anyone, not just engineers.
 */

import React from 'react'

const HOW_IT_WORKS = [
  {
    icon: '🌤',
    title: 'Real San Diego sunlight data',
    body: 'Every 5 minutes, sensors at the Scripps Institution of Oceanography measure actual solar radiation, temperature, and humidity across the city. That\'s our baseline for what the sky is doing right now.',
  },
  {
    icon: '🤖',
    title: 'AI predicts what each panel should produce',
    body: 'A machine learning model — trained on thousands of real readings — knows that an 8.4 kW south-facing rooftop in Carmel Valley on a sunny August afternoon should generate roughly 0.55 kWh every 5 minutes. If it produces less, something is wrong.',
  },
  {
    icon: '🚨',
    title: 'Live alert the moment a panel underperforms',
    body: 'If actual output drops more than 15% below what the model expects, an alert fires instantly — to this dashboard and to the ZenPower operations team. No more waiting for a homeowner to notice on their power bill.',
  },
]

const WHY_IT_MATTERS = [
  { stat: '$870',   label: 'lost per year',       sub: 'by a silently degraded 8.4 kW system' },
  { stat: '6–12',  label: 'months',               sub: 'before most homeowners notice a problem' },
  { stat: '50',    label: 'installs monitored',   sub: 'across San Diego County in real time' },
  { stat: '<5 s',  label: 'alert latency',        sub: 'from sensor reading to your screen' },
]

const TECH_PILLS = [
  'AWS SageMaker · XGBoost ML',
  'API Gateway WebSockets',
  'AWS Lambda + DynamoDB',
  'Scripps AWN Sensor Network',
  'React + Recharts',
]

export default function AboutPage({ onGoToDashboard }) {
  return (
    <div className="min-h-full bg-[#0a0f1e] text-slate-100">

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="max-w-4xl mx-auto px-8 pt-20 pb-16 text-center">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <img
            src="/logo.png"
            alt="SolarSentinel"
            className="h-28 w-auto rounded-2xl bg-white px-3 py-2 shadow-lg shadow-amber-500/10"
            onError={e => { e.target.style.display = 'none' }}
          />
        </div>

        <div className="inline-flex items-center gap-2 bg-amber-500/10 border border-amber-500/30
                        text-amber-400 text-xs font-semibold px-4 py-1.5 rounded-full mb-8 uppercase tracking-widest">
          DataHacks 2026 · Best Use of AWS
        </div>

        <h1 className="text-5xl font-bold tracking-tight leading-tight mb-6">
          Solar panels fail silently.<br />
          <span className="text-amber-400">SolarSentinel doesn't miss a thing.</span>
        </h1>

        <p className="text-lg text-slate-400 leading-relaxed max-w-2xl mx-auto mb-10">
          Most homeowners find out their solar panels are underperforming when they open their
          electricity bill — months later. SolarSentinel catches the problem in seconds, using
          real weather data and AI to know exactly what every panel should be producing right now.
        </p>

        <button
          onClick={onGoToDashboard}
          className="inline-flex items-center gap-2 bg-amber-500 hover:bg-amber-400
                     text-slate-900 font-bold px-8 py-3.5 rounded-xl text-base transition-all
                     shadow-lg shadow-amber-500/20 hover:shadow-amber-400/30"
        >
          ▶ Open Live Dashboard
        </button>

        <p className="text-xs text-slate-600 mt-4">
          Press the button, then watch 50 real San Diego solar installs come online — live.
        </p>
      </section>

      {/* ── How it works ──────────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-8 py-16 border-t border-slate-800">
        <h2 className="text-2xl font-bold text-center mb-2">How it works</h2>
        <p className="text-slate-500 text-center text-sm mb-12">
          Three steps, fully automated, no human in the loop.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {HOW_IT_WORKS.map((step, i) => (
            <div
              key={i}
              className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6
                         hover:border-slate-500 transition-colors"
            >
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-bold text-amber-500 bg-amber-500/10
                                 px-2 py-0.5 rounded-full">
                  Step {i + 1}
                </span>
                <span className="text-xl">{step.icon}</span>
              </div>
              <h3 className="font-semibold text-slate-100 mb-3 leading-snug">{step.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Why it matters ────────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-8 py-16 border-t border-slate-800">
        <h2 className="text-2xl font-bold text-center mb-2">Why it matters</h2>
        <p className="text-slate-500 text-center text-sm mb-12">
          Solar panel degradation is a $2.5 billion/year problem in the US — almost all of it invisible.
        </p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {WHY_IT_MATTERS.map((item, i) => (
            <div
              key={i}
              className="bg-slate-800/40 border border-slate-700 rounded-2xl p-6 text-center"
            >
              <p className="text-3xl font-bold text-amber-400 mb-1">{item.stat}</p>
              <p className="text-sm font-semibold text-slate-200 mb-1">{item.label}</p>
              <p className="text-xs text-slate-500 leading-snug">{item.sub}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Data source callout ───────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-8 py-16 border-t border-slate-800">
        <div className="bg-gradient-to-r from-blue-900/30 to-slate-800/30 border border-blue-700/30
                        rounded-2xl p-8 flex flex-col md:flex-row items-start md:items-center gap-6">
          <div className="text-5xl shrink-0">🌊</div>
          <div>
            <p className="text-xs font-bold text-blue-400 uppercase tracking-widest mb-1">
              Data Source · Scripps Challenge
            </p>
            <h3 className="text-xl font-bold mb-2">
              Powered by the Scripps Institution of Oceanography
            </h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Our AI model was trained on thousands of real readings from Scripps' Automated
              Weather Network (AWN) — solar radiation, outdoor temperature, humidity, and UV
              index measured at the actual San Diego climate, not estimates. When the model
              predicts what a panel should produce, it's grounded in real Scripps science.
            </p>
          </div>
        </div>
      </section>

      {/* ── Differentiator ────────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-8 py-16 border-t border-slate-800">
        <h2 className="text-2xl font-bold text-center mb-2">What makes this different</h2>
        <p className="text-slate-500 text-center text-sm mb-12">
          Existing solar monitoring tools have a fundamental flaw — SolarSentinel fixes it.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-800/30 border border-red-900/40 rounded-2xl p-6">
            <p className="text-xs font-bold text-red-400 uppercase tracking-widest mb-3">
              ❌ Traditional monitoring
            </p>
            <ul className="text-sm text-slate-400 space-y-2.5">
              <li>• Fires alerts on <strong className="text-slate-300">raw output thresholds</strong> — pages you every cloudy afternoon</li>
              <li>• Requires <strong className="text-slate-300">proprietary hardware</strong> — locks you to one brand</li>
              <li>• Shows a number, not a <strong className="text-slate-300">reason</strong></li>
              <li>• Checks daily — <strong className="text-slate-300">hours of revenue lost</strong> before anyone notices</li>
            </ul>
          </div>
          <div className="bg-gradient-to-b from-amber-900/20 to-slate-800/30
                          border border-amber-600/40 rounded-2xl p-6 relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2">
              <span className="bg-amber-500 text-slate-900 text-xs font-bold
                               px-3 py-1 rounded-full uppercase tracking-wider">
                SolarSentinel
              </span>
            </div>
            <ul className="text-sm text-slate-300 space-y-2.5 mt-2">
              <li>✅ <strong>Weather-corrected AI</strong> — only alerts when output is low <em>given actual Scripps sunlight</em></li>
              <li>✅ <strong>Hardware-agnostic</strong> — any install, any brand, any inverter</li>
              <li>✅ <strong>Root cause diagnosis</strong> — hardware fault, soiling, or just clouds?</li>
              <li>✅ <strong>Sub-5-second detection</strong> — WebSocket push the moment a reading is scored</li>
            </ul>
          </div>
          <div className="bg-slate-800/30 border border-slate-700 rounded-2xl p-6">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
              🌊 The Scripps advantage
            </p>
            <p className="text-sm text-slate-400 leading-relaxed">
              Our baseline is grounded in <strong className="text-slate-300">real Scripps AWN sensor data</strong> —
              not manufacturer spec sheets or satellite estimates.
              When the model says ZP-0014 should produce 0.55 kWh,
              that's based on what the sky over San Diego is <em>actually doing right now</em>,
              measured by scientists, not guessed by an algorithm.
            </p>
          </div>
        </div>
      </section>

      {/* ── Tech stack ────────────────────────────────────────────────── */}
      <section className="max-w-5xl mx-auto px-8 py-16 border-t border-slate-800">
        <h2 className="text-xl font-bold text-center mb-2 text-slate-300">Built on</h2>
        <div className="flex flex-wrap justify-center gap-3 mt-6">
          {TECH_PILLS.map(t => (
            <span
              key={t}
              className="bg-slate-800 border border-slate-600 text-slate-400
                         text-xs px-4 py-2 rounded-full font-medium"
            >
              {t}
            </span>
          ))}
        </div>
      </section>

      {/* ── Bottom CTA ────────────────────────────────────────────────── */}
      <section className="border-t border-slate-800 py-16 text-center px-8">
        <p className="text-slate-400 mb-6 text-lg">
          Ready to see it catch a real fault — live?
        </p>
        <button
          onClick={onGoToDashboard}
          className="inline-flex items-center gap-2 bg-amber-500 hover:bg-amber-400
                     text-slate-900 font-bold px-8 py-3.5 rounded-xl text-base transition-all
                     shadow-lg shadow-amber-500/20"
        >
          ▶ Open Live Dashboard
        </button>
      </section>

    </div>
  )
}
