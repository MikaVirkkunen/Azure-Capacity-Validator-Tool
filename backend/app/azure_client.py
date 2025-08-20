import os
from typing import List, Optional, Dict, Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.compute import ComputeManagementClient


def get_default_credential() -> DefaultAzureCredential:
    # Supports: Azure CLI, Managed Identity, Env Vars (Client ID/Secret), etc.
    # For local use, 'az login' is easiest.
    return DefaultAzureCredential(
        exclude_interactive_browser_credential=False
    )


def get_subscription_client(credential: Optional[DefaultAzureCredential] = None) -> SubscriptionClient:
    cred = credential or get_default_credential()
    return SubscriptionClient(cred)


def list_subscriptions() -> List[Dict[str, Any]]:
    client = get_subscription_client()
    subs = []
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


def get_compute_client(subscription_id: Optional[str] = None) -> ComputeManagementClient:
    sub_id = subscription_id or get_default_subscription_id()
    if not sub_id:
        raise RuntimeError("No Azure subscription available. Login with 'az login' or set AZURE_SUBSCRIPTION_ID.")
    cred = get_default_credential()
    return ComputeManagementClient(cred, sub_id)


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


def list_compute_resource_skus(location: Optional[str] = None, subscription_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List Microsoft.Compute resource SKUs (VMs, Disks, etc.), optionally filtering by location."""
    compute = get_compute_client(subscription_id)
    result = []
    for sku in compute.resource_skus.list():
        locations = sku.locations or []
        if location and (location not in locations):
            continue

        # restrictions may disable in the region
        restricted = False
        for r in sku.restrictions or []:
            if (not r.locations) or (location in (r.locations or [])):
                restricted = True
                break

        caps = {}
        for c in sku.capabilities or []:
            caps[c.name] = c.value

        result.append({
            "name": sku.name,
            "tier": sku.tier,
            "resource_type": sku.resource_type,
            "size": sku.size,
            "family": sku.family,
            "locations": locations,
            "restricted": restricted,
            "capabilities": caps
        })
    return result