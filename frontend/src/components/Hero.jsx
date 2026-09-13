import { useEffect, useState } from 'react'

/* The idle state runs the flagship transformation on a loop: a scan
   line crosses the real inspection report, each stage ignites in turn,
   and the approval note assembles itself. The motion is the process,
   not decoration. It pauses the moment the user starts a real run. */

const SRC = (p) => `/api/preview?path=${encodeURIComponent(p)}`

const STAGES = [
  ['Scan', 'OCR, 320 ms, no vision model needed'],
  ['Extract', 'tag, criticality, four findings'],
  ['Consult', 'SOP-MECH-014: who approves, how long'],
  ['Draft', 'Word note, figures copied verbatim'],
]

export default function Hero({ onRun, disabled }) {
  const [phase, setPhase] = useState(0)

  useEffect(() => {
    if (disabled) return
    const t = setInterval(() => setPhase((p) => (p + 1) % 6), 1500)
    return () => clearInterval(t)
  }, [disabled])

  const active = Math.min(phase, STAGES.length)
  const written = phase >= 4

  return (
    <div className="hero">
      <div className="hero-line">
        <figure className="sheet-thumb">
          <div className={`scanframe ${phase === 0 ? 'scanning' : ''}`}>
            <img src={SRC('data/samples/inspection_report.png')}
                 alt="Scanned inspection report" />
            <span className="scanline" />
          </div>
          <figcaption>
            Scanned inspection report<br />
            <span>INSP-2026-0417</span>
          </figcaption>
        </figure>

        <ol className="hero-flow">
          {STAGES.map(([name, detail], i) => (
            <li key={name}
                className={`flow-step ${i < active ? 'done' : ''} ${i === active ? 'live' : ''}`}>
              <span className="flow-dot" />
              <b>{name}</b>
              <span>{detail}</span>
            </li>
          ))}
        </ol>

        <figure className="sheet-thumb">
          <div className={`doc-face ${written ? 'written' : ''}`}>
            <div className="doc-title">APPROVAL NOTE &mdash; P-101A</div>
            <div className="doc-meta">Ref INSP-2026-0417 &middot; HIGH criticality</div>
            <div className="doc-h">Findings</div>
            <ol className="doc-list">
              <li>Casing 8.2 mm against 9.0 mm minimum</li>
              <li>Bearing 82 &deg;C, alarm at 75 &deg;C</li>
              <li>Seal weeping 4 drops/min</li>
            </ol>
            <div className="doc-h">Approval sought</div>
            <div className="doc-body">
              Unit Head and Head of Mechanical Maintenance, within 30 days
              <span className="doc-cite">[SOP-MECH-014 #3]</span>
            </div>
            <div className="doc-sign" />
          </div>
          <figcaption>
            Approval note<br />
            <span>ready for signature</span>
          </figcaption>
        </figure>
      </div>

      <div className="hero-cta">
        <button className="btn" onClick={onRun} disabled={disabled}>
          Run this task
        </button>
        <span className="muted">
          Four stages, about twelve seconds, entirely on this machine.
        </span>
      </div>
    </div>
  )
}
