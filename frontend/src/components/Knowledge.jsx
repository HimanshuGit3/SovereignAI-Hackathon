import { useEffect, useState } from 'react'
import { api } from '../api.js'

/* Grounded question answering over the organisation's own documents.
   Two things matter on this screen: every answer carries citations, and
   a question the corpus cannot answer is refused rather than guessed.
   The second is the harder property, so it gets its own preset. */

const ANSWERABLE = [
  'Who must approve a shutdown for HIGH criticality equipment?',
  'What is the bearing temperature alarm setpoint?',
  'What is the lead time for a standard mechanical seal?',
  'Is rounding of measured values allowed in an approval note?',
  'What does SOP-MECH-014 say about wall thickness?',
]

const UNANSWERABLE = [
  'What is the vibration trip setpoint in mm per second?',
  'What is the maximum allowable flare header pressure?',
]

export default function Knowledge() {
  const [q, setQ] = useState('')
  const [ans, setAns] = useState(null)
  const [busy, setBusy] = useState(false)
  const [stats, setStats] = useState(null)
  const [err, setErr] = useState('')
  const [ms, setMs] = useState(0)

  const load = () => api.kbStatus().then(setStats).catch(() => {})
  useEffect(() => { load() }, [])

  useEffect(() => {
    if (!busy) return
    const t0 = performance.now()
    const id = setInterval(() => setMs(performance.now() - t0), 100)
    return () => clearInterval(id)
  }, [busy])

  async function ask(text) {
    const question = (text ?? q).trim()
    if (!question || busy) return
    setQ(question); setBusy(true); setAns(null); setErr('')
    try {
      setAns(await api.kbAsk(question))
    } catch (e) {
      setErr(String(e.message || e))
    } finally { setBusy(false) }
  }

  async function reindex() {
    setBusy(true)
    try { await api.kbReindex(); await load() } finally { setBusy(false) }
  }

  return (
    <div className="screen scroll">
      <div className="screen-head">
        <div>
          <h2>Knowledge base</h2>
          <p>
            Answers are generated only from retrieved excerpts of the
            organisation's own SOPs, manuals and correspondence. Retrieval
            is hybrid: BM25 lexical scoring fused with dense embeddings, so
            exact document and tag references resolve as well as meaning.
          </p>
        </div>
        <button className="btn ghost sm" onClick={reindex} disabled={busy}>
          Reindex
        </button>
      </div>

      <div className="grid-3" style={{ marginBottom: 'var(--s4)' }}>
        <Stat v={stats?.total_chunks ?? '—'} l="Indexed chunks"
              n="sectioned on document headings" />
        <Stat v={stats?.documents?.length ?? '—'} l="Documents"
              n="SOPs and correspondence" />
        <Stat v="0.62" l="Confidence floor"
              n="below this, no model is called" tone="ok" />
      </div>

      <div className="askbar">
        <textarea rows={2} value={q} placeholder="Ask about a procedure, limit, authority or lead time"
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask() } }} />
        <button className="btn" onClick={() => ask()} disabled={busy || !q.trim()}>
          {busy ? `${(ms / 1000).toFixed(1)} s` : 'Ask'}
        </button>
      </div>

      <div className="presets">
        <span className="pl">Answerable</span>
        {ANSWERABLE.map((t) => (
          <button key={t} className="chip" onClick={() => ask(t)} disabled={busy}>
            {t.length > 42 ? t.slice(0, 40) + '…' : t}
          </button>
        ))}
      </div>

      <div className="presets">
        <span className="pl warn">Not in the corpus — should refuse</span>
        {UNANSWERABLE.map((t) => (
          <button key={t} className="chip warn" onClick={() => ask(t)} disabled={busy}>
            {t.length > 42 ? t.slice(0, 40) + '…' : t}
          </button>
        ))}
      </div>

      {busy && (
        <div className="scard"><div className="scard-body">
          <div className="live-phase">Retrieving and grounding
            <span className="ell"><i>.</i><i>.</i><i>.</i></span></div>
          <div className="live-bar"><span /></div>
        </div></div>
      )}

      {err && <div className="answer" style={{ borderLeftColor: 'var(--trip)' }}>{err}</div>}

      {ans && !busy && (
        <>
          <div className={`kbans ${ans.confident ? '' : 'low'}`}>
            <div className="kb-meta">
              <span className={`tag ${ans.confident ? 'service' : 'alarm'}`}>
                {ans.confident ? 'grounded' : 'below confidence floor'}
              </span>
              <span className="mono dim">top {ans.top_score?.toFixed(3)}</span>
              <span className="mono dim">{ans.model}</span>
              <span className="mono dim">{ans.elapsed_ms} ms</span>
            </div>
            <div className="kb-body">{ans.answer}</div>
          </div>

          <div className="scard">
            <div className="scard-head">
              <h3>Sources consulted</h3>
              <span className="dim">{ans.sources?.length ?? 0} excerpts</span>
            </div>
            <div className="scard-body">
              {ans.sources?.length ? ans.sources.map((s, i) => (
                <div key={i} className="srcrow">
                  <span className={`tag ${s.score >= 0.7 ? 'service' : s.score >= 0.58 ? 'info' : 'alarm'}`}>
                    {s.score.toFixed(3)}
                  </span>
                  <div className="grow">
                    <div className="mono srccite">{s.citation}</div>
                    <div className="srcex">{s.excerpt}</div>
                  </div>
                </div>
              )) : (
                <div className="muted">
                  Nothing scored above the floor, so no excerpts were passed
                  to the model and no answer was generated.
                </div>
              )}
            </div>
          </div>
        </>
      )}

      <div className="scard">
        <div className="scard-head"><h3>Indexed documents</h3></div>
        <div className="scard-body">
          {stats?.documents?.map((d) => (
            <div key={d.doc_id} className="destrow">
              <span className="mono grow">{d.source}</span>
              <span className="tag">{d.chunks} chunks</span>
            </div>
          )) || <div className="muted">Loading</div>}
          <div className="muted" style={{ marginTop: 10, fontSize: 11.5 }}>
            Embeddings: {stats?.embed_model} · stored in SQLite with numpy
            cosine similarity. No external vector service.
          </div>
        </div>
      </div>
    </div>
  )
}

function Stat({ v, l, n, tone = '' }) {
  return (
    <div className={`statcard ${tone}`}>
      <div className="sc-val">{v}</div>
      <div className="sc-lab">{l}</div>
      <div className="sc-note">{n}</div>
    </div>
  )
}
