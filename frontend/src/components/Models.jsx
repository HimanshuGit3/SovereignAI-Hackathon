import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Glyph } from './glyphs.jsx'

/* The model registry, rendered from models/registry.yaml.
   Adding a model means editing that file: no code change, no redeploy.
   The routing preview at the bottom shows the selection actually
   happening, which is the requirement this screen exists to prove. */

const ROLE_GLYPH = {
  router: 'router', general: 'orch', code: 'sandbox',
  vision: 'ingest', 'vision-alt': 'ingest', embedding: 'kb',
}

const PROBES = [
  ['Draft an approval note from this inspection report', []],
  ['Write a Python function to size a relief valve', []],
  ['Describe this drawing', ['data/samples/pid_extract.png']],
  ['What is the flash point of diesel?', []],
]

export default function Models() {
  const [data, setData] = useState(null)
  const [routes, setRoutes] = useState([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.models().then(setData).catch(() => {})
    const t = setInterval(() => api.models().then(setData).catch(() => {}), 6000)
    return () => clearInterval(t)
  }, [])

  async function probe() {
    setBusy(true); setRoutes([])
    try {
      for (const [task, atts] of PROBES) {
        const r = await api.route(task, atts)
        setRoutes((prev) => [...prev, { task, ...r }])
      }
    } finally { setBusy(false) }
  }

  const models = data?.models || []
  const resident = models.filter((m) => m.resident)
  const vram = resident.reduce((a, m) => a + (m.vram_gb || 0), 0)
  const disk = models.reduce((a, m) => a + (m.size_gb || 0), 0)

  return (
    <div className="screen scroll">
      <div className="screen-head">
        <div>
          <h2>Models</h2>
          <p>
            Every model is open-weight and runs locally. The registry is the
            single source of truth: adding a model means adding a few lines
            of YAML, not changing code.
          </p>
        </div>
        <button className="btn sm" onClick={probe} disabled={busy}>
          {busy ? 'Routing' : 'Run routing probe'}
        </button>
      </div>

      <div className="grid-3" style={{ marginBottom: 'var(--s4)' }}>
        <Stat v={models.length} l="Registered" n="all Apache 2.0 or open terms" />
        <Stat v={`${vram.toFixed(2)} GB`} l="Resident in VRAM"
              n={`${resident.length} of ${models.length} loaded`} tone="ok" />
        <Stat v={`${disk.toFixed(1)} GB`} l="On disk" n="pulled once, no network at run time" />
      </div>

      <div className="modelgrid">
        {models.map((m) => (
          <div key={m.id} className={`mcard ${m.resident ? 'on' : ''}`}>
            <div className="mc-top">
              <svg width="34" height="34" viewBox="-17 -17 34 34" className="mc-ico">
                <Glyph kind={ROLE_GLYPH[m.role] || 'orch'} />
              </svg>
              <div className="grow">
                <div className="mc-name mono">{m.name}</div>
                <div className="mc-role">{m.role}</div>
              </div>
              <span className={`lamp ${m.resident ? 'on' : 'idle'}`}>
                {m.resident ? 'in VRAM' : 'on disk'}
              </span>
            </div>

            <div className="mc-desc">{m.description}</div>

            <div className="mc-caps">
              {(m.capabilities || []).map((c) => (
                <span key={c} className={`tag ${c === 'orchestrator' ? 'info' : ''}`}>{c}</span>
              ))}
            </div>

            <div className="mc-foot">
              <span><b>{m.size_gb} GB</b> weights</span>
              <span><b>{m.options?.num_ctx?.toLocaleString() ?? '—'}</b> context</span>
              <span><b>{m.options?.temperature ?? '—'}</b> temp</span>
              {m.resident && <span className="ok"><b>{m.vram_gb} GB</b> on GPU</span>}
            </div>

            {m.resident && <div className="mc-bar"><span
              style={{ width: `${Math.min((m.vram_gb / 4) * 100, 100)}%` }} /></div>}
          </div>
        ))}
        {!models.length && <div className="muted">Loading registry</div>}
      </div>

      <div className="scard">
        <div className="scard-head">
          <h3>Routing</h3>
          <span className="dim">{data?.registry_file}</span>
        </div>
        <div className="scard-body">
          {!routes.length && !busy && (
            <div className="muted">
              Run the probe to route four different task types and see which
              model each one selects.
            </div>
          )}
          {routes.map((r, i) => (
            <div key={i} className="routerow">
              <span className="tag info">{r.task_type}</span>
              <span className="mono grow">{r.model_name}</span>
              <span className="dim">{r.reason}</span>
              <span className="mono dim">{r.method}</span>
              <span className="mono dim">{r.routing_latency_ms} ms</span>
            </div>
          ))}
          {busy && <div className="live-bar" style={{ marginTop: 10 }}><span /></div>}
        </div>
      </div>

      <div className="scard">
        <div className="scard-head"><h3>Why these models</h3></div>
        <div className="scard-body proof">
          <div><b>Tool calling was tested, not assumed</b>
            <span>Ollama reports tool support for qwen2.5-coder:3b, but it
            emits tool calls as plain text rather than through the native
            channel. It is a code-generation delegate, not the orchestrator.</span></div>
          <div><b>Context limits are per model and measured</b>
            <span>A sweep from 2K to 16K recorded GPU occupancy at each
            setting. Ollama defaults everything to 4096 regardless of what
            the model card advertises, so each entry sets num_ctx explicitly.</span></div>
          <div><b>Quantisation chosen for the card</b>
            <span>The Q8 build of qwen3.5:2b spilled to CPU on a 4 GB GPU.
            The Q4_K_M build runs fully resident at 91 tokens per second.</span></div>
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
