"""
carewatcher/audit/logger.py
Append-only, hash-chained audit log stored as local JSONL.

Every decision — proposals, approvals, rejections, escalations, sensor events —
is recorded with a cryptographic hash chain to detect tampering.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from carewatcher.interfaces import AuditEntry


class AuditLogger:
    """Append-only, hash-chained audit log.

    Each entry's hash is computed over all its fields plus the previous
    entry's hash.  Any tampering (edit, delete, reorder) breaks the chain.

    Parameters
    ----------
    log_path:
        Filesystem path for the JSONL audit log.
    hash_algorithm:
        Hash algorithm name (default: sha256).
    """

    def __init__(
        self,
        log_path: str | Path = "data/audit.jsonl",
        hash_algorithm: str = "sha256",
    ) -> None:
        self.log_path = Path(log_path)
        self.hash_algorithm = hash_algorithm
        self._lock = threading.Lock()
        self._sequence: int = 0
        self._prev_hash: str = ""

        # Create parent directories and recover chain state
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._recover_chain_state()

    def _recover_chain_state(self) -> None:
        """Read the last entry to recover sequence number and prev_hash."""
        if not self.log_path.exists():
            return
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                last_line = ""
                for line in f:
                    if line.strip():
                        last_line = line.strip()
                if last_line:
                    data = json.loads(last_line)
                    self._sequence = data.get("sequence", 0)
                    self._prev_hash = data.get("entry_hash", "")
        except (json.JSONDecodeError, OSError):
            # Corrupted or empty log — start fresh
            pass

    # ── public API ────────────────────────────────────────────────────

    def append(
        self,
        event_type: str,
        payload: dict[str, object],
    ) -> AuditEntry:
        """Write a new entry to the audit log and return it.

        The entry is hash-chained to the previous entry. The hash covers:
        sequence, timestamp, event_type, payload, and prev_hash.
        """
        with self._lock:
            self._sequence += 1
            now = datetime.now()

            entry = AuditEntry(
                sequence=self._sequence,
                timestamp=now,
                event_type=event_type,
                payload=payload,
                prev_hash=self._prev_hash,
                entry_hash="",  # computed below
            )

            # Compute hash
            entry_hash = entry.compute_hash()
            # Reconstruct with the computed hash (frozen dataclass)
            entry = AuditEntry(
                sequence=entry.sequence,
                timestamp=entry.timestamp,
                event_type=entry.event_type,
                payload=entry.payload,
                prev_hash=entry.prev_hash,
                entry_hash=entry_hash,
            )

            # Write to file
            record = {
                "sequence": entry.sequence,
                "timestamp": entry.timestamp.isoformat(),
                "event_type": entry.event_type,
                "payload": entry.payload,
                "prev_hash": entry.prev_hash,
                "entry_hash": entry.entry_hash,
            }
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")

            self._prev_hash = entry_hash
            return entry

    def verify_chain(self) -> bool:
        """Verify the integrity of the entire audit log.

        Returns True if every entry's hash is correct and chains properly
        to its predecessor.  Returns False if any tampering is detected.
        """
        if not self.log_path.exists():
            return True  # Empty log is valid

        prev_hash = ""
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    return False

                # Check prev_hash chain
                if data.get("prev_hash", "") != prev_hash:
                    return False

                # Reconstruct entry and verify hash
                entry = AuditEntry(
                    sequence=data["sequence"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    event_type=data["event_type"],
                    payload=data["payload"],
                    prev_hash=data["prev_hash"],
                    entry_hash="",
                )
                computed = entry.compute_hash()
                if computed != data.get("entry_hash", ""):
                    return False

                prev_hash = data["entry_hash"]

        return True

    def get_entries(self, limit: int = 50) -> list[dict[str, Any]]:
        """Read the last N entries from the audit log."""
        if not self.log_path.exists():
            return []

        entries: list[dict[str, Any]] = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return entries[-limit:]

    def entry_count(self) -> int:
        """Return the total number of entries in the log."""
        if not self.log_path.exists():
            return 0
        count = 0
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count
