"""StackSelectionService — pick a Stack from the catalog for a given intent."""
from __future__ import annotations

from agent.domain.aggregates.stack import Stack
from agent.domain.errors import StackNotFound
from agent.domain.ports import StackRepositoryPort
from agent.domain.values import ExtractedIntent


class StackSelectionService:
    def __init__(self, stack_repository: StackRepositoryPort) -> None:
        self._stacks = stack_repository

    def select(self, intent: ExtractedIntent) -> Stack:
        try:
            return self._stacks.get(intent.stack)
        except StackNotFound:
            raise
        except Exception as exc:  # pragma: no cover — defensive
            raise StackNotFound(f"Failed to load stack {intent.stack}: {exc}") from exc
