import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import Mark from './components/Mark.jsx'
import Backdrop from './components/Backdrop.jsx'
import { NavIcon } from './components/glyphs.jsx'
import Dashboard from './components/Dashboard.jsx'
import Workbench from './components/Workbench.jsx'
import Sovereignty from './components/Sovereignty.jsx'
import Knowledge from './components/Knowledge.jsx'
import Models from './components/Models.jsx'

const SCREENS = [
  { id: 'dashboard', label: 'Dashboard' },
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
    <>
    <Backdrop />
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
          <div className="classbar">
            <svg width="13" height="14" viewBox="0 0 14 15" fill="none"
                 stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"
                 strokeLinejoin="round">
              <path d="M7 1 l5.2 2.2 v4.3 c0 3.6 -2.2 6.2 -5.2 7.3
                       c-3 -1.1 -5.2 -3.7 -5.2 -7.3 v-4.3 z" />
              <path d="M4.8 7.4 l1.6 1.6 l3 -3.3" />
            </svg>
            <span>Confidential &mdash; processed on premises</span>
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

      <div className="shell">
        <nav className="sidebar">
          {SCREENS.map((s) => (
            <button key={s.id} aria-current={screen === s.id}
                    onClick={() => setScreen(s.id)}>
              <NavIcon id={s.id} />
              <span>{s.label}</span>
            </button>
          ))}
          <div className="side-foot">
            <div className="side-card">
              <div className="sc-title">SovereignAI</div>
              <div className="sc-sub">Autonomous intelligence for confidential work</div>
            </div>
          </div>
        </nav>

      <main>
        {screen === 'dashboard' && <Dashboard egress={egress} health={health} models={models} />}
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
    </div>
    </>
  )
}
