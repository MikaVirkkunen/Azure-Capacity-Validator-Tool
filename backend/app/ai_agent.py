import json
import os
from typing import Dict, Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI


def _get_azure_openai_client() -> AzureOpenAI:
    endpoint = os.getenv("AVATAR_AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise RuntimeError("Azure OpenAI endpoint not set: AVATAR_AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    key = os.getenv("AVATAR_AZURE_OPENAI_KEY")
    if key:
        # Key-based auth (fallback)
        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=key,
            api_version=api_version,
        )

    # Preferred: Azure AD (modern auth)
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    return AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version,
    )


def generate_initial_plan(prompt: str) -> Dict[str, Any]:
    """
    Use Azure OpenAI to draft a structured plan JSON the backend can validate.
    The backend will still validate every item against live Azure APIs.
    """
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
        "Create a minimal plan based on the user's description. Only include resources that can be validated with Microsoft.Compute today: "
        "Microsoft.Compute/virtualMachines (use VM sizes like Standard_D4s_v5), Microsoft.Compute/disks (use SKUs like Premium_LRS, StandardSSD_LRS). "
        "You may include quantity. Do not invent regions; if not provided, propose 'westeurope'.\n\n"
        f"User input:\n{prompt}"
    )

    resp = client.chat.completions.create(
        model=deployment,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = resp.choices[0].message.content
    return json.loads(content)