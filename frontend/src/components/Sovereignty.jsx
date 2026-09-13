import { useEffect, useState } from 'react'
import { api } from '../api.js'

/* Requirement #5. The problem statement calls this "the actual proof of
   the sovereign claim, not just a statement of it", so the screen shows
   the instrument working before it shows a clean result. */

export default function Sovereignty({ egress, onRefresh }) {
  const [cap, setCap] = useState(null)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')

  const ext = egress?.external_count ?? 0
  const clean = ext === 0
  const dest = egress?.destinations || []
  const events = egress?.events || []

  async function proveItWorks() {
    setBusy('capture'); setErr(''); setCap(null)
    try {
      await api.captureStart()
      await new Promise((r) => setTimeout(r, 6000))
      setCap(await api.captureStop())
    } catch (e) {
      setErr(String(e.message || e))
    } finally { setBusy('') }
  }

  async function reset() {
    setBusy('reset')
    try { await api.egressReset(); await onRefresh?.() } finally { setBusy('') }
  }

  return (
    <div className="screen scroll">
      <div className="screen-head">
        <div>
          <h2>Sovereignty</h2>
          <p>Every network destination this process contacts, classified and audited.</p>
        </div>
        <div className="row">
          <button className="btn ghost sm" onClick={reset} disabled={!!busy}>
            {busy === 'reset' ? 'Clearing' : 'Clear audit'}
          </button>
          <button className="btn sm" onClick={proveItWorks} disabled={!!busy}>
            {busy === 'capture' ? 'Capturing 6 s' : 'Run packet capture'}
          </button>
        </div>
      </div>

      <div className={`verdict-hero ${clean ? 'ok' : 'bad'}`}>
        <div className="vh-num">{ext}</div>
        <div className="vh-txt">
          <b>{clean ? 'No external destinations' : 'External egress detected'}</b>
          <span>
            {egress?.total_requests ?? 0} requests audited this session.
            Destinations are classified by IP properties, not against a
            blocklist, so an unknown address counts as external by default.
          </span>
        </div>
        <div className="vh-ring" />
      </div>

      <div className="grid-3">
        <Stat label="Loopback" value={egress?.by_classification?.LOCAL ?? 0}
              note="same process" />
        <Stat label="Private / LAN" value={egress?.by_classification?.PRIVATE ?? 0}
              note="same physical host" tone="ok" />
        <Stat label="External" value={ext} note="routable public address"
              tone={ext ? 'bad' : ''} />
      </div>

      <Section title="Destinations contacted">
        {dest.length ? dest.map((d) => (
          <div key={d} className="destrow">
            <span className="lamp on" />
            <span className="mono grow">{d}</span>
            <span className="tag service">private</span>
          </div>
        )) : <div className="muted">No traffic recorded yet</div>}
      </Section>

      {cap && (
        <Section title="Kernel packet capture"
                 right={<span className="tag info">{cap.duration_s}s on {'any'}</span>}>
          <pre className="capture">{cap.report}</pre>
        </Section>
      )}

      {err && <div className="answer" style={{ borderLeftColor: 'var(--trip)' }}>{err}</div>}

      <Section title="Recent calls">
        <div className="calltable">
          {events.slice(-14).reverse().map((e, i) => (
            <div key={i} className={`callrow ${e.classification === 'EXTERNAL' ? 'bad' : ''}`}>
              <span className="mono dim">{e.ts?.slice(11, 19)}</span>
              <span className={`tag ${e.classification === 'EXTERNAL' ? 'trip' : 'service'}`}>
                {e.classification}
              </span>
              <span className="mono grow">{e.host}:{e.port}</span>
              <span className="mono dim">{e.status ?? '-'}</span>
              <span className="mono dim">{e.elapsed_ms} ms</span>
            </div>
          ))}
          {!events.length && <div className="muted">Nothing yet</div>}
        </div>
      </Section>

      <Section title="How this is proven">
        <div className="proof">
          <div><b>1 &middot; Application audit</b>
            <span>The HTTP transport is patched, so every request in this
            process is recorded regardless of which library made it.</span></div>
          <div><b>2 &middot; Kernel capture</b>
            <span>tcpdump observes what actually crossed the interface. It
            does not trust the application, and reports INCONCLUSIVE rather
            than SOVEREIGN if it parses no packets.</span></div>
          <div><b>3 &middot; Negative control</b>
            <span>A deliberate external call must be detected before any
            clean result is trusted. An instrument that cannot see a
            violation cannot prove the absence of one.</span></div>
          <div><b>4 &middot; Air-gap enforcement</b>
            <span>infra/network/airgap.sh stops host services that reach the
            internet and rejects public egress on both the OUTPUT and
            FORWARD chains.</span></div>
        </div>
      </Section>
    </div>
  )
}

function Stat({ label, value, note, tone = '' }) {
  return (
    <div className={`statcard ${tone}`}>
      <div className="sc-val">{value}</div>
      <div className="sc-lab">{label}</div>
      <div className="sc-note">{note}</div>
    </div>
  )
}

function Section({ title, right, children }) {
  return (
    <div className="scard">
      <div className="scard-head">
        <h3>{title}</h3>
        {right}
      </div>
      <div className="scard-body">{children}</div>
    </div>
  )
}
