import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import Mark from './components/Mark.jsx'
import Workbench from './components/Workbench.jsx'
import Sovereignty from './components/Sovereignty.jsx'
import Knowledge from './components/Knowledge.jsx'
import Models from './components/Models.jsx'

const SCREENS = [
  { id: 'workbench', label: 'Workbench' },
  { id: 'sovereignty', label: 'Sovereignty' },
  { id: 'knowledge', label: 'Knowledge base' },
  { id: 'models', label: 'Models' },
]

export default function App() {
  const [screen, setScreen] = useState('workbench')
  const [health, setHealth] = useState(null)
  const [egress, setEgress] = useState(null)
  const [models, setModels] = useState([])

  const refresh = useCallback(async () => {
    try { setHealth(await api.health()) } catch { setHealth(null) }
    try { setEgress(await api.egress()) } catch { /* leave last known */ }
    try { setModels((await api.models()).models) } catch { /* leave last known */ }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 6000)
    return () => clearInterval(t)
  }, [refresh])

  const external = egress?.external_count ?? 0
  const reachable = health?.inference_reachable

  return (
    <div className="app">
      <header className="titleblock">
        <div className="tb-cell tb-grow brandcell">
          <Mark size={32} />
          <div>
            <div className="tb-name">
              Sovereign<span className="wordmark-ai">AI</span> Workbench
            </div>
            <div className="tb-sub">
              On-premise agentic AI for confidential industrial work
            </div>
          </div>
        </div>

        <div className="tb-cell">
          <div className="tb-key">Inference node</div>
          <div className="tb-val">
            {health?.inference_endpoint ?? 'connecting'}
          </div>
        </div>

        <div className="tb-cell">
          <div className="tb-key">Status</div>
          <div className="tb-val">
            <span className={`lamp ${reachable ? 'on' : 'off'}`}>
              {reachable ? 'in service' : 'no inference node'}
            </span>
          </div>
        </div>

        <div className="tb-cell">
          <div className="tb-key">Egress</div>
          <div className="tb-val">
            <span className={`lamp ${external > 0 ? 'off' : 'on'}`}>
              {external > 0 ? `${external} external` : 'none external'}
            </span>
          </div>
        </div>
      </header>

      <nav className="nav">
        {SCREENS.map((s) => (
          <button
            key={s.id}
            aria-current={screen === s.id}
            onClick={() => setScreen(s.id)}
          >
            {s.label}
          </button>
        ))}
      </nav>

      <main>
        {screen === 'workbench' && (
          <Workbench
            health={health}
            models={models}
            egress={egress}
            onDone={refresh}
          />
        )}
        {screen === 'sovereignty' && <Sovereignty egress={egress} onRefresh={refresh} />}
        {screen === 'knowledge' && <Knowledge />}
        {screen === 'models' && <Models />}
      </main>
    </div>
  )
}
