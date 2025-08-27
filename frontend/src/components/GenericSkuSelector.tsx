import React, { useEffect, useState } from 'react'
import { FormControl, InputLabel, Select, MenuItem } from '@mui/material'

interface Item { name: string; details?: string }
interface Props {
  resourceType: string
  region: string
  subscriptionId?: string
  value?: string
  onChange: (v: string) => void
  label?: string
  size?: 'small' | 'medium'
}

export default function GenericSkuSelector({ resourceType, region, subscriptionId, value, onChange, label = 'SKU', size = 'small' }: Props) {
  const [items, setItems] = useState<Item[]>([])

  useEffect(() => {
    if (!resourceType || !region) return
    const url = new URL('/api/resource-skus', window.location.origin)
    url.searchParams.set('resource_type', resourceType)
    url.searchParams.set('location', region)
    if (subscriptionId) url.searchParams.set('subscription_id', subscriptionId)
    fetch(url.toString().replace(window.location.origin, ''))
      .then(r => r.json())
      .then(data => {
        const list = data.items || []
        setItems(list)
        // Auto-select first if none chosen
        if (!value && list.length > 0) {
          onChange(list[0].name)
        }
      })
      .catch(() => setItems([]))
  }, [resourceType, region, subscriptionId])

  return (
    <FormControl sx={{ minWidth: 200 }} size={size}>
      <InputLabel id={`sku-${label}`}>{label}</InputLabel>
      <Select labelId={`sku-${label}`} label={label} value={value || ''} onChange={(e) => onChange(String(e.target.value))}>
        <MenuItem value=""><em>None</em></MenuItem>
        {items.map(it => (
          <MenuItem key={it.name} value={it.name}>{it.name}{it.details ? ` (${it.details})` : ''}</MenuItem>
        ))}
      </Select>
    </FormControl>
  )
}
