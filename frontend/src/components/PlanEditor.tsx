import React, { useState } from 'react'
import VMSizeSelector from './VMSizeSelector'
import { Box, Stack, Typography, Select, MenuItem, TextField, Button, IconButton, Paper, InputLabel, FormControl } from '@mui/material'
import DeleteIcon from '@mui/icons-material/Delete'

type PlanResource = {
  resource_type: string
  sku?: string
  features?: Record<string, any>
  quantity?: number
}

type Props = {
  plan: { region: string, resources: PlanResource[] }
  setPlan: (p: any) => void
  region: string
  subscriptionId?: string
}

export default function PlanEditor({ plan, setPlan, region, subscriptionId }: Props) {
  const [newType, setNewType] = useState<string>('Microsoft.Compute/virtualMachines')
  const [newSku, setNewSku] = useState<string>('')
  const [customType, setCustomType] = useState<string>('')

  const addResource = () => {
    const typeToUse = newType === 'custom' ? (customType || '').trim() : newType
    if (!typeToUse) return
    const res: PlanResource = { resource_type: typeToUse, sku: newSku || undefined, quantity: 1, features: {} }
    setPlan({ ...plan, resources: [...plan.resources, res] })
    setNewSku('')
    if (newType === 'custom') setCustomType('')
  }

  const updateResource = (idx: number, patch: Partial<PlanResource>) => {
    const updated = plan.resources.map((r, i) => i === idx ? { ...r, ...patch } : r)
    setPlan({ ...plan, resources: updated })
  }

  const removeResource = (idx: number) => {
    const updated = plan.resources.filter((_, i) => i !== idx)
    setPlan({ ...plan, resources: updated })
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Plan</Typography>

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <FormControl sx={{ minWidth: 280 }}>
          <InputLabel id="rtype-label">Resource Type</InputLabel>
          <Select labelId="rtype-label" label="Resource Type" value={newType} onChange={(e) => {
            const v = String(e.target.value)
            setNewType(v)
            // set sensible default SKUs
            if (v.toLowerCase() === 'microsoft.keyvault/vaults') setNewSku('standard')
            else if (v.toLowerCase() === 'microsoft.compute/virtualmachines') setNewSku('')
            else if (v.toLowerCase() === 'microsoft.compute/disks') setNewSku('Premium_LRS')
            else setNewSku('')
          }}>
            <MenuItem value="Microsoft.Compute/virtualMachines">Microsoft.Compute/virtualMachines</MenuItem>
            <MenuItem value="Microsoft.Compute/disks">Microsoft.Compute/disks</MenuItem>
            <MenuItem value="Microsoft.KeyVault/vaults">Microsoft.KeyVault/vaults</MenuItem>
            <MenuItem value="custom">Custom (enter RP/type)</MenuItem>
          </Select>
        </FormControl>

        {newType === 'custom' && (
          <TextField
            sx={{ minWidth: 320 }}
            placeholder="e.g., Microsoft.Storage/storageAccounts"
            value={customType}
            onChange={(e) => setCustomType(e.target.value)}
            label="Custom Type"
          />
        )}

        {newType.toLowerCase() === 'microsoft.compute/virtualmachines' ? (
          <VMSizeSelector region={region} subscriptionId={subscriptionId} value={newSku} onChange={setNewSku} />
        ) : newType.toLowerCase() === 'microsoft.keyvault/vaults' ? (
          <FormControl sx={{ minWidth: 200 }} size="small">
            <InputLabel id="kv-sku-label">Key Vault SKU</InputLabel>
            <Select labelId="kv-sku-label" label="Key Vault SKU" value={newSku} onChange={(e) => setNewSku(String(e.target.value))}>
              <MenuItem value="standard">Standard</MenuItem>
              <MenuItem value="premium">Premium</MenuItem>
            </Select>
          </FormControl>
        ) : (
          <TextField
            placeholder={newType === 'custom' ? 'Optional SKU' : 'Disk SKU (e.g., Premium_LRS)'}
            value={newSku}
            onChange={(e) => setNewSku(e.target.value)}
            label="SKU/Size"
          />
        )}

        <Button variant="contained" onClick={addResource}>Add</Button>
      </Stack>

      {plan.resources.length === 0 && <Typography color="text.secondary">No resources yet.</Typography>}

      <Stack spacing={1}>
        {plan.resources.map((r, idx) => (
          <Paper key={idx} variant="outlined" sx={{ p: 1.5 }}>
            <Typography><b>Type:</b> {r.resource_type}</Typography>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center" sx={{ mt: 1 }}>
              <Typography variant="body2" sx={{ minWidth: 72 }}>SKU/Size</Typography>
              {r.resource_type.toLowerCase() === 'microsoft.compute/virtualmachines' ? (
                <VMSizeSelector region={region} subscriptionId={subscriptionId} value={r.sku} onChange={(v) => updateResource(idx, { sku: v })} />
              ) : r.resource_type.toLowerCase() === 'microsoft.keyvault/vaults' ? (
                <FormControl sx={{ minWidth: 200 }} size="small">
                  <InputLabel id={`kv-sku-${idx}`}>Key Vault SKU</InputLabel>
                  <Select labelId={`kv-sku-${idx}`} label="Key Vault SKU" value={(r.sku || 'standard').toLowerCase()} onChange={(e) => updateResource(idx, { sku: String(e.target.value) })}>
                    <MenuItem value="standard">Standard</MenuItem>
                    <MenuItem value="premium">Premium</MenuItem>
                  </Select>
                </FormControl>
              ) : (
                <TextField value={r.sku || ''} onChange={(e) => updateResource(idx, { sku: e.target.value })} size="small" />
              )}
              <Typography variant="body2" sx={{ minWidth: 48 }}>Qty</Typography>
              <TextField type="number" inputProps={{ min: 1 }} value={r.quantity || 1} onChange={(e) => updateResource(idx, { quantity: Number(e.target.value) })} size="small" sx={{ width: 100 }} />
              <IconButton color="error" onClick={() => removeResource(idx)} aria-label="remove"><DeleteIcon /></IconButton>
            </Stack>
          </Paper>
        ))}
      </Stack>
    </Box>
  )
}