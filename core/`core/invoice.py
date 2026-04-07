from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class InvoiceLine(BaseModel):
    """Single line item on an invoice."""
    line_id: str = Field(..., description="Unique line identifier")
    description: str
    quantity: int
    unit_price: Decimal
    total: Decimal


class Invoice(BaseModel):
    """Structured invoice used by Marcel-Arch."""
    invoice_id: str
    vendor_name: str
    currency: str = "USD"
    units_purchased: Optional[int] = None  # for simple volume rules
    total_amount: Decimal
    lines: List[InvoiceLine] = Field(default_factory=list)
