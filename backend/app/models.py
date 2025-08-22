from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


class ValidationStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class PlanResource(BaseModel):
    # type examples: "Microsoft.Compute/virtualMachines", "Microsoft.Compute/disks"
    resource_type: str = Field(..., description="Azure resource type, e.g., Microsoft.Compute/virtualMachines")
    sku: Optional[str] = Field(None, description="SKU or size, e.g., Standard_D4s_v5 or Premium_LRS")
    features: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Feature flags or requirements")
    quantity: Optional[int] = Field(default=1)


class Plan(BaseModel):
    subscription_id: Optional[str] = None
    region: str
    resources: List[PlanResource]


class ValidationResultItem(BaseModel):
    resource: PlanResource
    status: ValidationStatus
    details: Optional[str] = None
    references: Optional[List[str]] = None


class ValidationResponse(BaseModel):
    region: str
    subscription_id: Optional[str]
    results: List[ValidationResultItem]