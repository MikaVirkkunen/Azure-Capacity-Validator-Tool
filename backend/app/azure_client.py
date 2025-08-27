import os
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from azure.identity import DefaultAzureCredential
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
import httpx

from .cache import ttl_cache


def get_default_credential() -> DefaultAzureCredential:
    # Supports: Azure CLI, Managed Identity, Env Vars (Client ID/Secret), etc.
    # For local use, 'az login' is easiest.
    return DefaultAzureCredential(
        exclude_interactive_browser_credential=False
    )


def get_subscription_client(credential: Optional[DefaultAzureCredential] = None) -> SubscriptionClient:
    cred = credential or get_default_credential()
    return SubscriptionClient(cred)


@ttl_cache(ttl_seconds=300)
def list_subscriptions() -> List[Dict[str, Any]]:
    """Cache subscription enumeration for 5 minutes to avoid repeated ARM calls."""
    client = get_subscription_client()
    subs: List[Dict[str, Any]] = []
    for s in client.subscriptions.list():
        subs.append({
            "subscription_id": s.subscription_id,
            "display_name": getattr(s, "display_name", None),
            "state": str(getattr(s, "state", "")),
            "tenant_id": getattr(s, "tenant_id", None)
        })
    return subs


def get_default_subscription_id() -> Optional[str]:
    # Prefer explicit env if provided
    env_sub = os.getenv("AZURE_SUBSCRIPTION_ID") or os.getenv("SUBSCRIPTION_ID")
    if env_sub:
        return env_sub

    subs = list_subscriptions()
    return subs[0]["subscription_id"] if subs else None


@ttl_cache(ttl_seconds=900)
def list_locations(subscription_id: Optional[str] = None) -> List[Dict[str, Any]]:
    sub_id = subscription_id or get_default_subscription_id()
    if not sub_id:
        return []
    client = get_subscription_client()
    result = client.subscriptions.list_locations(sub_id)
    return [
        {
            "name": loc.name,
            "display_name": loc.display_name,
            "regional_display_name": getattr(loc, "regional_display_name", None)
        }
        for loc in result
    ]


@ttl_cache(ttl_seconds=21600)  # 6h cache; zone mappings rarely change
def list_locations_with_zone_mappings(subscription_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Call the management REST API to retrieve locations including availabilityZoneMappings (logical->physical).

    Returns list of dicts each containing: name, displayName, availabilityZoneMappings (list or None)
    """
    sub_id = subscription_id or get_default_subscription_id()
    if not sub_id:
        return []
    # Acquire token for ARM
    cred = get_default_credential()
    token = cred.get_token("https://management.azure.com/.default").token
    url = f"https://management.azure.com/subscriptions/{sub_id}/locations?api-version=2022-12-01"
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
            resp.raise_for_status()
            data = resp.json()
            out: List[Dict[str, Any]] = []
            for entry in data.get("value", []) or []:
                out.append({
                    "name": entry.get("name"),
                    "displayName": entry.get("displayName"),
                    "availabilityZoneMappings": entry.get("availabilityZoneMappings")
                })
            return out
    except Exception:
        return []


@ttl_cache(ttl_seconds=21600)
def get_zone_mappings_for_location(location: str, subscription_id: Optional[str] = None) -> Dict[str, Any]:
    locs = list_locations_with_zone_mappings(subscription_id)
    norm = location.lower()
    for loc in locs:
        if (loc.get("name") or "").lower() == norm:
            return loc
    return {}


def get_compute_client(subscription_id: Optional[str] = None) -> ComputeManagementClient:
    sub_id = subscription_id or get_default_subscription_id()
    if not sub_id:
        raise RuntimeError("No Azure subscription available. Login with 'az login' or set AZURE_SUBSCRIPTION_ID.")
    cred = get_default_credential()
    return ComputeManagementClient(cred, sub_id)


def get_resource_client(subscription_id: Optional[str] = None) -> ResourceManagementClient:
    sub_id = subscription_id or get_default_subscription_id()
    if not sub_id:
        raise RuntimeError("No Azure subscription available. Login with 'az login' or set AZURE_SUBSCRIPTION_ID.")
    cred = get_default_credential()
    return ResourceManagementClient(cred, sub_id)


def get_cognitiveservices_client(subscription_id: Optional[str] = None) -> CognitiveServicesManagementClient:
    sub_id = subscription_id or get_default_subscription_id()
    if not sub_id:
        raise RuntimeError("No Azure subscription available. Login with 'az login' or set AZURE_SUBSCRIPTION_ID.")
    cred = get_default_credential()
    return CognitiveServicesManagementClient(cred, sub_id)


def get_cognitive_account_region_for_endpoint(endpoint_url: str, subscription_id: Optional[str] = None) -> Optional[str]:
    """Given an AOAI endpoint URL, attempt to find the Cognitive Services account and return its Azure location.
    Returns region code like 'swedencentral' or None if not found.
    """
    if not endpoint_url:
        return None
    try:
        parsed = urlparse(endpoint_url)
        base = f"{parsed.scheme}://{parsed.hostname}".lower()
        client = get_cognitiveservices_client(subscription_id)
        # list_by_subscription is available in recent SDKs
        accounts = []
        if hasattr(client.accounts, "list_by_subscription"):
            accounts = list(client.accounts.list_by_subscription())
        else:
            # Fallback: attempt provider listing only (no direct mapping)
            return None
        for acct in accounts:
            props = getattr(acct, "properties", None)
            ep = getattr(props, "endpoint", None)
            if ep:
                p2 = urlparse(ep)
                b2 = f"{p2.scheme}://{p2.hostname}".lower()
                if b2 == base:
                    # return location; ensure lower case code
                    return str(getattr(acct, "location", "") or "").lower()
        return None
    except Exception:
        return None


def is_resource_type_available(resource_type: str, location: Optional[str] = None, subscription_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Generic availability check using ARM Providers API:
    - resource_type: e.g., "Microsoft.Storage/storageAccounts" or "Microsoft.Network/publicIPAddresses".
    - location: optional region filter. If provided, returns whether the type lists that location.
    Returns: { "namespace": str, "type": str, "available": bool, "locations": [..] }
    """
    if "/" not in resource_type:
        return {"namespace": resource_type, "type": "", "available": False, "locations": [], "details": "Invalid resource_type format."}

    namespace, _, typ = resource_type.partition("/")
    client = get_resource_client(subscription_id)

    # Providers list is at subscription scope
    prov = client.providers.get(namespace)
    available_locations: list[str] = []
    for rt in prov.resource_types or []:
        if rt.resource_type and rt.resource_type.lower() == typ.lower():
            # locations can be None; default to []
            available_locations = [loc for loc in (rt.locations or [])]
            break

    available = True if available_locations else False
    if location:
        available = available and (location in available_locations)

    return {
        "namespace": namespace,
        "type": typ,
        "available": bool(available),
        "locations": available_locations,
    }


@ttl_cache(ttl_seconds=900)
def list_provider_resource_types(provider_namespace: str, subscription_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return provider resource types and their supported locations for a given provider namespace."""
    client = get_resource_client(subscription_id)
    providers = client.providers.get(provider_namespace)
    # providers is a Provider
    types = []
    for rt in providers.resource_types or []:
        types.append({
            "resource_type": rt.resource_type,  # e.g., 'virtualMachines'
            "locations": [loc for loc in (rt.locations or []) if loc],
            "api_versions": rt.api_versions or []
        })
    return types


def _normalize_location(s: str) -> str:
    return ''.join(ch for ch in s.lower() if ch.isalnum())


@ttl_cache(ttl_seconds=600)
def is_resource_available(resource_type_fqn: str, location: Optional[str] = None, subscription_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Generic availability check for any Azure resource type using the Providers API.
    resource_type_fqn example: "Microsoft.Compute/virtualMachines" or "Microsoft.Storage/storageAccounts".
    Returns a dict with fields: { available: bool, reason: str, provider: str, type: str, locations: [..] }
    """
    if not resource_type_fqn or "/" not in resource_type_fqn:
        return {"available": False, "reason": "Invalid resource_type format", "provider": None, "type": None, "locations": []}

    provider, rt = resource_type_fqn.split("/", 1)
    try:
        types = list_provider_resource_types(provider, subscription_id)
    except Exception as e:
        return {"available": False, "reason": f"Provider lookup failed: {e}", "provider": provider, "type": rt, "locations": []}

    entry = next((t for t in types if t["resource_type"].lower() == rt.lower()), None)
    if not entry:
        return {"available": False, "reason": f"Resource type not found under provider {provider}", "provider": provider, "type": rt, "locations": []}

    locs = entry.get("locations", [])  # provider usually returns display names (e.g., "West Europe")

    if not location:
        # If no location given, consider available if provider exposes any locations
        return {"available": len(locs) > 0, "reason": "", "provider": provider, "type": rt, "locations": locs}

    # Normalize for comparison and map region code -> display name via subscription locations
    norm_target = _normalize_location(location)

    # Build a set of normalized provider location strings
    norm_provider_locs = {_normalize_location(l) for l in locs if l}

    # Fetch subscription locations to map region codes to display names
    try:
        sub_locs = list_locations(subscription_id)
    except Exception:
        sub_locs = []

    # Possible variants for the requested region: code name and display name(s)
    variants = {norm_target}
    for sl in sub_locs:
        code = (sl.get("name") or "")
        disp = (sl.get("display_name") or "")
        if _normalize_location(code) == norm_target:
            variants.add(_normalize_location(disp))
            variants.add(_normalize_location(code))
        if _normalize_location(disp) == norm_target:
            variants.add(_normalize_location(code))

    available = any(v in norm_provider_locs for v in variants)
    return {"available": available, "reason": "", "provider": provider, "type": rt, "locations": locs}


# --------------------------- Generic Provider SKU Listing ---------------------------
@ttl_cache(ttl_seconds=3600)
def list_provider_skus(
    provider_namespace: str,
    subscription_id: Optional[str] = None,
    location: Optional[str] = None,
    target_resource_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Attempt to list SKUs for a provider namespace via ARM REST API and (optionally) filter by region.

    Returns list of dicts: { name, tier?, kind?, resource_type?, locations? }
    If region filtering is requested and the SKU advertises no locations, it's kept (assumed global).
    """
    sub_id = subscription_id or get_default_subscription_id()
    if not sub_id:
        return []
    api_versions = {
        "Microsoft.Storage": "2023-01-01",
        "Microsoft.Web": "2023-12-01",
        "Microsoft.CognitiveServices": "2023-05-01",
        "Microsoft.Network": "2023-09-01",
        "Microsoft.KeyVault": "2023-07-01",
    }
    api_version = api_versions.get(provider_namespace, "2023-01-01")
    cred = get_default_credential()
    try:
        token = cred.get_token("https://management.azure.com/.default").token
    except Exception:
        return []
    url = f"https://management.azure.com/subscriptions/{sub_id}/providers/{provider_namespace}/skus?api-version={api_version}"

    def _norm(s: str) -> str:
        return ''.join(ch for ch in s.lower() if ch.isalnum())

    want = _norm(location) if location else None
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code >= 400:
                return []
            data = resp.json()
            items: List[Dict[str, Any]] = []
            for v in (data.get("value") or []):
                name = v.get("name") or v.get("skuName") or v.get("sku")
                if not name:
                    continue
                rtype = v.get("resourceType") or v.get("resource_type")
                tier = v.get("tier") or v.get("skuTier") or v.get("tierName")
                kind = v.get("kind")
                # Collect locations from either 'locations' or nested 'locationInfo'
                locs_raw = set()
                for loc in (v.get("locations") or []):
                    if loc:
                        locs_raw.add(str(loc))
                for li in (v.get("locationInfo") or []):
                    # locationInfo entries may have 'locations' (list) or 'location'
                    if isinstance(li, dict):
                        for k in ("locations", "location"):
                            val = li.get(k)
                            if isinstance(val, list):
                                for xx in val:
                                    if xx:
                                        locs_raw.add(str(xx))
                            elif isinstance(val, str):
                                locs_raw.add(val)
                # Region filter
                if want and locs_raw:
                    norm_set = {_norm(l) for l in locs_raw}
                    if want not in norm_set:
                        continue
                # Target resource type filter: if caller specified a resource type, only include if SKU declares it.
                if target_resource_type:
                    if rtype is None:
                        # Skip entries that don't declare resourceType to avoid huge unrelated lists.
                        continue
                    if rtype.lower() != target_resource_type.lower():
                        continue
                items.append({
                    "name": name,
                    "resource_type": rtype,
                    "tier": tier,
                    "kind": kind,
                    "locations": sorted(locs_raw) if locs_raw else None,
                })
            # If we filtered everything out (e.g., provider doesn't enumerate at that granularity), return empty so caller can fallback.
            return items
    except Exception:
        return []


def list_specialized_skus(resource_type: str, location: str, subscription_id: Optional[str]) -> List[Dict[str, Any]]:
    """Enumerate SKUs for resource types where generic provider /skus is insufficient.

    Currently implemented:
      - Microsoft.KeyVault/vaults: static tiers (Standard, Premium) both assumed regionally available if resource type itself is.
      - Microsoft.CognitiveServices/accounts: check availability for F0 and S0 (OpenAI-like tiers) using check_sku_availability.
    Returns list[ {name, details} ] or empty list if not handled.
    """
    rt_lower = resource_type.lower()
    items: List[Dict[str, Any]] = []
    try:
        if rt_lower == "microsoft.keyvault/vaults":
            # Key Vault tiers are globally offered; region restrictions come from resource type availability.
            items = [
                {"name": "standard", "details": "Key Vault Standard"},
                {"name": "premium", "details": "Key Vault Premium"},
            ]
        elif rt_lower == "microsoft.cognitiveservices/accounts":
            # Probe both F0 and S0 via availability API (kind OpenAI). If unavailable still include but add note.
            statuses: Dict[str, str] = {}
            try:
                client = get_cognitiveservices_client(subscription_id)
                kind = "OpenAI"
                rtype = "Microsoft.CognitiveServices/accounts"
                for sku_name in ["F0", "S0"]:
                    try:
                        availability = None
                        if hasattr(client, "locations") and hasattr(client.locations, "check_sku_availability"):
                            availability = client.locations.check_sku_availability(location, [sku_name], kind, rtype)
                        if availability is None and hasattr(client, "accounts") and hasattr(client.accounts, "check_sku_availability"):
                            params = {"kind": kind, "type": rtype, "skus": [sku_name]}
                            availability = client.accounts.check_sku_availability(location, params)
                        avail_flag = False
                        for item in getattr(availability, "value", []) or []:
                            if getattr(item, "sku_name", sku_name) == sku_name and getattr(item, "is_available", False):
                                avail_flag = True
                        statuses[sku_name] = "available" if avail_flag else "unavailable"
                    except Exception:
                        statuses[sku_name] = "unknown"
            except Exception:
                statuses = {"F0": "unknown", "S0": "unknown"}
            items = [
                {"name": sku, "details": status.capitalize() if status != "available" else "Standard" if sku=="S0" else "Free"}
                for sku, status in statuses.items()
            ]
    except Exception:
        return []
    return items


def is_sku_available_for_resource(resource_type: str, sku_name: str, location: str, subscription_id: Optional[str]) -> bool:
    """Best-effort check whether a given SKU exists for the resource type in the region.

    Falls back to True if provider enumeration not possible (to avoid false negatives).
    """
    if not sku_name:
        return True
    # Specialized first
    spec = list_specialized_skus(resource_type, location, subscription_id)
    if spec:
        names = {i["name"].lower() for i in spec if i.get("name")}
        return sku_name.lower() in names
    # Generic provider list
    try:
        provider, _, typ = resource_type.partition('/')
        skus = list_provider_skus(provider, subscription_id, location, typ)
        if not skus:
            return True  # Unknown enumeration ability -> optimistic
        return any(sku_name.lower() == (s.get("name") or "").lower() for s in skus)
    except Exception:
        return True


@ttl_cache(ttl_seconds=600)
def list_vm_sizes(location: str, subscription_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List VM sizes available in a region."""
    compute = get_compute_client(subscription_id)
    sizes = compute.virtual_machine_sizes.list(location)
    return [
        {
            "name": s.name,
            "number_of_cores": s.number_of_cores,
            "os_disk_size_in_mb": s.os_disk_size_in_mb,
            "resource_disk_size_in_mb": s.resource_disk_size_in_mb,
            "memory_in_mb": s.memory_in_mb,
            "max_data_disk_count": s.max_data_disk_count
        }
        for s in sizes
    ]


@ttl_cache(ttl_seconds=600)
def list_compute_resource_skus(location: Optional[str] = None, subscription_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List Microsoft.Compute resource SKUs (VMs, Disks, etc.), optionally filtering by location."""
    compute = get_compute_client(subscription_id)
    result = []
    # Normalize incoming location for case-insensitive comparisons (Azure may return e.g. 'SwedenCentral')
    norm_loc = location.lower() if location else None
    for sku in compute.resource_skus.list():
        locations = sku.locations or []
        if norm_loc and all((l or "").lower() != norm_loc for l in locations):
            # Skip SKUs that do not include the requested location (case-insensitive)
            continue

        # restrictions may disable in the region
        restricted = False
        for r in sku.restrictions or []:
            # Newer SDKs expose locations under restriction_info.locations
            # Fallback to r.locations if present (older SDKs)
            ri = getattr(r, "restriction_info", None)
            ri_locations = []
            if ri is not None:
                ri_locations = getattr(ri, "locations", None) or []
            else:
                ri_locations = getattr(r, "locations", None) or []

            # If no specific locations listed, assume restriction applies generally
            if not ri_locations:
                restricted = True
                break
            # Otherwise, flag restricted if the selected location is within the restriction list
            if location and (location in ri_locations):
                restricted = True
                break

        caps = {}
        for c in sku.capabilities or []:
            caps[c.name] = c.value

        # Extract zone availability and details for this region if present
        zones: List[str] = []
        zone_caps: List[Dict[str, Any]] = []
        for li in getattr(sku, "location_info", []) or []:
            li_loc = getattr(li, "location", None)
            if norm_loc and (li_loc or "").lower() == norm_loc:
                # zones: ["1","2","3"]
                zones = getattr(li, "zones", None) or []
                # zoneDetails: each with capabilities
                for zd in getattr(li, "zone_details", []) or []:
                    caps_map = {}
                    for c in getattr(zd, "capabilities", []) or []:
                        # c.name, c.value
                        caps_map[c.name] = c.value
                    if caps_map:
                        zone_caps.append(caps_map)

        result.append({
            "name": sku.name,
            "tier": sku.tier,
            "resource_type": sku.resource_type,
            "size": sku.size,
            "family": sku.family,
            "locations": locations,
            "restricted": restricted,
            "capabilities": caps,
            "zones": zones,
            "zone_capabilities": zone_caps,
        })
    return result


@ttl_cache(ttl_seconds=300)
def get_compute_usages(location: str, subscription_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return compute usage (quotas) for a region.

    Each item: { name: str, current_value: int, limit: int, unit: str }
    """
    client = get_compute_client(subscription_id)
    try:
        usages = client.usage.list(location)
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for u in usages:
        name = None
        if getattr(u, 'name', None):
            # name is a LocalizableString
            name = getattr(u.name, 'value', None) or getattr(u.name, 'localized_value', None)
        out.append({
            "name": name,
            "current_value": getattr(u, 'current_value', None),
            "limit": getattr(u, 'limit', None),
            "unit": getattr(u, 'unit', None)
        })
    return out


@ttl_cache(ttl_seconds=900)
def is_azure_openai_available(location: str, subscription_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Check if Azure OpenAI (kind=OpenAI) is available in a given region for the subscription.
    Uses Cognitive Services SKU availability API.
    Returns { available: bool, details: str }
    """
    try:
        client = get_cognitiveservices_client(subscription_id)
        kind = "OpenAI"
        rtype = "Microsoft.CognitiveServices/accounts"
        skus = ["S0"]

        availability = None
        # Prefer locations operation group if available (common in recent SDKs)
        if hasattr(client, "locations") and hasattr(client.locations, "check_sku_availability"):
            try:
                availability = client.locations.check_sku_availability(location, skus, kind, rtype)
            except TypeError:
                # Try with keyword args
                availability = client.locations.check_sku_availability(location=location, skus=skus, kind=kind, type=rtype)
        elif hasattr(client, "accounts") and hasattr(client.accounts, "check_sku_availability"):
            try:
                # Some SDKs take a model object/dict as a single param
                params = {"kind": kind, "type": rtype, "skus": skus}
                availability = client.accounts.check_sku_availability(location, params)
            except TypeError:
                # Others take discrete parameters
                availability = client.accounts.check_sku_availability(location=location, skus=skus, kind=kind, type=rtype)

        if availability is None:
            # Fallback: Provider listing
            avail = is_resource_available("Microsoft.CognitiveServices/accounts", location, subscription_id)
            return {"available": bool(avail.get("available")), "details": "Used provider fallback."}

        # availability.value is list of SkuAvailability
        any_available = False
        reasons: List[str] = []
        for item in getattr(availability, "value", []) or []:
            if getattr(item, "is_available", False):
                any_available = True
            else:
                reason = getattr(item, "message", None) or getattr(item, "reason", None)
                if reason:
                    reasons.append(str(reason))
        return {"available": any_available, "details": "; ".join(reasons)}
    except Exception as e:
        # On error, return neutral availability to avoid false "unavailable" results
        return {"available": None, "details": f"AOAI availability check error: {e}"}