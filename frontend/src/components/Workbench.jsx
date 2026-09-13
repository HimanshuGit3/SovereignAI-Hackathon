import { useEffect, useRef, useState } from 'react'
import { api, streamTask, ms, kb } from '../api.js'
import { Tag, Zone, Empty } from './bits.jsx'
import InstrumentRail from './InstrumentRail.jsx'
import Hero from './Hero.jsx'
import Upload from './Upload.jsx'

const PRESETS = [
  ['Approval note', 'Read data/samples/inspection_report.png, extract the key findings and draft a formal approval note as a Word document called approval_note.docx'],
  ['Read a drawing', 'Read data/samples/pid_extract.png and list every equipment tag with what it represents'],
  ['Pump power', 'A pump moves 0.028 m3/s of crude at density 850 kg/m3 against 45 m head at 72 percent efficiency. Calculate the shaft power and show the working.'],
  ['NPSH available', 'Calculate NPSH available: suction pressure 1.8 bar absolute, vapour pressure 0.35 bar, density 850 kg/m3, static head 3.2 m, friction losses 0.9 m'],
  ['Run code', 'Write and run Python that computes the first 12 Fibonacci numbers'],
  ['Check an SOP', 'Who must approve a shutdown for HIGH criticality equipment?'],
]

export default function Workbench({ health, models, egress, onDone }) {
  const [task, setTask] = useState('')
  const [running, setRunning] = useState(false)
  const [routing, setRouting] = useState(null)
  const [steps, setSteps] = useState([])
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState('')
  const [files, setFiles] = useState(null)
  const traceEnd = useRef(null)

  const loadFiles = () => api.files().then(setFiles).catch(() => {})
  useEffect(() => { loadFiles() }, [])

  useEffect(() => {
    traceEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [steps, summary])

  async function run() {
    const t = task.trim()
    if (!t || running) return
    setRunning(true)
    setRouting(null); setSteps([]); setSummary(null); setError('')

    try {
      await streamTask(t, [], (ev) => {
        if (ev.type === 'routing') setRouting(ev)
        else if (ev.type === 'step') setSteps((s) => [...s, ev])
        else if (ev.type === 'done') setSummary(ev)
        else if (ev.type === 'error') setError(ev.error)
      })
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setRunning(false)
      loadFiles()
      onDone?.()
    }
  }

  async function runWorkflow() {
    if (running) return
    setRunning(true)
    setRouting(null); setSteps([]); setSummary(null); setError('')
    try {
      const r = await api.runWorkflow(
        'data/samples/inspection_report.png', 'approval_note.docx')
      setSteps(r.stages.map((s) => ({
        type: 'step', n: s.n, kind: 'tool', tool: s.name,
        ok: s.ok, arguments: {}, observation: s.detail,
        elapsed_ms: s.elapsed_ms, model: 'workflow',
      })))
      setSummary({
        steps: r.stages.length, tool_calls: r.stages.map((s) => s.name),
        artifacts: r.artifacts, total_ms: r.total_ms,
        stopped_reason: r.failed || 'workflow complete',
        answer: r.summary, orchestrator_model: 'scripted pipeline',
      })
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setRunning(false); loadFiles(); onDone?.()
    }
  }

  return (
    <>
      <aside className="rail col">
        <div className="scroll pad stack">
          <Zone title="Documents">
            <Upload onUploaded={(f) => {
              loadFiles()
              setTask(`Read ${f.path} and summarise the key findings`)
            }} />
            <div style={{ marginTop: 10 }}>
              {[...(files?.uploads || []), ...(files?.samples || [])].map((f) => (
                <div key={f.path} className="filerow"
                     onClick={() => setTask(`Read ${f.path} and summarise the key findings`)}>
                  <span className="fname grow">{f.name}</span>
                  {f.area === 'upload' && <span className="tag info">yours</span>}
                  <span className="muted mono" style={{ fontSize: 10.5 }}>{kb(f.size)}</span>
                </div>
              ))}
              {!files?.samples?.length && !files?.uploads?.length && (
                <div className="muted">No documents yet</div>
              )}
            </div>
          </Zone>

          <Zone title="Generated deliverables">
            {files?.outputs?.length ? (
              <div className="stack">
                {files.outputs.slice(-8).reverse().map((f) => (
                  <a key={f.path} className="row" href={api.downloadUrl(f.name)}
                     style={{ textDecoration: 'none', color: 'inherit', fontSize: 12.5 }}>
                    <span className="mono grow" style={{ color: 'var(--blueprint)' }}>{f.name}</span>
                    <span className="muted mono">{kb(f.size)}</span>
                  </a>
                ))}
              </div>
            ) : <div className="muted">Nothing generated yet</div>}
          </Zone>
        </div>
      </aside>

      <section className="col grow">
        <div className="pad" style={{ borderBottom: '1px solid var(--rule-soft)' }}>
          <div className="row" style={{ alignItems: 'flex-start' }}>
            <textarea
              className="grow"
              rows={3}
              value={task}
              placeholder="Describe the work. The router picks the model; the agent picks the tools."
              onChange={(e) => setTask(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) run()
              }}
            />
            <button className="btn" onClick={run} disabled={running || !task.trim()}>
              {running ? 'Working' : 'Run'}
            </button>
          </div>

          <div className="wrap" style={{ marginTop: 12 }}>
            {PRESETS.map(([label, text]) => (
              <button key={label} className="chip" onClick={() => setTask(text)}>{label}</button>
            ))}
            <button className="chip" style={{ borderColor: 'var(--service)', color: 'var(--service)' }}
              onClick={runWorkflow} disabled={running}>
              Run scripted workflow
            </button>
          </div>
        </div>

        <div className="scroll pad grow">
          {!routing && !steps.length && !error && (
            <Hero onRun={runWorkflow} disabled={running} />
          )}

          {routing && (
            <div className="stack" style={{ marginBottom: 20 }}>
              <div className="row" style={{ flexWrap: 'wrap' }}>
                <span className="muted">Routed to</span>
                <Tag kind="info">{routing.task_type}</Tag>
                <Tag>{routing.model_name}</Tag>
                <span className="muted mono" style={{ fontSize: 11 }}>
                  {routing.method}, {routing.routing_latency_ms} ms
                </span>
              </div>
              <div className="muted" style={{ fontSize: 12 }}>{routing.reason}</div>
            </div>
          )}

          {steps.length > 0 && (
            <div className="trace">
              {steps.map((s, i) => (
                <div key={i} className={`step ${s.ok ? '' : 'err'} ${s.kind === 'final' ? 'final' : ''}`}>
                  <div className="marker">{s.kind === 'final' ? '\u2713' : s.n}</div>
                  <div className="step-head">
                    <span className="name">{s.kind === 'final' ? 'answer' : s.tool}</span>
                    {!s.ok && <Tag kind="trip">failed</Tag>}
                    <span className="t">{ms(s.elapsed_ms)}</span>
                  </div>
                  {s.kind === 'tool' && Object.keys(s.arguments || {}).length > 0 && (
                    <div className="obs" style={{ maxHeight: 90 }}>
                      {JSON.stringify(s.arguments, null, 1)}
                    </div>
                  )}
                  {s.observation && <div className="obs">{s.observation}</div>}
                  {s.kind === 'final' && s.content && <div className="answer">{s.content}</div>}
                </div>
              ))}
            </div>
          )}

          {error && <div className="answer" style={{ borderLeftColor: 'var(--trip)' }}>{error}</div>}

          {summary?.artifacts?.map((a) => {
            const name = a.split('/').pop()
            return (
              <a key={a} className="artifact" href={api.downloadUrl(name)} download>
                Download {name}
              </a>
            )
          })}

          <div ref={traceEnd} />
        </div>
      </section>

      <InstrumentRail
        egress={egress}
        health={health}
        models={models}
        summary={summary}
        running={running}
      />
    </>
  )
}
