import os
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .azure_client import (
    list_subscriptions,
    list_locations,
    list_vm_sizes,
    list_compute_resource_skus,
    get_default_subscription_id,
    is_resource_available,
    is_azure_openai_available,
    get_zone_mappings_for_location,
)
from .cache import clear_all_cache
import re
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


@app.get("/api/debug/versions")
def debug_versions():
    """Return runtime package versions & module paths to help diagnose mixed dependency issues."""
    info: dict[str, str | None] = {}
    try:
        import openai  # type: ignore
        info["openai_version"] = getattr(openai, "__version__", None)
        info["openai_file"] = getattr(openai, "__file__", None)
    except Exception as e:  # pragma: no cover
        info["openai_error"] = str(e)
    try:
        import httpx  # type: ignore
        info["httpx_version"] = getattr(httpx, "__version__", None)
        info["httpx_file"] = getattr(httpx, "__file__", None)
    except Exception as e:  # pragma: no cover
        info["httpx_error"] = str(e)
    try:
        import sys
        info["python_executable"] = sys.executable
        info["sys_path"] = ";".join(sys.path)
    except Exception:
        pass

    return info


@app.get("/api/subscriptions")
def api_subscriptions():
    return list_subscriptions()


@app.get("/api/locations")
def api_locations(subscription_id: str | None = None):
    return list_locations(subscription_id)


@app.get("/api/locations/zone-mappings")
def api_locations_zone_mappings(location: str, subscription_id: str | None = None):
    """Return availabilityZoneMappings for a region (logical to physical zone mapping if available)."""
    if not location:
        raise HTTPException(400, "location is required")
    data = get_zone_mappings_for_location(location, subscription_id)
    if not data:
        return {"location": location, "availabilityZoneMappings": None}
    return {"location": location, "availabilityZoneMappings": data.get("availabilityZoneMappings")}


@app.get("/api/compute/vm-sizes")
def api_vm_sizes(location: str, subscription_id: str | None = None):
    if not location:
        raise HTTPException(400, "location is required")
    return list_vm_sizes(location, subscription_id)


@app.get("/api/compute/resource-skus")
def api_compute_skus(location: str | None = None, subscription_id: str | None = None):
    return list_compute_resource_skus(location, subscription_id)


@app.get("/api/compute/vm-zone-details")
def api_vm_zone_details(location: str, size: str, subscription_id: str | None = None):
    """Return full vs feature-differentiated zone sets for a VM size.

    Response example:
    {
      "size": "Standard_D2s_v5",
      "region": "westeurope",
      "all_zones": ["1","2","3"],
      "feature_zones": {"UltraSSDAvailable": ["1","2"]}
    }
    """
    if not location or not size:
        raise HTTPException(400, "location and size are required")
    skus = list_compute_resource_skus(location, subscription_id)
    all_zones: set[str] = set()
    feature_map: dict[str, set[str]] = {}
    for sku in skus:
        if sku.get("resource_type", "").lower() != "virtualmachines":
            continue
        if sku.get("name") != size and sku.get("size") != size:
            continue
        for z in sku.get("zones") or []:
            all_zones.add(str(z))
        # zone_capabilities is a list of capability dicts for zone groups; we can't know exact zone grouping
        # (Azure groups multiple zones with identical capability sets). We assume each capability applies to the
        # subset of zones that appear in the same group ordering. For simplicity: if capability present in any group,
        # attach all zones from that group.
        zone_caps = sku.get("zone_capabilities") or []
        # We need to access original zoneDetails zone names; not stored—enhancement would store mapping. For now,
        # approximate by assigning capabilities to all_zones if any capability differs.
        for cap_dict in zone_caps:
            for cname, cval in cap_dict.items():
                key = f"{cname}={cval}" if cval not in ("True", "False", None, "") else cname
                feature_map.setdefault(key, set()).update(all_zones)
    return {
        "size": size,
        "region": location,
        "all_zones": sorted(all_zones),
        "feature_zones": {k: sorted(v) for k, v in feature_map.items()}
    }


@app.post("/api/cache/clear")
def api_cache_clear():
    """Clear all in-memory caches (useful for testing or forcing fresh Azure metadata)."""
    clear_all_cache()
    return {"status": "cleared"}


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
                {"name": "F0", "details": "Free (quota limited)"},
                {"name": "S0", "details": "Standard"}
            ]
        elif rt_lower == "microsoft.storage/storageaccounts":
            items = [
                {"name": "Standard_LRS", "details": "Standard Locally Redundant"},
                {"name": "Standard_GRS", "details": "Standard Geo-Redundant"},
                {"name": "Standard_RAGRS", "details": "Standard Read-Access GRS"},
                {"name": "Standard_ZRS", "details": "Standard Zone-Redundant"},
                {"name": "Standard_GZRS", "details": "Standard Geo-Zone Redundant"},
                {"name": "Standard_RAGZRS", "details": "Standard Read-Access GZRS"},
                {"name": "Premium_LRS", "details": "Premium (e.g. File Shares / Page Blobs)"},
            ]
        elif rt_lower == "microsoft.network/publicipaddresses":
            items = [
                {"name": "Basic", "details": "Basic SKU"},
                {"name": "Standard", "details": "Standard SKU"},
            ]
        elif rt_lower == "microsoft.web/serverfarms":
            # App Service Plans (curated common SKUs)
            items = [
                {"name": "F1", "details": "Free"},
                {"name": "B1", "details": "Basic Small"},
                {"name": "S1", "details": "Standard Small"},
                {"name": "P1v3", "details": "Premium v3 P1"},
                {"name": "I1v2", "details": "Isolated v2 I1"},
            ]
        elif rt_lower == "microsoft.web/sites":
            # Sites map to an App Service Plan; expose same curated SKUs for convenience
            items = [
                {"name": "F1", "details": "Free"},
                {"name": "B1", "details": "Basic Small"},
                {"name": "S1", "details": "Standard Small"},
                {"name": "P1v3", "details": "Premium v3 P1"},
                {"name": "I1v2", "details": "Isolated v2 I1"},
            ]
    except Exception as e:
        # On failure, return empty list with hint
        return {"items": [], "warning": f"SKU enumeration failed: {e}"}

    return {"items": items}


@app.post("/api/ai/plan")
def api_ai_plan(payload: Dict[str, Any]):
    """Generate an initial plan via Azure OpenAI (optional feature).

    Request body: { "prompt": "..." }
    If Azure OpenAI environment variables are not configured, returns 503 instead of 500 so
    the frontend can distinguish "feature unavailable" from a real server error.
    """
    prompt = payload.get("prompt")
    if not prompt:
        raise HTTPException(400, "prompt is required")
    # Quick presence check before invoking client (to avoid stack trace noise)
    if not os.getenv("AVATAR_AZURE_OPENAI_ENDPOINT") or not os.getenv("AVATAR_AZURE_OPENAI_DEPLOYMENT"):
        raise HTTPException(status_code=503, detail="Azure OpenAI not configured (set AVATAR_AZURE_OPENAI_ENDPOINT and AVATAR_AZURE_OPENAI_DEPLOYMENT).")
    try:
        plan = generate_initial_plan(prompt)
        if "region" not in plan:
            plan["region"] = "westeurope"
        # Heuristic default SKU inference if AI left some blank
        _apply_default_skus(plan, prompt)
        return plan
    except Exception as e:
        # Distinguish config vs transient errors
        raise HTTPException(502, f"AI plan generation failed: {e}")


def _apply_default_skus(plan: Dict[str, Any], original_prompt: str) -> None:
    """Fill in missing skus based on simple keyword heuristics; mutates plan in place."""
    if not plan or not isinstance(plan.get("resources"), list):
        return
    text = (original_prompt or "").lower()
    for r in plan["resources"]:
        try:
            rt = (r.get("resource_type") or "").lower()
            sku = r.get("sku")
            if sku:
                continue  # honor AI-provided choice
            # Disks
            if rt == "microsoft.compute/disks":
                if "ultra" in text:
                    r["sku"] = "UltraSSD_LRS"
                elif "premium" in text:
                    r["sku"] = "Premium_LRS"
                elif "standard ssd" in text:
                    r["sku"] = "StandardSSD_LRS"
                else:
                    r["sku"] = "Standard_LRS"
            # VM sizes - look for explicit size pattern
            elif rt == "microsoft.compute/virtualmachines":
                m = re.search(r"standard_[a-z]\d+[a-z]*s?_v\d+", text)
                if m:
                    r["sku"] = m.group(0).replace("standard_", "Standard_")
                elif "gpu" in text:
                    r["sku"] = "Standard_NC4as_T4_v3"
                elif "memory optimized" in text or "memory-optimized" in text:
                    r["sku"] = "Standard_E4s_v5"
                else:
                    r["sku"] = "Standard_D2s_v5"
            elif rt == "microsoft.keyvault/vaults":
                r["sku"] = "standard"
            elif rt == "microsoft.cognitiveservices/accounts":
                # prefer S0 if not explicitly free
                r["sku"] = "F0" if "free tier" in text or "f0" in text else "S0"
            elif rt == "microsoft.storage/storageaccounts":
                if "gzs" in text or "gzs" in text:
                    r["sku"] = "Standard_GZRS"
                elif "zrs" in text:
                    r["sku"] = "Standard_ZRS"
                elif "premium" in text:
                    r["sku"] = "Premium_LRS"
                elif "geo redundant" in text or "grs" in text:
                    r["sku"] = "Standard_GRS"
                else:
                    r["sku"] = "Standard_LRS"
            elif rt == "microsoft.network/publicipaddresses":
                r["sku"] = "Standard" if "standard public ip" in text or "production" in text else "Basic"
            elif rt == "microsoft.web/serverfarms":
                if "premium" in text:
                    r["sku"] = "P1v3"
                elif "isolated" in text:
                    r["sku"] = "I1v2"
                elif "standard" in text:
                    r["sku"] = "S1"
                elif "basic" in text:
                    r["sku"] = "B1"
                else:
                    r["sku"] = "F1"
            elif rt == "microsoft.web/sites":
                if "premium" in text:
                    r["sku"] = "P1v3"
                elif "isolated" in text:
                    r["sku"] = "I1v2"
                elif "standard" in text:
                    r["sku"] = "S1"
                elif "basic" in text:
                    r["sku"] = "B1"
                else:
                    r["sku"] = "F1"
        except Exception:
            continue


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
    # Support older serialized objects missing zones attribute by falling back to dict lookup
    rz = getattr(resource, 'zones', None)
    if rz is None and isinstance(resource, PlanResource):  # attempt internal dict
        rz = getattr(resource, '__dict__', {}).get('zones')
    requested_zones = set([str(z).strip() for z in (rz or []) if z])
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
        # Derive simple feature capabilities that vary by zone (approximation using zone_capabilities union)
        feature_caps: set[str] = set()
        for m in matching:
            for cap_group in (m.get("zone_capabilities") or []):
                for cname, cval in cap_group.items():
                    # highlight capabilities explicitly set True (common pattern e.g. UltraSSDAvailable)
                    if str(cval).lower() == "true":
                        feature_caps.add(cname)
        if feature_caps:
            extras.append(f"Feature Zones: {', '.join(sorted(feature_caps))}")
        if tier:
            extras.append(f"Tier: {tier}")
        if family:
            extras.append(f"Family: {family}")
        if extras:
            details = details + " " + "; ".join(extras) + "."

        # Zone validation logic
        if requested_zones:
            if not zones_set:
                return ValidationResultItem(
                    resource=resource,
                    status=ValidationStatus.UNAVAILABLE,
                    details=f"Requested zones {sorted(requested_zones)} but size not zonally available in {region}."
                )
            missing = requested_zones - zones_set
            if missing:
                return ValidationResultItem(
                    resource=resource,
                    status=ValidationStatus.UNAVAILABLE,
                    details=f"Missing requested zones: {sorted(missing)}; available zones: {sorted(zones_set)}"
                )
            # all good, annotate
            details = details + f" Requested zones satisfied: {', '.join(sorted(requested_zones))}."

    if resource.features and matching:
        issues: list[str] = []
        for k, v in resource.features.items():
            for m in matching:
                caps = m.get("capabilities") or {}
                if k in caps and str(caps[k]).lower() != str(v).lower():
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
    # Add region-level zone mapping summary (logical->physical) once
    mapping = get_zone_mappings_for_location(plan.region, subscription_id)
    az_maps_raw = mapping.get("availabilityZoneMappings") if mapping else None
    zone_mapping: list[dict] | None = None
    if az_maps_raw:
        zone_mapping = []
        for m in az_maps_raw:
            if not isinstance(m, dict):
                continue
            lz = m.get('logicalZone') or m.get('logicalzone')
            pz = m.get('physicalZone') or m.get('physicalzone')
            if lz is not None and pz:
                zone_mapping.append({'logicalZone': lz, 'physicalZone': pz})
    return ValidationResponse(region=plan.region, subscription_id=subscription_id, results=results, zone_mapping=zone_mapping)