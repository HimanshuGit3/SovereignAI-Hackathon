import { useEffect, useRef, useState } from 'react'
import { api, ms } from '../api.js'

/* Operational overview. Every figure is measured: host metrics come
   from /proc, VRAM from the inference node, run history from this
   session. Nothing is illustrative. */

function useCountUp(target, dur = 900) {
  const [v, setV] = useState(0)
  const from = useRef(0)
  useEffect(() => {
    const t0 = performance.now()
    const start = from.current
    let raf
    const step = (now) => {
      const p = Math.min((now - t0) / dur, 1)
      const e = 1 - Math.pow(1 - p, 3)
      setV(start + (target - start) * e)
      if (p < 1) raf = requestAnimationFrame(step)
      else from.current = target
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, dur])
  return v
}

function Ring({ pct, label, value, tone = 'blue' }) {
  const p = useCountUp(pct || 0)
  const R = 34, C = 2 * Math.PI * R
  return (
    <div className="ring">
      <svg width="92" height="92" viewBox="0 0 92 92">
        <circle className="ring-bg" cx="46" cy="46" r={R} />
        <circle className={`ring-fg ${tone}`} cx="46" cy="46" r={R}
                strokeDasharray={C}
                strokeDashoffset={C - (C * Math.min(p, 100)) / 100}
                transform="rotate(-90 46 46)" />
      </svg>
      <div className="ring-mid">
        <b>{Math.round(p)}<i>%</i></b>
      </div>
      <div className="ring-lab">{label}</div>
      <div className="ring-val">{value}</div>
    </div>
  )
}

function Spark({ points, height = 46 }) {
  if (!points.length) return <div className="sparkempty">No runs yet</div>
  const max = Math.max(...points, 1)
  const w = 240
  const step = points.length > 1 ? w / (points.length - 1) : w
  const d = points.map((v, i) =>
    `${i ? 'L' : 'M'} ${i * step} ${height - (v / max) * (height - 6) - 3}`).join(' ')
  const area = `${d} L ${(points.length - 1) * step} ${height} L 0 ${height} Z`
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id="sparkfill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--indigo)" stopOpacity=".22" />
          <stop offset="100%" stopColor="var(--indigo)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path className="spark-area" d={area} fill="url(#sparkfill)" />
      <path className="spark-line" d={d} />
      {points.map((v, i) => (
        <circle key={i} className="spark-dot" cx={i * step}
                cy={height - (v / max) * (height - 6) - 3} r="2.2"
                style={{ animationDelay: `${i * 60}ms` }} />
      ))}
    </svg>
  )
}

export default function Dashboard({ egress, health, models = [] }) {
  const [m, setM] = useState(null)

  useEffect(() => {
    const pull = () => api.metrics().then(setM).catch(() => {})
    pull()
    const t = setInterval(pull, 3000)
    return () => clearInterval(t)
  }, [])

  const ext = egress?.external_count ?? 0
  const resident = models.filter((x) => x.resident)
  const vram = resident.reduce((a, x) => a + (x.vram_gb || 0), 0)
  const vramPct = Math.min((vram / 4) * 100, 100)
  const durations = (m?.runs?.recent || []).map((r) => r.total_ms || 0)
  const sv = m?.sovereign

  const totalRuns = useCountUp(m?.runs?.total ?? 0)
  const audited = useCountUp(egress?.total_requests ?? 0)

  return (
    <div className="screen scroll">
      <div className="screen-head">
        <div>
          <h2>Dashboard</h2>
          <p>
            Live operational state of the workbench. Host figures are read
            from the kernel; model residency from the inference node.
          </p>
        </div>
        <div className="uptime mono">
          uptime {m ? fmtUptime(m.uptime_s) : '—'}
        </div>
      </div>

      <div className="hero-strip">
        <div className={`hs-card ${ext ? 'bad' : 'ok'}`}>
          <div className="hs-lab">Sovereignty</div>
          <div className="hs-val">{ext === 0 ? 'SEALED' : 'BREACH'}</div>
          <div className="hs-note">
            {Math.round(audited)} calls audited · {ext} external
          </div>
          <div className="hs-pulse" />
        </div>

        <div className="hs-card">
          <div className="hs-lab">Inference node</div>
          <div className="hs-val">{health?.inference_reachable ? 'ONLINE' : 'DOWN'}</div>
          <div className="hs-note">{resident.length} of {models.length} models resident</div>
        </div>

        <div className="hs-card">
          <div className="hs-lab">Tasks this session</div>
          <div className="hs-val mono">{Math.round(totalRuns)}</div>
          <div className="hs-note">
            {m?.runs?.success_rate != null ? `${m.runs.success_rate}% succeeded` : 'none yet'}
          </div>
        </div>

        <div className="hs-card">
          <div className="hs-lab">Median task</div>
          <div className="hs-val mono">{m?.runs?.median_ms ? ms(m.runs.median_ms) : '—'}</div>
          <div className="hs-note">across {m?.runs?.total ?? 0} runs</div>
        </div>
      </div>

      <div className="dash-grid">
        <Panel title="Model selection"
               note={sv?.deterministic_pct != null
                 ? `${sv.deterministic_pct}% routed without an inference call`
                 : 'no runs yet'}>
          <Split a={{ n: sv?.routing?.deterministic ?? 0, l: 'Deterministic',
                      s: '0–1 ms, regex signals', tone: 'green' }}
                 b={{ n: sv?.routing?.llm ?? 0, l: 'LLM classifier',
                      s: '~400 ms, only when ambiguous', tone: 'blue' }} />
          <Bars rows={sv?.by_model || []} empty="No tasks routed yet" />
        </Panel>

        <Panel title="Document ingest"
               note="routed by measured OCR yield, not file type">
          <Split a={{ n: sv?.ingest?.ocr ?? 0, l: 'OCR path',
                      s: '≥300 chars/MP, ~320 ms', tone: 'green' }}
                 b={{ n: sv?.ingest?.vision ?? 0, l: 'Vision escalation',
                      s: 'sparse text, ~4 s', tone: 'amber' }} />
          <div className="minirow">
            <span>Native PDF text layer</span>
            <b className="mono">{sv?.ingest?.native_pdf ?? 0}</b>
          </div>
        </Panel>
      </div>

      <div className="dash-grid">
        <Panel title="Grounded retrieval"
               note="confidence floor 0.62 — below it, no model is called">
          <Split a={{ n: sv?.retrieval?.answered ?? 0, l: 'Answered',
                      s: 'with citations', tone: 'green' }}
                 b={{ n: sv?.retrieval?.refused ?? 0, l: 'Refused',
                      s: 'corpus does not cover it', tone: 'slate' }} />
          <div className="note-line">
            Refusing is the harder property. A retrieval system that always
            answers is guessing on the questions it cannot support.
          </div>
        </Panel>

        <Panel title="Safety-critical paths">
          <div className="tiles">
            <Tile n={sv?.verified_calcs ?? 0} l="Verified calculations"
                  s="deterministic code, not the LLM" tone="green" />
            <Tile n={sv?.sandbox_runs ?? 0} l="Sandboxed executions"
                  s="no network namespace" tone="blue" />
            <Tile n={sv?.deliverables ?? 0} l="Deliverables written"
                  s="figures copied verbatim" tone="green" />
            <Tile n={sv?.model_swaps ?? 0} l="Model swaps"
                  s="12–20 s each on 4 GB VRAM" tone="amber" />
          </div>
        </Panel>
      </div>

    </div>
  )
}

function Panel({ title, note, children }) {
  return (
    <div className="scard">
      <div className="scard-head">
        <h3>{title}</h3>
        {note && <span className="dim">{note}</span>}
      </div>
      <div className="scard-body">{children}</div>
    </div>
  )
}

function Split({ a, b }) {
  const total = (a.n + b.n) || 1
  return (
    <>
      <div className="splitbar">
        <span className={a.tone} style={{ width: `${(a.n / total) * 100}%` }} />
        <span className={b.tone} style={{ width: `${(b.n / total) * 100}%` }} />
      </div>
      <div className="splitlegend">
        {[a, b].map((x) => (
          <div key={x.l}>
            <i className={x.tone} />
            <b className="mono">{x.n}</b>
            <span>{x.l}</span>
            <em>{x.s}</em>
          </div>
        ))}
      </div>
    </>
  )
}

function Bars({ rows, empty }) {
  if (!rows.length) return <div className="muted">{empty}</div>
  const max = rows[0][1] || 1
  return (
    <div className="minibars">
      {rows.map(([label, n], i) => (
        <div key={label} className="barrow">
          <span className="mono bl">{label}</span>
          <div className="bar">
            <span style={{ width: `${(n / max) * 100}%`, animationDelay: `${i * 70}ms` }} />
          </div>
          <span className="mono bn">{n}</span>
        </div>
      ))}
    </div>
  )
}

function Tile({ n, l, s, tone }) {
  return (
    <div className={`tile ${tone}`}>
      <div className="tile-n mono">{n}</div>
      <div className="tile-l">{l}</div>
      <div className="tile-s">{s}</div>
    </div>
  )
}

function fmtUptime(s) {
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}
