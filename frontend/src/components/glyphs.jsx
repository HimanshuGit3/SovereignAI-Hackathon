/* P&ID-style glyphs drawn inline. No icon library: this project's pitch
   is an audited dependency tree, and generic app icons would read as
   clip art next to real instrument symbology. Each glyph is centred on
   (0,0) so it can be dropped into a node with a transform. */

export function Glyph({ kind }) {
  const P = { fill: 'none', strokeWidth: 1.5, strokeLinecap: 'round',
              strokeLinejoin: 'round' }
  switch (kind) {
    case 'ingest':   // a sheet being read
      return (
        <g className="gly" {...P}>
          <path d="M-7 -8 h9 l5 5 v11 h-14 z" />
          <path d="M2 -8 v5 h5" />
          <path d="M-4 0 h7 M-4 4 h7" />
        </g>
      )
    case 'kb':       // stacked records with a lookup mark
      return (
        <g className="gly" {...P}>
          <ellipse cx="0" cy="-6" rx="8" ry="3" />
          <path d="M-8 -6 v6 c0 1.7 3.6 3 8 3 s8 -1.3 8 -3 v-6" />
          <path d="M-8 0 v6 c0 1.7 3.6 3 8 3 s8 -1.3 8 -3 v-6" />
        </g>
      )
    case 'calc':     // orifice plate with flow
      return (
        <g className="gly" {...P}>
          <path d="M-9 -7 v14 M9 -7 v14" />
          <path d="M-9 0 h4 M5 0 h4" />
          <path d="M-2 -5 v10 M2 -5 v10" />
        </g>
      )
    case 'sandbox':  // shielded enclosure
      return (
        <g className="gly" {...P}>
          <path d="M0 -9 l8 3 v6 c0 4.5 -3.4 7.8 -8 9 c-4.6 -1.2 -8 -4.5 -8 -9 v-6 z" />
          <path d="M-3.5 0 l2.5 2.5 l4.5 -5" />
        </g>
      )
    case 'docgen':   // centrifugal impeller
      return (
        <g className="gly" {...P}>
          <circle cx="0" cy="0" r="2.5" />
          <path d="M0 -2.5 c4 -3 8 -1 8 3" />
          <path d="M2.2 1.3 c1.5 4.7 -1.3 7.8 -5 6.7" />
          <path d="M-2.2 1.3 c-5.5 1.7 -7.5 -2 -5.5 -5.3" />
        </g>
      )
    case 'router':   // three-way selector
      return (
        <g className="gly" {...P}>
          <path d="M-9 0 h6" />
          <circle cx="0" cy="0" r="3" />
          <path d="M3 0 h6 M2.2 -2.2 l4.5 -5 M2.2 2.2 l4.5 5" />
        </g>
      )
    case 'orch':     // vessel with agitator
      return (
        <g className="gly" {...P}>
          <path d="M0 -11 v6" />
          <path d="M-5 -5 h10" />
          <path d="M0 -5 v9" />
          <path d="M-6 4 q6 5 12 0" />
          <circle cx="0" cy="7" r="1.2" fill="currentColor" stroke="none" />
        </g>
      )
    default:
      return null
  }
}

export function NavIcon({ id }) {
  const P = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.7,
              strokeLinecap: 'round', strokeLinejoin: 'round' }
  const d = {
    dashboard: <><path d="M3 13 a8 8 0 0 1 16 0" /><path d="M11 13 l4.5 -4.5" /><circle cx="11" cy="13" r="1.4" /></>,
    workbench: <><rect x="3" y="3" width="7" height="7" rx="1.5" />
                 <rect x="12" y="3" width="7" height="7" rx="1.5" />
                 <rect x="3" y="12" width="7" height="7" rx="1.5" />
                 <rect x="12" y="12" width="7" height="7" rx="1.5" /></>,
    sovereignty: <><path d="M11 2 l7 3 v6 c0 5 -3 8.5 -7 10 c-4 -1.5 -7 -5 -7 -10 v-6 z" />
                   <path d="M8 11 l2.2 2.2 l4.3 -4.6" /></>,
    knowledge: <><path d="M4 4.5 c3 -1.5 6 -1.5 7 0 v13 c-1 -1.5 -4 -1.5 -7 0 z" />
                 <path d="M18 4.5 c-3 -1.5 -6 -1.5 -7 0 v13 c1 -1.5 4 -1.5 7 0 z" /></>,
    models: <><path d="M11 2.5 l8 4.5 v9 l-8 4.5 l-8 -4.5 v-9 z" />
              <path d="M11 11.5 l8 -4.5 M11 11.5 v9 M11 11.5 l-8 -4.5" /></>,
  }[id]
  return <svg className="navico" width="21" height="22" viewBox="0 0 22 22" {...P}>{d}</svg>
}
