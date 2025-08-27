# Azure Capacity Validator

Lightweight local tool to check if an Azure region can host your planned architecture (VM sizes, disks, other resource types) using live Azure APIs. It uses Azure OpenAI to draft an initial JSON plan that you refine and validate—no hallucinated availability, everything is verified against Microsoft endpoints.

![Overview](docs/Capacity%20Validator%20-%20Demo.png)

## Audience
Designed for Azure Infrastructure / Cloud Architects who want a quick, trustworthy pre-check before building landing zones, running formal quota increase requests, or approving designs. No deep developer background required.

## Key Capabilities
* Discover subscriptions (uses your Azure login / identity)
* List regions and availability zone mappings
* Enumerate VM sizes & disk / common SKUs per region
* Validate a multi-resource plan (VMs, disks, Key Vault, Storage, Public IPs, App Service, Azure OpenAI)
* Summarise relevant compute quotas and projected usage (cores, families)
* Optional AI plan draft (Azure OpenAI deployment you already own)

## Architecture (Local Only)
Backend: FastAPI + Azure SDK (runs on your machine, no data leaves except Azure API calls)
Frontend: React/Vite UI
Auth: DefaultAzureCredential (supports az login, Visual Studio / VS Code sign‑in, Managed Identity, or Service Principal env vars)

## Setup (5–10 minutes)
1. Prerequisites
	* Python 3.11+
	* Node.js 18+
	* Azure CLI installed & you can run: `az login`
	* Reader permission on target subscription(s)
2. Clone repo and create a .env
	* Copy `.env.example` to `.env`
	* Fill `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` if you want AI plan draft (otherwise skip and feature is disabled gracefully)
	* (Optional) Set `AZURE_SUBSCRIPTION_ID` to pin a default subscription
3. Sign in to Azure
	* Run `az login` (or use a Service Principal exported via `AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET` if needed)
4. Install & run backend
```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate  # Windows PowerShell
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```
5. Install & run frontend (separate terminal)
```bash
cd frontend
npm install
npm run dev
```
6. Open the UI: http://localhost:5173

## Using the Tool
1. Subscriptions: The dropdown auto-loads visible subscriptions (or uses the one you pinned)
2. Region: Pick a region; VM sizes & SKU lists query live metadata
3. Build Plan: Add resources (VMs, disks, etc.) and quantities
4. (Optional) AI Draft: Enter a natural language prompt (e.g. "3 web VMs, premium disks, Key Vault, storage for logs") – edit the produced JSON
5. Validate: Click validate; results show per-resource availability plus:
	* Zone mapping (logical→physical) if published
	* Quota summary and projected utilisation after your requested cores
6. Iterate: Adjust SKUs or region until everything is AVAILABLE or consciously accepted

## Environment Variables Summary
| Variable | Purpose | Required |
|----------|---------|----------|
| AZURE_OPENAI_ENDPOINT | Your Azure OpenAI endpoint | Only for AI draft |
| AZURE_OPENAI_DEPLOYMENT | Model deployment name (e.g. gpt-4.1) | Only for AI draft |
| AZURE_OPENAI_KEY | API key (if not using AAD) | No |
| AZURE_SUBSCRIPTION_ID | Pin default subscription | No |
| CORS_ALLOW_ORIGINS | Frontend origin(s) | No |
| AZURE_OPENAI_API_VERSION | Override default API version | No |

If AI vars are absent `/api/ai/plan` returns 503 so the UI can hide the feature.

## Security & Privacy
* No secrets committed: `.env` is ignored, see `.env.example`
* Uses your existing Azure identity—no extra credential store
* All data remains local except Azure management/data plane calls
* Optional API key for Azure OpenAI never logged

## Troubleshooting
Issue: AI plan call fails mentioning `proxies`.
Cause: Older `openai` SDK combined with newer `httpx`.
Fix: A small shim is auto-applied. To disable set `OPENAI_HTTPX_DISABLE_SHIM=1` or keep `httpx<0.28` (already pinned).

Issue: No subscriptions listed.
Fix: Ensure `az login` succeeded and your identity has Reader role. Optionally set `AZURE_SUBSCRIPTION_ID`.

Issue: Plan shows UNKNOWN for Azure OpenAI.
Fix: Region may not publish availability via SKU API or call failed; re-run later or verify in Portal.

## Extending (Optional)
* Add more resource-type specific validators (Storage redundancy permutations, Public IP zone constraints, etc.)
* Export / import plan JSON files
* Persist plans (e.g. local JSON, Blob Storage)
* Wrap logic as MCP tools for agent automation

## Contributing
Pull requests welcome: test additions, new validators, UI usability improvements. Keep dependencies minimal.

## License
MIT License. See `LICENSE` for full text.

---
Feel free to open issues with real-world validation edge cases so they can be encoded as tests.