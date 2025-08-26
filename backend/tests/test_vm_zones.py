import pytest
pytestmark = pytest.mark.xfail(reason="Zone validation feature removed", strict=False)

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(autouse=True)
def _mock_compute(monkeypatch):
    # ensure any prior cached values are cleared so zones reflect this test's monkeypatch
    import app.main as main
    try:
        main.list_compute_resource_skus.invalidate()  # type: ignore[attr-defined]
        main.list_vm_sizes.invalidate()  # type: ignore[attr-defined]
    except Exception:
        pass
    monkeypatch.setattr('app.main.list_vm_sizes', lambda region, subscription_id=None: [
        {"name": "Standard_D4s_v5"}
    ])
    monkeypatch.setattr('app.main.list_compute_resource_skus', lambda region, subscription_id=None: [
        {"name": "Standard_D4s_v5", "size": "Standard_D4s_v5", "resource_type": "virtualMachines", "tier": "Standard", "family": "Dsv5", "zones": ["1"], "capabilities": {}}
    ])
    monkeypatch.setattr('app.main.get_default_subscription_id', lambda: 'sub-1234')


def test_vm_zone_happy():
    # Deprecated test kept for backward compatibility; now no zones field logic.
    client = TestClient(app)
    payload = {"region": "westeurope", "resources": [
        {"resource_type": "Microsoft.Compute/virtualMachines", "sku": "Standard_D4s_v5"}
    ]}
    r = client.post('/api/validate-plan', json=payload)
    assert r.status_code == 200


def test_vm_zone_missing():
    # Deprecated test (zones removed)
    client = TestClient(app)
    payload = {"region": "westeurope", "resources": [
        {"resource_type": "Microsoft.Compute/virtualMachines", "sku": "Standard_D4s_v5"}
    ]}
    r = client.post('/api/validate-plan', json=payload)
    assert r.status_code == 200