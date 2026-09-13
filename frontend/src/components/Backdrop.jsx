import { useEffect, useRef } from 'react'

/* Ambient plant network.
   Nodes sit on a relaxed grid, joined by orthogonal pipe runs. Product
   travels the runs continuously, junctions flare as it passes, and a
   slow survey sweep crosses the field every twelve seconds, briefly
   illuminating whatever it touches.
   Low contrast throughout: this must never compete with the canvas. */

const NAVY = '11,37,69'
const BLUE = '0,102,255'
const GREEN = '0,168,120'

export default function Backdrop() {
  const ref = useRef(null)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const cv = ref.current
    const ctx = cv.getContext('2d')
    const DPR = Math.min(window.devicePixelRatio || 1, 2)
    let raf, w, h, t = 0
    let nodes = [], runs = [], flows = [], sweep = -0.25

    function build() {
      w = cv.clientWidth; h = cv.clientHeight
      cv.width = w * DPR; cv.height = h * DPR
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0)

      const gx = 168, gy = 132
      const cols = Math.ceil(w / gx) + 2
      const rows = Math.ceil(h / gy) + 2

      nodes = []
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          nodes.push({
            x: c * gx - gx / 2 + (r % 2 ? gx / 2 : 0) + (Math.random() - .5) * 26,
            y: r * gy - gy / 2 + (Math.random() - .5) * 22,
            r: 1.4 + Math.random() * 1.6,
            ph: Math.random() * 6.28,
            sp: .5 + Math.random() * .7,
            major: Math.random() > 0.82,
          })
        }
      }

      // orthogonal pipe runs between near neighbours
      runs = []
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j]
          const d = Math.hypot(a.x - b.x, a.y - b.y)
          if (d > 190 || Math.random() > .5) continue
          runs.push({ a, b, mx: a.x + (b.x - a.x) * .5, len: d })
        }
      }

      flows = Array.from({ length: 9 }, () => ({
        run: runs[(Math.random() * runs.length) | 0],
        u: Math.random(),
        sp: .0016 + Math.random() * .0022,
        green: Math.random() > .55,
      }))
    }

    function pipe(run) {
      const { a, b, mx } = run
      ctx.beginPath()
      ctx.moveTo(a.x, a.y)
      ctx.lineTo(mx, a.y)
      ctx.lineTo(mx, b.y)
      ctx.lineTo(b.x, b.y)
    }

    function pointOn(run, u) {
      const { a, b, mx } = run
      const l1 = Math.abs(mx - a.x), l2 = Math.abs(b.y - a.y), l3 = Math.abs(b.x - mx)
      const total = l1 + l2 + l3 || 1
      let d = u * total
      if (d < l1) return { x: a.x + Math.sign(mx - a.x) * d, y: a.y }
      d -= l1
      if (d < l2) return { x: mx, y: a.y + Math.sign(b.y - a.y) * d }
      d -= l2
      return { x: mx + Math.sign(b.x - mx) * d, y: b.y }
    }

    function frame() {
      ctx.clearRect(0, 0, w, h)
      t += 1
      sweep += 0.0011
      if (sweep > 1.3) sweep = -0.25
      const sx = sweep * w

      // pipe runs, brightened near the sweep
      ctx.lineWidth = 1
      for (const run of runs) {
        const near = Math.max(0, 1 - Math.abs(run.mx - sx) / 240)
        ctx.strokeStyle = `rgba(${NAVY},${0.030 + near * 0.085})`
        pipe(run); ctx.stroke()
      }

      // the survey sweep itself
      const g = ctx.createLinearGradient(sx - 150, 0, sx + 60, 0)
      g.addColorStop(0, `rgba(${BLUE},0)`)
      g.addColorStop(.72, `rgba(${BLUE},.055)`)
      g.addColorStop(1, `rgba(${BLUE},0)`)
      ctx.fillStyle = g
      ctx.fillRect(sx - 150, 0, 210, h)

      // nodes
      for (const n of nodes) {
        const k = .5 + .5 * Math.sin(t * .005 * n.sp + n.ph)
        const near = Math.max(0, 1 - Math.abs(n.x - sx) / 170)
        const a = (n.major ? .16 : .09) + k * .07 + near * .34
        ctx.fillStyle = `rgba(${near > .35 ? BLUE : NAVY},${a})`
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r + near * 1.3, 0, 7); ctx.fill()

        if (n.major) {
          ctx.strokeStyle = `rgba(${NAVY},${.05 + near * .22})`
          ctx.lineWidth = 1
          ctx.beginPath(); ctx.arc(n.x, n.y, 7 + k * 2.5, 0, 7); ctx.stroke()
        }
      }

      // product travelling the runs
      for (const f of flows) {
        f.u += f.sp
        if (f.u >= 1) {
          f.u = 0
          f.run = runs[(Math.random() * runs.length) | 0]
          f.green = Math.random() > .55
        }
        if (!f.run) continue
        const p = pointOn(f.run, f.u)
        const fade = Math.sin(f.u * Math.PI)
        const col = f.green ? GREEN : BLUE

        const rg = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 20)
        rg.addColorStop(0, `rgba(${col},${.22 * fade})`)
        rg.addColorStop(1, `rgba(${col},0)`)
        ctx.fillStyle = rg
        ctx.beginPath(); ctx.arc(p.x, p.y, 20, 0, 7); ctx.fill()

        ctx.fillStyle = `rgba(${col},${.6 * fade})`
        ctx.beginPath(); ctx.arc(p.x, p.y, 1.9, 0, 7); ctx.fill()
      }

      raf = requestAnimationFrame(frame)
    }

    const onVis = () => {
      cancelAnimationFrame(raf)
      if (!document.hidden) raf = requestAnimationFrame(frame)
    }

    build(); frame()
    window.addEventListener('resize', build)
    document.addEventListener('visibilitychange', onVis)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', build)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [])

  return (
    <div className="backdrop" aria-hidden="true">
      <canvas ref={ref} />
      <div className="wash w1" />
      <div className="wash w2" />
      <div className="vignette" />
    </div>
  )
}
