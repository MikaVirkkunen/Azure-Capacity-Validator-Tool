# Development Guide

This MVP provides:
- Backend (FastAPI) using Azure SDKs to validate capacity from live Azure APIs
- Azure OpenAI integration to generate an initial plan
- Frontend (React + TypeScript) for a modern UI

It aligns with the README vision:
- Reads live data from Microsoft APIs (no hallucinations)
- Agents optional; AI only drafts a JSON plan that is later validated
- Modern UI to pick regions, VM sizes, and disk SKUs pulled from Azure APIs

## Prerequisites

- Python 3.11+
- Node 18+
- Azure access with Reader permissions on target subscriptions
- Login with Azure CLI (`az login`) OR set a Service Principal via environment variables

## Authentication (Modern-first)

Azure Resource access:
- Uses `DefaultAzureCredential` (supports `az login`, Managed Identity, Service Principal, etc.).

Azure OpenAI:
- Preferred: Azure AD via `DefaultAzureCredential` (no keys).
- Fallback: API key if `AZURE_OPENAI_KEY` is set.

Required env:
- `AZURE_OPENAI_DEPLOYMENT` (e.g., gpt-4.1)
- `AZURE_OPENAI_ENDPOINT` (e.g., https://<your-aoai>.openai.azure.com/)

Optional:
- `AZURE_OPENAI_KEY` (only if you prefer key-based auth)
- `AZURE_SUBSCRIPTION_ID` (to pin a default subscription)
- `CORS_ALLOW_ORIGINS` (comma-separated, default "*")
- `AZURE_OPENAI_API_VERSION` (default `2024-02-15-preview`)

Service Principal (optional):
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
Ensure the app has "Reader" role on the subscription(s) for discovery and SKU checks, and has access to the Azure OpenAI resource if using AAD.

## Run Backend

```bash
cd backend
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Set Azure OpenAI env
export AZURE_OPENAI_DEPLOYMENT=gpt-4.1
export AZURE_OPENAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
# Optional key (AAD is preferred):
# export AZURE_OPENAI_KEY=...

# Optional default subscription:
# export AZURE_SUBSCRIPTION_ID=...

# Authenticate with Azure (AAD):
az login

uvicorn app.main:app --reload --port 8000
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Features Implemented

- Subscription discovery
- Region listing per subscription
- VM size availability per region
- Disk SKU availability per region
- Plan validation (`/api/validate-plan`)
- AI plan generation (`/api/ai/plan`) using Azure OpenAI with AAD by default

## API Examples

- GET `/api/subscriptions`
- GET `/api/locations?subscription_id=<subId>`
- GET `/api/compute/vm-sizes?location=westeurope`
- GET `/api/compute/resource-skus?location=westeurope`
- POST `/api/validate-plan`
  ```json
  {
    "subscription_id": "<optional>",
    "region": "westeurope",
    "resources": [
      { "resource_type": "Microsoft.Compute/virtualMachines", "sku": "Standard_D4s_v5", "quantity": 2 },
      { "resource_type": "Microsoft.Compute/disks", "sku": "Premium_LRS", "quantity": 4 }
    ]
  }
  ```
- POST `/api/ai/plan`
  ```json
  { "prompt": "We need 3x Standard_D4s_v5 VMs and Premium_LRS disks" }
  ```

## Roadmap / Next Steps

- Add validators for:
  - Microsoft.Network/publicIPAddresses (SKU Standard)
  - Storage account SKUs (for completeness around disks)
- Caching and rate limiting for performance
- Export/import plan JSON
- Optional persistence:
  - Local file or SQLite
  - Azure Blob Storage toggle via env (if you want to store plans in Azure)
- MCP servers (optional):
  - Azure MCP wrapping current SDK queries as tools
  - Microsoft Learn MCP retrieving canonical docs; append references to results

## Notes

- No AKS or App Service dependencies; runs locally.
- AI outputs a JSON skeleton only; availability is always checked against live Azure APIs.