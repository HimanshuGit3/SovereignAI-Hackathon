import { useEffect, useMemo, useRef, useState } from 'react'
import { Glyph } from './glyphs.jsx'

/* Workflow canvas. Each card is a component that exists in the codebase:
   the id maps to a real module, and a card only lights when that module
   actually ran. No illustrative nodes. */

const NODES = [
  { id: 'input',   x:   8, y: 150, t: 'Input Document',    s: 'PDF · image · scan',
    tag: 'N-101', g: 'ingest' },
  { id: 'ingest',  x: 176, y: 150, t: 'Ingest & Parse',    s: 'OCR yield routing',
    tag: 'N-102', g: 'ingest' },
  { id: 'router',  x: 344, y: 150, t: 'Task Router',       s: 'Deterministic + LLM',
    tag: 'N-103', g: 'router' },
  { id: 'orch',    x: 512, y: 150, t: 'Orchestrator',      s: 'Plan · Act · Observe',
    tag: 'N-104', g: 'orch' },
  { id: 'kb',      x: 700, y:  22, t: 'Knowledge Base',    s: 'Hybrid BM25 + dense',
    tag: 'N-201', g: 'kb' },
  { id: 'calc',    x: 700, y: 106, t: 'Calculation',       s: 'Verified, unit-safe',
    tag: 'N-202', g: 'calc' },
  { id: 'sandbox', x: 700, y: 190, t: 'Code Sandbox',      s: 'No network namespace',
    tag: 'N-203', g: 'sandbox' },
  { id: 'vision',  x: 700, y: 274, t: 'Vision Model',      s: 'Drawings & scans',
    tag: 'N-204', g: 'ingest' },
  { id: 'docgen',  x: 1080, y: 150, t: 'Document Generator', s: 'DOCX · XLSX · PPTX',
    tag: 'N-301', g: 'docgen' },
  { id: 'output',  x: 1080, y: 262, t: 'Deliverable',      s: 'Signed-ready output',
    tag: 'N-401', g: 'docgen' },
]

const W = 152, H = 62

const TOOL_NODE = {
  read_document: 'ingest', list_files: 'ingest',
  __vision: 'vision',
  search_knowledge_base: 'kb', knowledge_base_status: 'kb',
  engineering_calculation: 'calc',
  run_python: 'sandbox', generate_code: 'sandbox',
  create_word_document: 'docgen', write_text_file: 'docgen',
  'ingest document': 'ingest', 'extract structured fields': 'orch',
  'consult SOPs': 'kb', 'draft approval note': 'docgen',
}

const N = Object.fromEntries(NODES.map((n) => [n.id, n]))

/* Orthogonal routing with filleted corners, the way a P&ID or a rack
   diagram is drawn. Straight runs and right angles read as engineered;
   bezier curves read as decoration. */
function link(a, b) {
  const A = N[a], B = N[b]
  const x1 = A.x + W, y1 = A.y + H / 2
  const x2 = B.x, y2 = B.y + H / 2
  const r = 10

  if (Math.abs(y1 - y2) < 2) return `M ${x1} ${y1} H ${x2}`

  const mid = x1 + (x2 - x1) * 0.46
  const down = y2 > y1
  const s1 = down ? 1 : -1
  return [
    `M ${x1} ${y1}`,
    `H ${mid - r}`,
    `Q ${mid} ${y1} ${mid} ${y1 + r * s1}`,
    `V ${y2 - r * s1}`,
    `Q ${mid} ${y2} ${mid + r} ${y2}`,
    `H ${x2}`,
  ].join(' ')
}

/* every branch returns to the orchestrator: the agent reads each tool
   result before choosing the next step, so the loop must be visible */
function returnPath(from) {
  const A = N[from], O = N.orch
  const x1 = A.x + W, y1 = A.y + H / 2
  const bus = 1046
  return `M ${x1} ${y1} H ${bus} V ${O.y + H - 14} H ${O.x + W / 2}`
}

const EDGES = [
  ['input', 'ingest'], ['ingest', 'router'], ['router', 'orch'],
  ['orch', 'kb'], ['orch', 'calc'], ['orch', 'sandbox'], ['orch', 'vision'],
  ['orch', 'docgen'], ['docgen', 'output'],
]

export default function Canvas({ steps = [], running, routing }) {
  const [ping, setPing] = useState(null)
  const seen = useRef(0)

  const active = useMemo(() => {
    if (!steps.length) return running ? 'router' : null
    const last = steps[steps.length - 1]
    if (last.kind === 'final') return 'output'
    return TOOL_NODE[last.tool] || 'orch'
  }, [steps, running])

  useEffect(() => {
    if (steps.length > seen.current) {
      seen.current = steps.length
      setPing(active)
      const t = setTimeout(() => setPing(null), 1200)
      return () => clearTimeout(t)
    }
    if (!steps.length) seen.current = 0
  }, [steps.length, active])

  const used = new Set()
  if (routing) { used.add('input'); used.add('router'); used.add('orch') }
  for (const s of steps) {
    if (s.kind !== 'tool') continue
    const n = TOOL_NODE[s.tool]
    if (n) used.add(n)
    // the vision model only engages when OCR yield fell below threshold
    if (n === 'ingest' && /escalated to|method.*vision/i.test(s.observation || '')) {
      used.add('vision')
    }
  }
  if (steps.some((s) => s.kind === 'final')) used.add('output')

  const cls = (id) =>
    ['node', used.has(id) && 'used', active === id && 'live',
     ping === id && 'ping'].filter(Boolean).join(' ')

  return (
    <svg className={`canvas ${running ? 'running' : ''}`} viewBox="0 0 1240 372">
      <defs>
        <pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="1" className="dot" />
        </pattern>
        <filter id="lift" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity=".10" />
        </filter>
        <filter id="halo" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="4" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      <rect width="1240" height="372" fill="url(#dots)" />

      <g className="edges">
        {EDGES.map(([a, b]) => (
          <path key={`${a}${b}`} d={link(a, b)}
                className={used.has(a) && used.has(b) ? 'on' : ''} />
        ))}
        {['kb', 'calc', 'sandbox', 'vision'].map((b) => (
          <path key={`ret-${b}`} className={`ret ${used.has(b) ? 'on' : ''}`}
                d={returnPath(b)} />
        ))}
      </g>

      {/* junction dots where the return bus meets a branch */}
      <g className="junctions">
        {['kb', 'calc', 'sandbox', 'vision'].map((b) => (
          <circle key={`j${b}`} cx={1046} cy={N[b].y + H / 2} r="3"
                  className={used.has(b) ? 'on' : ''} />
        ))}
      </g>

      {running && active && (
        <g className="pulse">
          {EDGES.filter(([, b]) => b === active).map(([a, b]) => (
            <path key={`p${a}${b}`} d={link(a, b)} />
          ))}
        </g>
      )}

      {NODES.map((n) => (
        <g key={n.id} className={cls(n.id)}>
          <rect x={n.x} y={n.y} width={W} height={H} rx="8" filter="url(#lift)" />
          <rect className="accent" x={n.x} y={n.y} width="3" height={H} rx="1.5" />
          <g transform={`translate(${n.x + 26} ${n.y + 24})`}>
            <Glyph kind={n.g} />
          </g>
          <text className="t" x={n.x + 44} y={n.y + 24}>{n.t}</text>
          <text className="s" x={n.x + 44} y={n.y + 38}>{n.s}</text>
          <text className="tag" x={n.x + 44} y={n.y + 52}>{n.tag}</text>
          {active === n.id && n.id === 'ingest' && (
            <rect className="fx-scan" x={n.x + 2} y={n.y + 2}
                  width={W - 4} height="7" rx="3" />
          )}
          {active === n.id && n.id === 'kb' && (
            <>
              <circle className="fx-sonar" cx={n.x + 26} cy={n.y + 31} r="12" />
              <circle className="fx-sonar d2" cx={n.x + 26} cy={n.y + 31} r="12" />
            </>
          )}
          {active === n.id && n.id === 'calc' && (
            <g className="fx-tick">
              {[0, 1, 2, 3].map((i) => (
                <rect key={i} x={n.x + W - 34 + i * 7} y={n.y + 44}
                      width="4" height="10" rx="1"
                      style={{ animationDelay: `${i * 0.12}s` }} />
              ))}
            </g>
          )}
          {active === n.id && n.id === 'sandbox' && (
            <rect className="fx-seal" x={n.x + 1} y={n.y + 1}
                  width={W - 2} height={H - 2} rx="8" />
          )}
          {active === n.id && n.id === 'docgen' && (
            <g className="fx-write">
              {[0, 1, 2].map((i) => (
                <rect key={i} x={n.x + 44} y={n.y + 40 + i * 5}
                      height="2.2" rx="1"
                      style={{ animationDelay: `${i * 0.22}s` }} />
              ))}
            </g>
          )}
          {active === n.id && n.id === 'router' && (
            <g className="fx-select">
              {[0, 1, 2].map((i) => (
                <circle key={i} cx={n.x + W - 26 + i * 8} cy={n.y + 50} r="2"
                        style={{ animationDelay: `${i * 0.18}s` }} />
              ))}
            </g>
          )}
          {used.has(n.id) && (
            <g transform={`translate(${n.x + W - 15} ${n.y + 14})`}>
              <circle className="tick" r="7" />
              <path className="check" d="M-3 0 l2 2.2 l4 -4.6" />
            </g>
          )}
        </g>
      ))}
    </svg>
  )
}
