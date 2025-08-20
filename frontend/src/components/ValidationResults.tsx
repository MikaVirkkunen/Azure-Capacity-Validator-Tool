import React from 'react'

type Props = {
  results: any
}

export default function ValidationResults({ results }: Props) {
  return (
    <section style={{ marginTop: 16, border: '1px solid #ddd', padding: 12, borderRadius: 8 }}>
      <h3>Validation Results</h3>
      <div>Region: {results.region}</div>
      <div>Subscription: {results.subscription_id || 'Default'}</div>

      <ul>
        {results.results.map((r: any, idx: number) => (
          <li key={idx} style={{ marginTop: 8 }}>
            <div><b>{r.resource.resource_type}</b> — {r.resource.sku || '(no sku)'} — qty {r.resource.quantity || 1}</div>
            <div>Status: <b>{r.status}</b></div>
            {r.details && <div>Details: {r.details}</div>}
          </li>
        ))}
      </ul>
    </section>
  )
}