import { ms } from '../api.js'

/* The one dark surface in the product. Everything a judge needs to
   believe the sovereignty claim is on screen at all times, alongside
   what the GPU is actually holding. */

export default function InstrumentRail({ egress, health, models, summary, running }) {
  const external = egress?.external_count ?? 0
  const total = egress?.total_requests ?? 0
  const clean = external === 0
  const resident = (models || []).filter((m) => m.resident)
  const vram = resident.reduce((a, m) => a + (m.vram_gb || 0), 0)

  return (
    <aside className="rail-r col panel">
      <div className="panel-head">
        <h3>Egress</h3>
        <span className="note">{total} calls audited</span>
      </div>

      <div className={`reading ${clean ? 'state-service' : 'state-trip'}`}>
        <span className="value">{external}</span>
        <span className="unit">
          external<br />destinations
        </span>
      </div>

      <div className="panel-body" style={{ paddingTop: 0 }}>
        <div className="rowlist">
          {(egress?.destinations || []).map((d) => (
            <div key={d}>
              <span className="lamp on" /> <b>{d}</b>
            </div>
          ))}
          {!egress?.destinations?.length && <div>no traffic yet</div>}
        </div>
        <div style={{ marginTop: 12, fontSize: 11, color: 'var(--panel-dim)', lineHeight: 1.6 }}>
          Classified by address, not by allowlist. Anything routable counts
          as external.
        </div>
      </div>

      <div className="panel-head" style={{ borderTop: '1px solid var(--panel-rule)' }}>
        <h3>Inference node</h3>
        <span className="note">{vram ? `${vram.toFixed(2)} GB VRAM` : 'idle'}</span>
      </div>

      <div className="panel-body" style={{ paddingTop: 8 }}>
        <div className="rowlist">
          {(models || []).map((m) => (
            <div key={m.id} className="row" style={{ gap: 8 }}>
              <span className={`lamp ${m.resident ? 'on' : 'idle'}`} />
              <b className="grow" style={{ color: m.resident ? undefined : 'var(--panel-dim)' }}>
                {m.name}
              </b>
              <span>{m.role}</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--panel-dim)' }}>
          {health?.inference_endpoint}
        </div>
      </div>

      {(summary || running) && (
        <>
          <div className="panel-head" style={{ borderTop: '1px solid var(--panel-rule)' }}>
            <h3>Last run</h3>
            {running && <span className="note">working</span>}
          </div>
          <div className="panel-body" style={{ paddingTop: 8 }}>
            <div className="rowlist">
              <div>steps <b>{summary?.steps ?? '-'}</b></div>
              <div>elapsed <b>{summary ? ms(summary.total_ms) : '-'}</b></div>
              <div>orchestrator <b>{summary?.orchestrator_model ?? '-'}</b></div>
              <div>delegates <b>{summary?.delegate_models?.join(', ') || 'none'}</b></div>
              <div>tools offered <b>{summary?.tools_offered?.length ?? '-'}</b></div>
            </div>
          </div>
        </>
      )}
    </aside>
  )
}
