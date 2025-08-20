import React, { useEffect, useState } from 'react'

type Props = {
  region: string
  subscriptionId?: string
  value?: string
  onChange: (size: string) => void
}

export default function VMSizeSelector({ region, subscriptionId, value, onChange }: Props) {
  const [sizes, setSizes] = useState<any[]>([])

  useEffect(() => {
    if (!region) return
    const url = new URL('/api/compute/vm-sizes', window.location.origin)
    url.searchParams.set('location', region)
    if (subscriptionId) url.searchParams.set('subscription_id', subscriptionId)
    fetch(url.toString().replace(window.location.origin, ''))
      .then(r => r.json())
      .then(setSizes)
      .catch(console.error)
  }, [region, subscriptionId])

  return (
    <select value={value || ''} onChange={e => onChange(e.target.value)}>
      <option value="">Select VM size</option>
      {sizes.map(s => (
        <option key={s.name} value={s.name}>
          {s.name} ({Math.round(s.memory_in_mb/1024)} GB, {s.number_of_cores} vCPU)
        </option>
      ))}
    </select>
  )
}