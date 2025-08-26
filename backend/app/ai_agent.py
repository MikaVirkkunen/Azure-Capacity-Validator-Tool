import json
import os
from typing import Dict, Any

import inspect
import logging

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

logger = logging.getLogger("ai_agent")


def _ensure_httpx_proxies_compat():  # pragma: no cover (simple monkeypatch)
    """Shim for openai versions passing 'proxies' to httpx>=0.28 (which removed the param).

    Safe to remove once using openai/httpx combo that no longer sends 'proxies'. Can be disabled
    via OPENAI_HTTPX_DISABLE_SHIM=1.
    """
    if os.getenv("OPENAI_HTTPX_DISABLE_SHIM"):
        return
    try:
        import httpx  # type: ignore
        sig = inspect.signature(httpx.Client.__init__)
        if 'proxies' in sig.parameters:
            return  # legacy version that still supports proxies kw
        if getattr(httpx.Client, '__wrapped_for_proxies__', False):
            return
        original = httpx.Client

        def patched_client(*args, **kwargs):  # type: ignore
            if 'proxies' in kwargs:
                kwargs.pop('proxies', None)
            return original(*args, **kwargs)

        patched_client.__wrapped_for_proxies__ = True  # type: ignore
        httpx.Client = patched_client  # type: ignore
        logger.warning("Applied httpx.Client proxies shim (removed 'proxies' kw).")
    except Exception as e:  # pragma: no cover
        logger.debug(f"Did not apply proxies shim: {e}")


def _get_azure_openai_client() -> AzureOpenAI:
    endpoint = os.getenv("AVATAR_AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise RuntimeError("Azure OpenAI endpoint not set: AVATAR_AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    key = os.getenv("AVATAR_AZURE_OPENAI_KEY")
    _ensure_httpx_proxies_compat()

    if key:
        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=key,
            api_version=api_version,
        )

    credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version,
    )


def generate_initial_plan(prompt: str) -> Dict[str, Any]:
    """Generate a JSON plan using Azure OpenAI; always returns parsed JSON dict."""
    deployment = os.getenv("AVATAR_AZURE_OPENAI_DEPLOYMENT")
    if not deployment:
        raise RuntimeError("AVATAR_AZURE_OPENAI_DEPLOYMENT is not set.")

    client = _get_azure_openai_client()
    system = (
        "You are an assistant that produces STRICT JSON for Azure resource capacity validation. "
        "Output only JSON. "
        "Schema: {\"region\": \"<azure-region>\", \"resources\": [{\"resource_type\": \"<RP/type>\", \"sku\": \"<sku-or-size>\", \"features\": {}, \"quantity\": <int>}]}"
    )
    user = (
        "Create a minimal plan based on the user's description. Include any relevant Azure resource types, not just compute. "
        "Examples: Microsoft.Compute/virtualMachines, Microsoft.Compute/disks, Microsoft.Storage/storageAccounts, Microsoft.Network/publicIPAddresses, "
        "Microsoft.KeyVault/vaults, Microsoft.CognitiveServices/accounts, Microsoft.Web/sites. "
        "Prefer realistic SKUs when mentioned; otherwise leave sku empty for non-compute. "
        "Do not invent regions; if not provided, use 'westeurope'.\n\n"
        f"User input:\n{prompt}"
    )

    try:
        resp = client.chat.completions.create(
            model=deployment,
            temperature=1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except TypeError as te:
        if 'proxies' in str(te).lower():
            raise RuntimeError("OpenAI/httpx mismatch (proxies kw). Pin httpx<0.28 or rely on shim.") from te
        raise

    content = resp.choices[0].message.content
    return json.loads(content)
