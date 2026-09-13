import { useEffect, useRef, useState } from 'react'

/* Shown while the model is thinking or a tool is running.
   The backend cannot report progress mid-call, so rather than fake a
   percentage this counts real elapsed time and names what is actually
   happening. Honest, and it stops the UI looking frozen. */

const PHASES = [
  [0,    'Model is reading the request'],
  [2500, 'Selecting a tool'],
  [6000, 'Tool is running'],
  [12000, 'Still working — vision and document steps take longer'],
  [25000, 'Long task. Model swaps cost 12–20 s on a 4 GB card'],
]

export default function LiveStep({ n, hint }) {
  const [ms, setMs] = useState(0)
  const t0 = useRef(performance.now())

  useEffect(() => {
    const id = setInterval(() => setMs(performance.now() - t0.current), 90)
    return () => clearInterval(id)
  }, [])

  const phase = [...PHASES].reverse().find(([at]) => ms >= at)[1]

  return (
    <div className="step live">
      <div className="marker"><span className="spin-dot" /></div>
      <div className="step-head">
        <span className="name">{hint || `step ${n}`}</span>
        <span className="t mono">{(ms / 1000).toFixed(1)} s</span>
      </div>
      <div className="live-phase">
        {phase}
        <span className="ell"><i>.</i><i>.</i><i>.</i></span>
      </div>
      <div className="live-bar"><span /></div>
    </div>
  )
}
