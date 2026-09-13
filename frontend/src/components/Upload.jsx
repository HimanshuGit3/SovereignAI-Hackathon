import { useRef, useState } from 'react'
import { api } from '../api.js'

/* Drop target for the left rail. Accepts scans, photographs and PDFs.
   The file lands in data/uploads on the host, then the ingest layer
   routes it: OCR for typed text, vision model for drawings. */

const ACCEPT = '.png,.jpg,.jpeg,.pdf,.tif,.tiff,.webp,.bmp,.txt,.md,.csv'

export default function Upload({ onUploaded }) {
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const input = useRef(null)

  async function send(files) {
    if (!files?.length) return
    setBusy(true); setErr('')
    try {
      let last = null
      for (const f of files) last = await api.upload(f)
      onUploaded?.(last)
    } catch (e) {
      setErr(String(e.message || e))
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }

  return (
    <>
      <label
        className={`drop ${over ? 'over' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault(); setOver(false)
          send(Array.from(e.dataTransfer.files))
        }}
      >
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          onChange={(e) => send(Array.from(e.target.files))}
        />
        {busy ? 'Uploading' : (
          <>
            Drop a scan or PDF
            <br />
            <span style={{ fontSize: 10.5 }}>or click to choose</span>
          </>
        )}
      </label>
      {err && (
        <div className="muted" style={{ color: 'var(--trip)', fontSize: 11, marginTop: 6 }}>
          {err}
        </div>
      )}
    </>
  )
}
