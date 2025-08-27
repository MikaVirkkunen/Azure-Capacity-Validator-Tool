import React, { useEffect, useState } from 'react'
import { FormControl, InputLabel, Select, MenuItem } from '@mui/material'

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
      .then((list) => {
        setSizes(list)
        if (!value && list && list.length > 0) {
          onChange(list[0].name)
        }
      })
      .catch(console.error)
  }, [region, subscriptionId])

  return (
    <FormControl sx={{ minWidth: 260 }} size="small">
      <InputLabel id="vm-size-label">VM Size</InputLabel>
      <Select labelId="vm-size-label" label="VM Size" value={value || ''} onChange={(e) => onChange(String(e.target.value))}>
        <MenuItem value=""><em>Select VM size</em></MenuItem>
        {sizes.map((s) => (
          <MenuItem key={s.name} value={s.name}>
            {s.name} ({Math.round(s.memory_in_mb/1024)} GB, {s.number_of_cores} vCPU)
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  )
}