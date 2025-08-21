import React from 'react'
import { Typography, Chip, Stack, Divider } from '@mui/material'

type Props = {
  results: any
}

export default function ValidationResults({ results }: Props) {
  return (
    <div>
      <Typography variant="h6" gutterBottom>Validation Results</Typography>
      <Typography variant="body2">Region: {results.region}</Typography>
      <Typography variant="body2" sx={{ mb: 1 }}>Subscription: {results.subscription_id || 'Default'}</Typography>
      <Divider sx={{ mb: 1 }} />
      <Stack spacing={1}>
        {results.results.map((r: any, idx: number) => {
          const ok = (String(r.status || '').toLowerCase() === 'ok' || String(r.status || '').toLowerCase() === 'available')
          return (
            <Stack key={idx} direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems="center">
              <Typography sx={{ flex: 1 }}>
                <b>{r.resource.resource_type}</b> — {r.resource.sku || '(no sku)'} — qty {r.resource.quantity || 1}
              </Typography>
              <Chip label={r.status} color={ok ? 'success' : 'error'} size="small" />
              {r.details && <Typography variant="body2" color="text.secondary">{r.details}</Typography>}
            </Stack>
          )
        })}
      </Stack>
    </div>
  )
}