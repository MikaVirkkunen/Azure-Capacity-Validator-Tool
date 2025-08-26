import React from 'react'
import { Typography, Chip, Stack, Divider, Table, TableHead, TableRow, TableCell, TableBody, Box } from '@mui/material'

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
      {Array.isArray(results.zone_mapping) && results.zone_mapping.length > 0 && (
        <>
          <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle1" gutterBottom>Zone Mapping (Logical ➜ Physical)</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {results.zone_mapping.map((m: any, i: number) => (
                <Chip key={i} label={`${m.logicalZone} ➜ ${m.physicalZone}`} size="small" />
              ))}
            </Stack>
        </>
      )}
      {!results.zone_mapping?.length && results.zone_mapping_status && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle1" gutterBottom>Zone Mapping (Logical ➜ Physical)</Typography>
          <Typography variant="body2" color="text.secondary">
            {results.zone_mapping_status === 'unavailable' ? 'No logical → physical zone mapping published for this region or insufficient permissions.' : results.zone_mapping_status}
          </Typography>
        </>
      )}
      {Array.isArray(results.quota_summary) && results.quota_summary.length > 0 && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle1" gutterBottom>Quota Summary (Compute – Plan Impact)</Typography>
          <Box sx={{ overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell align="right">Current</TableCell>
                  <TableCell align="right">Limit</TableCell>
                  <TableCell align="right">Remaining</TableCell>
                  <TableCell align="right">Planned Add</TableCell>
                  <TableCell align="right">Post-Plan Remaining</TableCell>
                  <TableCell align="right">Used %</TableCell>
                  <TableCell align="right">Used % After</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {results.quota_summary.map((q: any, i: number) => {
                  const pct = q.percent_used ?? null
          const postPct = q.percent_used_after_request ?? null
          const warn = (postPct !== null ? postPct : pct) !== null && ((postPct ?? pct) >= 80)
                  return (
                    <TableRow key={i} sx={warn ? { bgcolor: 'warning.light' } : undefined}>
                      <TableCell sx={{ minWidth: 220 }}>{q.name}</TableCell>
                      <TableCell align="right">{q.current}</TableCell>
                      <TableCell align="right">{q.limit}</TableCell>
                      <TableCell align="right">{q.remaining}</TableCell>
            <TableCell align="right">{q.requested_additional ?? 0}</TableCell>
            <TableCell align="right">{q.remaining_after_request ?? ''}</TableCell>
            <TableCell align="right">{pct !== null ? `${pct}%` : ''}</TableCell>
            <TableCell align="right">{postPct !== null ? `${postPct}%` : ''}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
      Highlighted rows indicate projected utilization &gt;=80%; consider requesting increases before scaling.
          </Typography>
        </>
      )}
      {(!results.quota_summary || results.quota_summary.length === 0) && results.quota_status && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle1" gutterBottom>Quota Summary (Compute)</Typography>
          <Typography variant="body2" color="text.secondary">
            {results.quota_status === 'empty' && 'No quotas with limits found to display.'}
            {results.quota_status === 'unavailable' && 'Quota data unavailable (permission, region, or API error).'}
          </Typography>
        </>
      )}
    </div>
  )
}