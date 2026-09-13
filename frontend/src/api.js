// Single point of contact with the backend.
// In dev, Vite proxies /api to the workbench. In production the bundle is
// served by FastAPI itself, so relative paths resolve correctly either way.

const BASE = ''

async function get(path) {
  const r = await fetch(`${BASE}${path}`)
  if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`)
  return r.json()
}

async function post(path, body) {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`)
  return r.json()
}

export const api = {
  health: () => get('/api/health'),
  models: () => get('/api/models'),
  files: () => get('/api/files'),
  workflows: () => get('/api/workflows'),

  route: (task, attachments = []) => post('/api/route', { task, attachments }),
  runTask: (task, attachments = []) => post('/api/task', { task, attachments }),

  runWorkflow: (documentPath, outputFilename, workflow = 'inspection_to_approval') =>
    post('/api/workflow', {
      workflow,
      document_path: documentPath,
      output_filename: outputFilename,
    }),

  kbStatus: () => get('/api/kb/status'),
  kbReindex: () => post('/api/kb/reindex'),
  kbAsk: (question) => post('/api/kb/ask', { task: question }),

  metrics: () => get('/api/metrics'),
  egress: () => get('/api/monitor/egress'),
  egressReset: () => post('/api/monitor/egress/reset'),
  captureStart: () => post('/api/monitor/capture/start'),
  captureStop: () => post('/api/monitor/capture/stop'),

  downloadUrl: (filename) => `${BASE}/api/download/${encodeURIComponent(filename)}`,

  async upload(file) {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${BASE}/api/upload`, { method: 'POST', body: fd })
    if (!r.ok) throw new Error(`upload -> HTTP ${r.status}`)
    return r.json()
  },
}

// Server-sent events over POST. EventSource cannot send a body, so this
// reads the response stream manually. Events can split across network
// chunks, so the incomplete tail is carried into the next iteration.
export async function streamTask(task, attachments, onEvent, signal) {
  const res = await fetch(`${BASE}/api/task/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task, attachments }),
    signal,
  })
  if (!res.ok) throw new Error(`stream -> HTTP ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop()
    for (const part of parts) {
      if (!part.startsWith('data: ')) continue
      try {
        onEvent(JSON.parse(part.slice(6)))
      } catch {
        // a malformed frame should not kill the stream
      }
    }
  }
}

export function ms(n) {
  if (n == null) return '-'
  return n < 1000 ? `${n} ms` : `${(n / 1000).toFixed(1)} s`
}

export function kb(bytes) {
  if (bytes == null) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}
