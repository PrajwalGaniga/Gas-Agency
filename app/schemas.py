from pydantic import BaseModel, Field
from typing import Optional

class DriverLogin(BaseModel):
    phone_number: str = Field(..., max_length=15)
    password: str = Field(...)

class AcceptOrderRequest(BaseModel):
    order_id: str

class CompleteOrderRequest(BaseModel):
    order_id: str
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    empties_collected: int = Field(default=0, ge=0)
    payment_mode: str = Field(default="CASH") # CASH or UPI
    amount_collected: float = Field(default=0.0, ge=0.0)

class LocationPing(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)

class ChangeRequestPayload(BaseModel):
    customer_id: str
    category: str
    new_details: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    order_id: Optional[str] = None

class ReportIssueRequest(BaseModel):
    issue_type: str = Field(...)
    remarks: str = Field("")
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)

class StartShiftRequest(BaseModel):
    driver_id: str
    admin_id: str
    full_cylinders: int = Field(..., ge=1)
    empty_cylinders: int = Field(default=0, ge=0)

class CloseShiftRequest(BaseModel):
    driver_id: str
    admin_id: str
    actual_cash: float = Field(default=0, ge=0)
    returned_full: int = Field(default=0, ge=0)
    returned_empty: int = Field(default=0, ge=0)
