import pytest
from fastapi.testclient import TestClient

from app.main import app

# Monkeypatch azure_client functions to avoid real Azure calls
@pytest.fixture(autouse=True)
def _mock_azure(monkeypatch):
    monkeypatch.setattr('app.azure_client.list_vm_sizes', lambda region, subscription_id=None: [
        {"name": "Standard_D2s_v5"}, {"name": "Standard_D4s_v5"}
    ])
    # Return a minimal set of compute resource skus
    monkeypatch.setattr('app.azure_client.list_compute_resource_skus', lambda region, subscription_id=None: [
        {"name": "Standard_D4s_v5", "size": "Standard_D4s_v5", "resource_type": "virtualMachines", "tier": "Standard", "family": "Dsv5", "zones": ["1"], "capabilities": {}} ,
        {"name": "Premium_LRS", "resource_type": "disks", "size": None, "tier": "Premium", "family": None, "zones": [], "capabilities": {}, "restricted": False}
    ])
    monkeypatch.setattr('app.azure_client.is_resource_available', lambda rt, region, subscription_id=None: {"available": True})
    monkeypatch.setattr('app.azure_client.is_azure_openai_available', lambda region, subscription_id=None: {"available": True, "details": ""})
    monkeypatch.setattr('app.azure_client.get_default_subscription_id', lambda: 'sub-1234')


def test_validate_plan_vm_and_disk():
    client = TestClient(app)
    payload = {
        "region": "westeurope",
        "resources": [
            {"resource_type": "Microsoft.Compute/virtualMachines", "sku": "Standard_D4s_v5", "quantity": 2},
            {"resource_type": "Microsoft.Compute/disks", "sku": "Premium_LRS", "quantity": 1}
        ]
    }
    res = client.post('/api/validate-plan', json=payload)
    assert res.status_code == 200
    data = res.json()
    statuses = [r['status'] for r in data['results']]
    assert statuses == ['available', 'available']


def test_validate_plan_missing_vm_size():
    client = TestClient(app)
    payload = {
        "region": "westeurope",
        "resources": [
            {"resource_type": "Microsoft.Compute/virtualMachines", "sku": "NonExistent_Size"}
        ]
    }
    res = client.post('/api/validate-plan', json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data['results'][0]['status'] == 'unavailable'
