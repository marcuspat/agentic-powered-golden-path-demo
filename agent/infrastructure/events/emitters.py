"""Event emitters."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from agent.domain.events import EventEnvelope
from agent.domain.ports import EventEmitterPort

logger = logging.getLogger(__name__)


class LoggingEmitter(EventEmitterPort):
    """Emit events as structured INFO log records."""

    def emit(self, envelope: EventEnvelope) -> None:
        logger.info(
            "event %s",
            envelope.to_json(),
            extra={"correlation_id": envelope.correlation_id, "event": envelope.name},
        )


class JsonlEmitter(EventEmitterPort):
    """Append-only JSON-Lines file emitter (also logs to logger)."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._inner = LoggingEmitter()

    def emit(self, envelope: EventEnvelope) -> None:
        self._inner.emit(envelope)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(envelope.to_json())
            fh.write("\n")


class CompositeEmitter(EventEmitterPort):
    def __init__(self, *emitters: EventEmitterPort) -> None:
        self._emitters = emitters

    def emit(self, envelope: EventEnvelope) -> None:
        for emitter in self._emitters:
            try:
                emitter.emit(envelope)
            except Exception:  # pragma: no cover
                logger.exception("event.emitter_failed emitter=%s", type(emitter).__name__)


class NullEmitter(EventEmitterPort):
    def emit(self, envelope: EventEnvelope) -> None:  # pragma: no cover
        pass
