"""Response dataclasses for SUNAT web service operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BillResponse:
    """Response from sendBill."""

    success: bool
    cdr_bytes: bytes | None = None
    cdr_code: str | None = None
    cdr_description: str | None = None
    hash_value: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class SummaryResponse:
    """Response from sendSummary."""

    success: bool
    ticket: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class StatusResponse:
    """Response from getStatus."""

    success: bool
    status_code: str | None = None
    cdr_bytes: bytes | None = None
    cdr_code: str | None = None
    cdr_description: str | None = None
    error_code: str | None = None
    error_message: str | None = None
