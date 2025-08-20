import React, { useEffect, useState } from 'react'
import RegionSelector from './components/RegionSelector'
import VMSizeSelector from './components/VMSizeSelector'
import PlanEditor from './components/PlanEditor'
import ValidationResults from './components/ValidationResults'

type Subscription = { subscription_id: string, display_name?: string }

export default function App() {
  const [subs, setSubs] = useState<Subscription[]>([])
  const [subscriptionId, setSubscriptionId] = useState<string | undefined>(undefined)
  const [region, setRegion] = useState<string>('westeurope')
  const [plan, setPlan] = useState<any>({ region: 'westeurope', resources: [] })
  const [results, setResults] = useState<any>(null)
  const [aiPrompt, setAiPrompt] = useState<string>('')

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
    const res = await fetch('/api/ai/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: aiPrompt })
    })
    const data = await res.json()
    // normalize into editor format
    setRegion(data.region || 'westeurope')
    setPlan({ region: data.region || 'westeurope', resources: data.resources || [] })
  }

  return (
    <div style={{ padding: 24, fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial' }}>
      <h1>Azure Capacity Validator</h1>

      <section style={{ marginBottom: 16 }}>
        <label>Subscription:&nbsp;</label>
        <select value={subscriptionId || ''} onChange={e => setSubscriptionId(e.target.value || undefined)}>
          <option value=''>Default</option>
          {subs.map(s => (
            <option key={s.subscription_id} value={s.subscription_id}>
              {s.display_name || s.subscription_id}
            </option>
          ))}
        </select>
      </section>

      <RegionSelector subscriptionId={subscriptionId} value={region} onChange={setRegion} />

      <section style={{ margin: '16px 0', padding: 12, border: '1px solid #ddd', borderRadius: 8 }}>
        <h3>AI Plan Generator</h3>
        <textarea
          value={aiPrompt}
          onChange={(e) => setAiPrompt(e.target.value)}
          rows={4}
          style={{ width: '100%' }}
          placeholder="Describe your architecture (e.g., 3 VM Standard_D4s_v5 and Premium_LRS disks)..."
        />
        <div style={{ marginTop: 8 }}>
          <button onClick={runAI}>Generate Plan with Azure OpenAI</button>
        </div>
      </section>

      <PlanEditor plan={plan} setPlan={setPlan} region={region} subscriptionId={subscriptionId} />

      <div style={{ marginTop: 16 }}>
        <button onClick={runValidation}>Validate Plan</button>
      </div>

      {results && <ValidationResults results={results} />}
    </div>
  )
}