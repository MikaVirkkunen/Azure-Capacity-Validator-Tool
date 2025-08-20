import React, { useState } from 'react'
import VMSizeSelector from './VMSizeSelector'

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

  const addResource = () => {
    const res: PlanResource = { resource_type: newType, sku: newSku || undefined, quantity: 1, features: {} }
    setPlan({ ...plan, resources: [...plan.resources, res] })
    setNewSku('')
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
    <section style={{ border: '1px solid #ddd', padding: 12, borderRadius: 8 }}>
      <h3>Plan</h3>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <select value={newType} onChange={e => setNewType(e.target.value)}>
          <option>Microsoft.Compute/virtualMachines</option>
          <option>Microsoft.Compute/disks</option>
        </select>

        {newType.toLowerCase() === 'microsoft.compute/virtualmachines' ? (
          <VMSizeSelector region={region} subscriptionId={subscriptionId} value={newSku} onChange={setNewSku} />
        ) : (
          <input placeholder="Disk SKU (e.g., Premium_LRS)" value={newSku} onChange={e => setNewSku(e.target.value)} />
        )}

        <button onClick={addResource}>Add</button>
      </div>

      {plan.resources.length === 0 && <div>No resources yet.</div>}

      {plan.resources.map((r, idx) => (
        <div key={idx} style={{ padding: 8, border: '1px solid #eee', marginBottom: 8, borderRadius: 6 }}>
          <div><b>Type:</b> {r.resource_type}</div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 6 }}>
            <label>SKU/Size:&nbsp;</label>
            {r.resource_type.toLowerCase() === 'microsoft.compute/virtualmachines' ? (
              <VMSizeSelector region={region} subscriptionId={subscriptionId} value={r.sku} onChange={(v) => updateResource(idx, { sku: v })} />
            ) : (
              <input value={r.sku || ''} onChange={e => updateResource(idx, { sku: e.target.value })} />
            )}
            <label>Qty:&nbsp;</label>
            <input type="number" min={1} value={r.quantity || 1} onChange={e => updateResource(idx, { quantity: Number(e.target.value) })} style={{ width: 80 }} />
            <button onClick={() => removeResource(idx)}>Remove</button>
          </div>
        </div>
      ))}
    </section>
  )
}