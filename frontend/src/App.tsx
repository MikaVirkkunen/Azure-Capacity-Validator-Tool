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
  // Default region changed to Sweden Central (swedencentral)
  const [region, setRegion] = useState<string>('swedencentral')
  const [plan, setPlan] = useState<any>({ region: 'swedencentral', resources: [] })
  const [results, setResults] = useState<any>(null)
  const [aiPrompt, setAiPrompt] = useState<string>('')
  const [aiLoading, setAiLoading] = useState<boolean>(false)
  const [aiPhase, setAiPhase] = useState<string>('')
  const [validating, setValidating] = useState<boolean>(false)
  const [validationPhase, setValidationPhase] = useState<string>('')
  const [aiError, setAiError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/subscriptions').then(r => r.json()).then(setSubs).catch(console.error)
  }, [])

  const runValidation = async () => {
    setValidating(true)
    setValidationPhase('Validating plan')
    try {
      const payload = { ...plan, region, subscription_id: subscriptionId }
      const res = await fetch('/api/validate-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      setValidationPhase('Processing results')
      setResults(data)
    } finally {
      setValidationPhase('')
      setValidating(false)
    }
  }

  const runAI = async () => {
    setAiError(null)
    setAiLoading(true)
    setAiPhase('Analyzing architecture prompt')
    try {
      const res = await fetch('/api/ai/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: aiPrompt })
      })
      setAiPhase('Extracting resource providers & SKUs')
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const detail = (data && (data.detail || data.message)) || `HTTP ${res.status}`
        setAiError(`AI analysis failed: ${detail}. Configure Azure OpenAI in backend env vars.`)
        return
      }
      setAiPhase('Building draft plan')
      setPlan({ region, resources: data.resources || [] })
      setAiPhase('Completed')
    } catch (e: any) {
      setAiError(e?.message || 'Unexpected error calling AI analysis API')
    } finally {
      setTimeout(() => { setAiPhase(''); setAiLoading(false) }, 600)
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
            {aiLoading ? (aiPhase || 'Analyzing…') : 'Analyze Architecture with Azure OpenAI'}
          </Button>
        </Stack>
        {aiError && (
          <Alert severity="error" sx={{ mt: 1 }}>{aiError}</Alert>
        )}
        {aiLoading && aiPhase && !aiError && (
          <Typography variant="caption" sx={{ mt: 1, display: 'block' }}>{aiPhase}</Typography>
        )}
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <PlanEditor plan={plan} setPlan={setPlan} region={region} subscriptionId={subscriptionId} />
        <Stack direction="row" sx={{ mt: 2 }}>
          <Button variant="contained" onClick={runValidation} disabled={validating}>
            {validating ? (validationPhase || 'Validating…') : 'Validate Plan'}
          </Button>
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