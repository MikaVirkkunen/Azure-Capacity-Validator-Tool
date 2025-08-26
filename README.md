# Azure Capacity Validator (Local MVP)

Validates whether a selected Azure region can support a planned architecture, using live Azure APIs and a modern local UX.

- Live validation against Microsoft APIs (no hallucinations)
- Runs locally (FastAPI + React)
- Uses Azure AD (DefaultAzureCredential) by default
- Azure OpenAI (GPT-4.1) can generate an initial plan JSON which is then validated

## Quickstart

1) Backend

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# Required (AAD by default; key optional)
export AVATAR_AZURE_OPENAI_DEPLOYMENT=gpt-4.1
export AVATAR_AZURE_OPENAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
# Optional: export AVATAR_AZURE_OPENAI_KEY=...

# Optional: export AZURE_SUBSCRIPTION_ID=<subId>
az login
uvicorn app.main:app --reload --port 8000
```

2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## What you can do

- Pick subscription and region
- Browse VM sizes available in the chosen region
- Add VM and Disk resources to a plan
- Validate availability per region and subscription
- Use AI to draft a plan from a natural language description

## Agent/MCP

Not required for this MVP. If you want agent workflows next (as in the original vision), we can:
- Wrap the Azure SDK calls as MCP tools
- Add a Microsoft Learn MCP to fetch official docs and return canonical references alongside validations

### AI Compatibility (httpx & openai)
Some `openai` SDK releases pass a legacy `proxies` kwarg to `httpx.Client`. `httpx` 0.28+ removed that parameter. This app includes a small runtime shim that strips `proxies` if the installed httpx no longer supports it. To disable the shim set `OPENAI_HTTPX_DISABLE_SHIM=1`. If you prefer no shim, pin `httpx<0.28` (and a compatible `openai` version) or upgrade both once upstream removes the dependency.