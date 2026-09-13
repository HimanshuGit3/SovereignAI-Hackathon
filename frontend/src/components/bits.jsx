// Small shared pieces. Kept together so the screens stay readable.

export function Tag({ kind = '', children }) {
  return <span className={`tag ${kind}`}>{children}</span>
}

export function Lamp({ state = 'idle', children }) {
  return <span className={`lamp ${state}`}>{children}</span>
}

export function Zone({ title, right, children }) {
  return (
    <div className="zone">
      {(title || right) && (
        <div className="spread">
          <div className="zone-h">{title}</div>
          {right}
        </div>
      )}
      {children}
    </div>
  )
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>
}

// Scores are the honest part of retrieval: always show the number.
export function Score({ value }) {
  const kind = value >= 0.7 ? 'service' : value >= 0.58 ? 'info' : 'alarm'
  return <Tag kind={kind}>{value.toFixed(3)}</Tag>
}
