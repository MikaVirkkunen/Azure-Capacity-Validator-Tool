import os
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .azure_client import list_subscriptions, list_locations, list_vm_sizes, list_compute_resource_skus, get_default_subscription_id, is_resource_available, is_azure_openai_available
from .models import Plan, ValidationResponse, ValidationResultItem, PlanResource, ValidationStatus
from .ai_agent import generate_initial_plan

app = FastAPI(title="Azure Capacity Validator Tool", version="0.1.1")

# Allow local dev UIs and static hosting origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/subscriptions")
def api_subscriptions():
    return list_subscriptions()


@app.get("/api/locations")
def api_locations(subscription_id: str | None = None):
    return list_locations(subscription_id)


@app.get("/api/compute/vm-sizes")
def api_vm_sizes(location: str, subscription_id: str | None = None):
    if not location:
        raise HTTPException(400, "location is required")
    return list_vm_sizes(location, subscription_id)


@app.get("/api/compute/resource-skus")
def api_compute_skus(location: str | None = None, subscription_id: str | None = None):
    return list_compute_resource_skus(location, subscription_id)


@app.get("/api/resource-skus")
def api_resource_skus(resource_type: str, location: str, subscription_id: str | None = None):
    """Return list of SKU/size options for a given resource type in a region.

    Response shape: { "items": [ {"name": "Standard_D4s_v5", "details": "..."}, ... ] }
    If resource type unsupported for dynamic listing, returns empty list.
    """
    if not resource_type or "/" not in resource_type:
        raise HTTPException(400, "resource_type is required (Provider/Type)")
    if not location:
        raise HTTPException(400, "location is required")

    rt_lower = resource_type.lower()
    items: list[dict[str, str]] = []

    try:
        if rt_lower == "microsoft.compute/virtualmachines":
            # Map VM sizes
            for s in list_vm_sizes(location, subscription_id):
                mem_gb = s.get("memory_in_mb")
                cores = s.get("number_of_cores")
                details = []
                if mem_gb:
                    details.append(f"{round(mem_gb/1024)} GB")
                if cores:
                    details.append(f"{cores} vCPU")
                items.append({"name": s["name"], "details": ", ".join(details)})
        elif rt_lower == "microsoft.compute/disks":
            # Use compute resource SKUs for disks
            skus = list_compute_resource_skus(location, subscription_id)
            seen = set()
            for sku in skus:
                if sku.get("resource_type") == "disks" and not sku.get("restricted") and sku.get("name"):
                    name = sku["name"]
                    if name not in seen:
                        seen.add(name)
                        tier = sku.get("tier")
                        items.append({"name": name, "details": tier or ""})
        elif rt_lower == "microsoft.keyvault/vaults":
            items = [
                {"name": "standard", "details": "Key Vault Standard"},
                {"name": "premium", "details": "Key Vault Premium"},
            ]
        elif rt_lower == "microsoft.cognitiveservices/accounts":
            # Minimal: expose S0 which is the common SKU for cognitive services like OpenAI
            items = [
                {"name": "S0", "details": "Standard (S0)"}
            ]
    except Exception as e:
        # On failure, return empty list with hint
        return {"items": [], "warning": f"SKU enumeration failed: {e}"}

    return {"items": items}


@app.post("/api/ai/plan")
def api_ai_plan(payload: Dict[str, Any]):
    """
    payload: { "prompt": "..." }
    """
    prompt = payload.get("prompt")
    if not prompt:
        raise HTTPException(400, "prompt is required")
    try:
        plan = generate_initial_plan(prompt)
        # Ensure some defaults
        if "region" not in plan:
            plan["region"] = "westeurope"
        return plan
    except Exception as e:
        raise HTTPException(500, f"AI plan generation failed: {e}")


def _validate_vm(resource: PlanResource, region: str, subscription_id: str | None) -> ValidationResultItem:
    """Validate a VM size against region availability & simple capability equality checks."""
    size = resource.sku
    if not size:
        return ValidationResultItem(resource=resource, status=ValidationStatus.UNKNOWN, details="VM size missing (sku).")

    names = {s["name"] for s in list_vm_sizes(region, subscription_id)}
    if size not in names:
        return ValidationResultItem(
            resource=resource,
            status=ValidationStatus.UNAVAILABLE,
            details=f"VM size {size} is not available in {region}."
        )

    skus = list_compute_resource_skus(region, subscription_id)
    matching = [s for s in skus if s["resource_type"].lower() == "virtualmachines" and (s.get("name") == size or s.get("size") == size)]
    details = "Available."
    if matching:
        zones_set: set[str] = set()
        tier = None
        family = None
        for m in matching:
            for z in (m.get("zones") or []):
                zones_set.add(str(z))
            tier = tier or m.get("tier")
            family = family or m.get("family")
        extras: list[str] = []
        if zones_set:
            extras.append(f"Zones: {', '.join(sorted(zones_set))}")
        if tier:
            extras.append(f"Tier: {tier}")
        if family:
            extras.append(f"Family: {family}")
        if extras:
            details = details + " " + "; ".join(extras) + "."

    if resource.features:
        issues: list[str] = []
        for k, v in resource.features.items():
            for m in matching:
                caps = m.get("capabilities", {})
                if k in caps:
                    if str(caps[k]).lower() != str(v).lower():
                        issues.append(f"Capability {k}={caps[k]} does not meet requirement {v}")
        if issues:
            return ValidationResultItem(resource=resource, status=ValidationStatus.UNKNOWN, details="; ".join(issues))
    return ValidationResultItem(resource=resource, status=ValidationStatus.AVAILABLE, details=details)


def _validate_disk(resource: PlanResource, region: str, subscription_id: str | None) -> ValidationResultItem:
    sku = resource.sku
    if not sku:
        return ValidationResultItem(resource=resource, status=ValidationStatus.UNKNOWN, details="Disk SKU missing (sku).")

    skus = list_compute_resource_skus(region, subscription_id)
    disk_skus = [s for s in skus if s["resource_type"] == "disks" and s["name"] == sku and not s["restricted"]]
    if not disk_skus:
        return ValidationResultItem(
            resource=resource,
            status=ValidationStatus.UNAVAILABLE,
            details=f"Disk SKU {sku} not available in {region}."
        )
    return ValidationResultItem(resource=resource, status=ValidationStatus.AVAILABLE, details="Available.")


def _validate_cognitive_account(resource: PlanResource, region: str, subscription_id: str | None) -> ValidationResultItem:
    """Validate only regional availability of Azure OpenAI (no model/deployment checks)."""
    aoai = is_azure_openai_available(region, subscription_id)
    avail = aoai.get("available")
    details = aoai.get("details", "") or ""
    if avail is True:
        return ValidationResultItem(resource=resource, status=ValidationStatus.AVAILABLE, details=f"Azure OpenAI available in {region}. {details}".strip())
    if avail is False:
        return ValidationResultItem(resource=resource, status=ValidationStatus.UNAVAILABLE, details=f"Azure OpenAI not available in {region}. {details}".strip())
    # None / indeterminate
    return ValidationResultItem(resource=resource, status=ValidationStatus.UNKNOWN, details=f"Azure OpenAI availability indeterminate in {region}. {details}".strip())


@app.post("/api/validate-plan", response_model=ValidationResponse)
def api_validate_plan(plan: Plan):
    if not plan.region:
        raise HTTPException(400, "region is required")
    subscription_id = plan.subscription_id or get_default_subscription_id()

    results: List[ValidationResultItem] = []
    for r in plan.resources:
        rt = r.resource_type.lower()
        if rt == "microsoft.compute/virtualmachines":
            results.append(_validate_vm(r, plan.region, subscription_id))
        elif rt == "microsoft.compute/disks":
            results.append(_validate_disk(r, plan.region, subscription_id))
        elif rt == "microsoft.cognitiveservices/accounts":
            results.append(_validate_cognitive_account(r, plan.region, subscription_id))
        else:
            # Generic availability check via ARM Providers
            avail = is_resource_available(r.resource_type, plan.region, subscription_id)
            if avail.get("available"):
                results.append(ValidationResultItem(resource=r, status=ValidationStatus.AVAILABLE, details="Available (provider)."))
            else:
                reason = avail.get("reason") or f"{r.resource_type} not available in {plan.region} for this subscription."
                results.append(ValidationResultItem(resource=r, status=ValidationStatus.UNAVAILABLE, details=reason))

    return ValidationResponse(region=plan.region, subscription_id=subscription_id, results=results)