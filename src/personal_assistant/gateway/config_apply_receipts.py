"""Durable write-ahead receipts for Gateway Agent configuration operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import os
from pathlib import Path
import threading
from typing import Mapping
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ConfigOperationReceipt:
    """Persist one recoverable Agent configuration operation.

    Args:
        operation_id: Stable caller-provided idempotency identity.
        kind: ``create`` or ``apply``.
        candidate_fingerprint: Fingerprint supplied and verified by the caller.
        expected_previous_fingerprint: Expected current Gateway Agent state.
        candidate: Canonical non-secret Gateway Agent candidate.
        desired_state_fingerprint: Fingerprint of the resolved durable candidate.
        status: ``prepared``, ``applied`` or ``rejected``.
        error_code: Stable rejection code when rejected.
        message: Human-readable rejection detail when rejected.
    """

    operation_id: str
    kind: str
    candidate_fingerprint: str
    expected_previous_fingerprint: str | None
    candidate: dict[str, object]
    desired_state_fingerprint: str
    status: str = "prepared"
    error_code: str | None = None
    message: str | None = None


class OperationIdReusedError(ValueError):
    """Report reuse of one operation id for a different candidate."""


class ConfigApplyReceiptStore:
    """Own a small atomic JSON store of Gateway config-operation receipts.

    Args:
        path: Durable JSON file colocated with the Gateway config.
    """

    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()
        self._lock = threading.RLock()

    def get(self, operation_id: str) -> ConfigOperationReceipt | None:
        """Return one persisted receipt, if present."""

        with self._lock:
            return self._read_all().get(operation_id)

    def prepare(
        self,
        *,
        operation_id: str,
        kind: str,
        candidate_fingerprint: str,
        expected_previous_fingerprint: str | None,
        candidate: Mapping[str, object],
        desired_state_fingerprint: str,
    ) -> ConfigOperationReceipt:
        """Durably establish an operation before any mutable side effect.

        Raises:
            OperationIdReusedError: When the id already names another candidate.
        """

        with self._lock:
            receipts = self._read_all()
            existing = receipts.get(operation_id)
            if existing is not None:
                if (
                    existing.kind != kind
                    or existing.candidate_fingerprint != candidate_fingerprint
                    or existing.expected_previous_fingerprint
                    != expected_previous_fingerprint
                ):
                    raise OperationIdReusedError(
                        "operation_id is already bound to a different operation intent"
                    )
                return existing
            receipt = ConfigOperationReceipt(
                operation_id=operation_id,
                kind=kind,
                candidate_fingerprint=candidate_fingerprint,
                expected_previous_fingerprint=expected_previous_fingerprint,
                candidate=dict(candidate),
                desired_state_fingerprint=desired_state_fingerprint,
            )
            receipts[operation_id] = receipt
            self._write_all(receipts)
            return receipt

    def finish(
        self,
        operation_id: str,
        *,
        status: str,
        error_code: str | None = None,
        message: str | None = None,
    ) -> ConfigOperationReceipt:
        """Durably write one terminal result and return it."""

        if status not in {"applied", "rejected"}:
            raise ValueError("terminal receipt status must be applied or rejected")
        with self._lock:
            receipts = self._read_all()
            current = receipts.get(operation_id)
            if current is None:
                raise KeyError(operation_id)
            if current.status in {"applied", "rejected"}:
                return current
            updated = replace(
                current,
                status=status,
                error_code=error_code,
                message=message,
            )
            receipts[operation_id] = updated
            self._write_all(receipts)
            return updated

    def _read_all(self) -> dict[str, ConfigOperationReceipt]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("version") != 1:
            raise ValueError("unsupported config operation receipt store")
        records = raw.get("operations")
        if not isinstance(records, dict):
            raise ValueError("config operation receipt store is malformed")
        return {
            operation_id: ConfigOperationReceipt(**payload)
            for operation_id, payload in records.items()
            if isinstance(operation_id, str) and isinstance(payload, dict)
        }

    def _write_all(self, receipts: Mapping[str, ConfigOperationReceipt]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "operations": {
                operation_id: asdict(receipt)
                for operation_id, receipt in receipts.items()
            },
        }
        temp_path = self._path.with_name(f".{self._path.name}.{uuid4().hex}.tmp")
        data = json.dumps(
            payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._path)
            directory_fd = os.open(self._path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temp_path.unlink(missing_ok=True)


__all__ = [
    "ConfigApplyReceiptStore",
    "ConfigOperationReceipt",
    "OperationIdReusedError",
]
