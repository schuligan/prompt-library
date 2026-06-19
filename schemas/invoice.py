"""Pydantic model mirroring schemas/invoice.schema.json.

Kept in lockstep with the JSON Schema so the same contract can be enforced
both at decode time (JSON Schema / tool mode) and at parse time (pydantic).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_CCY = re.compile(r"^[A-Z]{3}$")


class LineItem(BaseModel):
    description: str
    quantity: float | None = None
    amount: float | None = None


class Invoice(BaseModel):
    vendor_name: str | None
    invoice_number: str | None
    invoice_date: str | None
    currency: str | None
    subtotal: float | None
    tax: float | None
    total: float | None
    line_items: list[LineItem]

    @field_validator("invoice_date")
    @classmethod
    def _check_date(cls, v: str | None) -> str | None:
        if v is not None and not _ISO_DATE.match(v):
            raise ValueError("invoice_date must be YYYY-MM-DD or null")
        return v

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, v: str | None) -> str | None:
        if v is not None and not _ISO_CCY.match(v):
            raise ValueError("currency must be a 3-letter ISO-4217 code or null")
        return v
