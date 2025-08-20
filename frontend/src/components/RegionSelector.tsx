import React, { useEffect, useState } from 'react'

type Props = {
  subscriptionId?: string
  value: string
  onChange: (v: string) => void
}

export default function RegionSelector({ subscriptionId, value, onChange }: Props) {
  const [regions, setRegions] = useState<any[]>([])

  useEffect(() => {
    const url = new URL('/api/locations', window.location.origin)
    if (subscriptionId) url.searchParams.set('subscription_id', subscriptionId)
    fetch(url.toString().replace(window.location.origin, ''))
      .then(r => r.json())
      .then(setRegions)
      .catch(console.error)
  }, [subscriptionId])

  return (
    <section style={{ marginBottom: 16 }}>
      <label>Region:&nbsp;</label>
      <select value={value} onChange={e => onChange(e.target.value)}>
        {regions.map(r => (
          <option key={r.name} value={r.name}>{r.display_name || r.name}</option>
        ))}
      </select>
    </section>
  )
}