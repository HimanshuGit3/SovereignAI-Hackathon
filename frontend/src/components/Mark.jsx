/* Identity derived from P&ID symbology: a process line running into an
   instrument bubble, with the equipment square upstream. It draws itself
   on load the way a plotter would lay it down. */

export default function Mark({ size = 30 }) {
  return (
    <svg className="mark" width={size} height={size} viewBox="0 0 40 40"
         fill="none" aria-hidden="true">
      <line className="m-line" x1="2" y1="20" x2="38" y2="20" />
      <rect className="m-eq" x="7" y="14" width="12" height="12" />
      <circle className="m-bubble" cx="29.5" cy="20" r="7.5" />
      <circle className="m-core" cx="29.5" cy="20" r="2.4" />
    </svg>
  )
}
