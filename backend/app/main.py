import os
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .azure_client import list_subscriptions, list_locations, list_vm_sizes, list_compute_resource_skus, get_default_subscription_id
from .models import Plan, ValidationResponse, ValidationResultItem, PlanResource
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
    size = resource.sku
    if not size:
        return ValidationResultItem(resource=resource, status="unknown", details="VM size missing (sku).")

    sizes = list_vm_sizes(region, subscription_id)
    names = {s["name"] for s in sizes}
    if size not in names:
        return ValidationResultItem(
            resource=resource,
            status="unavailable",
            details=f"VM size {size} is not available in {region}."
        )

    # Optional capability checks using resource SKUs
    skus = list_compute_resource_skus(region, subscription_id)
    matching = [s for s in skus if s["resource_type"] == "virtualMachines" and (s["name"] == size or s["size"] == size)]
    details = "Available."
    if resource.features:
        issues = []
        for k, v in resource.features.items():
            for m in matching:
                caps = m.get("capabilities", {})
                if k in caps:
                    # Compare normalized values
                    cap_val = str(caps[k]).lower()
                    req_val = str(v).lower()
                    if cap_val != req_val:
                        issues.append(f"Capability {k}={caps[k]} does not meet requirement {v}")
        if issues:
            details = "; ".join(issues)
            return ValidationResultItem(resource=resource, status="unknown", details=details)

    return ValidationResultItem(resource=resource, status="available", details=details)


def _validate_disk(resource: PlanResource, region: str, subscription_id: str | None) -> ValidationResultItem:
    sku = resource.sku
    if not sku:
        return ValidationResultItem(resource=resource, status="unknown", details="Disk SKU missing (sku).")

    skus = list_compute_resource_skus(region, subscription_id)
    # disks appear in resource_type == "disks", names like Premium_LRS, StandardSSD_LRS, etc.
    disk_skus = [s for s in skus if s["resource_type"] == "disks" and s["name"] == sku and not s["restricted"]]
    if not disk_skus:
        return ValidationResultItem(
            resource=resource,
            status="unavailable",
            details=f"Disk SKU {sku} not available in {region}."
        )
    return ValidationResultItem(resource=resource, status="available", details="Available.")


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
        else:
            results.append(ValidationResultItem(
                resource=r,
                status="unknown",
                details=f"Validator for {r.resource_type} not implemented yet."
            ))

    return ValidationResponse(region=plan.region, subscription_id=subscription_id, results=results)