import React, { useEffect, useState } from 'react'
import { FormControl, InputLabel, Select, MenuItem } from '@mui/material'

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
    <FormControl fullWidth>
      <InputLabel id="region-label">Region</InputLabel>
      <Select
        labelId="region-label"
        label="Region"
        value={value}
        onChange={(e) => onChange(String(e.target.value))}
      >
        {regions.map((r) => (
          <MenuItem key={r.name} value={r.name}>
            {r.display_name || r.name}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  )
}