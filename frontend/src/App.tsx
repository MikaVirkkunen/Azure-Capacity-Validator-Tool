import React, { useEffect, useState } from 'react'
import RegionSelector from './components/RegionSelector'
import VMSizeSelector from './components/VMSizeSelector'
import PlanEditor from './components/PlanEditor'
import ValidationResults from './components/ValidationResults'
import { Box, Container, Typography, Paper, TextField, Button, MenuItem, Select, FormControl, InputLabel, Stack, Alert } from '@mui/material'

type Subscription = { subscription_id: string, display_name?: string }

export default function App() {
  const [subs, setSubs] = useState<Subscription[]>([])
  const [subscriptionId, setSubscriptionId] = useState<string | undefined>(undefined)
  const [region, setRegion] = useState<string>('westeurope')
  const [plan, setPlan] = useState<any>({ region: 'westeurope', resources: [] })
  const [results, setResults] = useState<any>(null)
  const [aiPrompt, setAiPrompt] = useState<string>('')
  const [aiLoading, setAiLoading] = useState<boolean>(false)
  const [aiError, setAiError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/subscriptions').then(r => r.json()).then(setSubs).catch(console.error)
  }, [])

  const runValidation = async () => {
    const payload = { ...plan, region, subscription_id: subscriptionId }
    const res = await fetch('/api/validate-plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const data = await res.json()
    setResults(data)
  }

  const runAI = async () => {
    setAiError(null)
    setAiLoading(true)
    try {
      const res = await fetch('/api/ai/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: aiPrompt })
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const detail = (data && (data.detail || data.message)) || `HTTP ${res.status}`
        setAiError(`AI plan generation failed: ${detail}. Configure Azure OpenAI in backend env vars.`)
        return
      }
  // Normalize into editor format. Do not override the user's selected region.
  // Keep the currently selected region and only adopt AI region if it is explicitly provided
  // AND the current region is empty (not the case in this UI).
  setPlan({ region, resources: data.resources || [] })
    } catch (e: any) {
      setAiError(e?.message || 'Unexpected error calling AI plan API')
    } finally {
      setAiLoading(false)
    }
  }

  return (
    <Container maxWidth="lg" sx={{ py: 3 }}>
      <Typography variant="h4" fontWeight={700} gutterBottom>Azure Capacity Validator</Typography>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center">
          <FormControl sx={{ minWidth: 280 }}>
            <InputLabel id="sub-label">Subscription</InputLabel>
            <Select labelId="sub-label" label="Subscription" value={subscriptionId || ''} onChange={(e) => setSubscriptionId(String(e.target.value) || undefined)}>
              <MenuItem value="">Default</MenuItem>
              {subs.map(s => (
                <MenuItem key={s.subscription_id} value={s.subscription_id}>
                  {s.display_name || s.subscription_id}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Box flex={1}>
            <RegionSelector subscriptionId={subscriptionId} value={region} onChange={setRegion} />
          </Box>
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" gutterBottom>AI Plan Generator</Typography>
        <TextField
          value={aiPrompt}
          onChange={(e) => setAiPrompt(e.target.value)}
          multiline minRows={3}
          fullWidth
          placeholder="Describe your architecture (e.g., 3x Standard_D4s_v5 VMs, Premium_LRS disks, Key Vault, Public IP)."
        />
        <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
          <Button variant="contained" onClick={runAI} disabled={aiLoading}>
            {aiLoading ? 'Generating…' : 'Generate Plan with Azure OpenAI'}
          </Button>
        </Stack>
        {aiError && (
          <Alert severity="error" sx={{ mt: 1 }}>{aiError}</Alert>
        )}
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <PlanEditor plan={plan} setPlan={setPlan} region={region} subscriptionId={subscriptionId} />
        <Stack direction="row" sx={{ mt: 2 }}>
          <Button variant="contained" onClick={runValidation}>Validate Plan</Button>
        </Stack>
      </Paper>

      {results && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <ValidationResults results={results} />
        </Paper>
      )}
    </Container>
  )
}