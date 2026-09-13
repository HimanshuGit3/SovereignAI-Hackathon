import { useEffect, useRef } from 'react'

/* Timestamped record of what the system actually did, streamed live.
   Every line corresponds to a real event from the backend: a routing
   decision, a tool call, a tool result, an artifact. Nothing is
   synthesised to make the log look busier than the work was. */

const ICON = {
  start: '\u25B8', route: '\u2387', tool: '\u2699', ok: '\u2713',
  fail: '\u2715', artifact: '\u2913', done: '\u25A0', wait: '\u25CC',
}

export function buildLog(routing, steps, summary, running, error) {
  const out = []
  if (routing) {
    out.push({ k: 'start', t: 'Run started', d: 'request accepted' })
    out.push({
      k: 'route',
      t: `Routed to ${routing.task_type}`,
      d: `${routing.model_name} · ${routing.method} · ${routing.routing_latency_ms} ms`,
    })
  }
  for (const s of steps) {
    if (s.kind === 'final') {
      out.push({ k: 'ok', t: 'Answer produced', d: `${s.elapsed_ms} ms` })
      continue
    }
    out.push({ k: 'tool', t: `Calling ${s.tool}`, d: shortArgs(s.arguments) })
    out.push({
      k: s.ok ? 'ok' : 'fail',
      t: s.ok ? `${s.tool} returned` : `${s.tool} failed`,
      d: firstLine(s.observation, s.elapsed_ms),
    })
  }
  for (const a of summary?.artifacts || []) {
    out.push({ k: 'artifact', t: 'Deliverable written', d: a.split('/').pop() })
  }
  if (error) out.push({ k: 'fail', t: 'Run failed', d: error.slice(0, 90) })
  if (summary) {
    out.push({
      k: 'done', t: 'Run complete',
      d: `${summary.steps} steps · ${(summary.total_ms / 1000).toFixed(1)} s`,
    })
  } else if (running) {
    out.push({ k: 'wait', t: 'Working', d: 'awaiting the next step' })
  }
  return out
}

function shortArgs(a) {
  if (!a || !Object.keys(a).length) return 'no arguments'
  const [k, v] = Object.entries(a)[0]
  return `${k}: ${String(v).slice(0, 46)}`
}

function firstLine(obs, ms) {
  const head = (obs || '').split('\n').find((l) => l.trim()) || ''
  const clean = head.replace(/^=+\s*/, '').slice(0, 52)
  return `${ms} ms${clean ? ' · ' + clean : ''}`
}

export default function ExecutionLog({ entries, streaming }) {
  const end = useRef(null)
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [entries.length])

  return (
    <div className="exlog">
      <div className="panel-head">
        <h3>Live execution log</h3>
        <span className={`note ${streaming ? 'streaming' : ''}`}>
          {streaming ? 'streaming' : `${entries.length} events`}
        </span>
      </div>
      <div className="exlog-body">
        {!entries.length && <div className="exlog-idle">No run yet</div>}
        {entries.map((e, i) => (
          <div key={i} className={`exline k-${e.k}`}
               style={{ animationDelay: `${Math.min(i * 35, 400)}ms` }}>
            <span className="ex-ico">{ICON[e.k]}</span>
            <span className="ex-txt">
              <b>{e.t}</b>
              <i>{e.d}</i>
            </span>
          </div>
        ))}
        <div ref={end} />
      </div>
    </div>
  )
}
