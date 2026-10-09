"""The renderer restarts a dead game once, only when asked to."""

import asyncio
from typing import Any
from unittest import mock

import pytest

from src.orchestration.live_render import GameUnavailableError, LiveRenderer


class DeadBackend:
    """A backend that never answers, then answers after ``alive_after`` reconnects."""

    def __init__(self, alive_after: int) -> None:
        self.reconnects = 0
        self._alive_after = alive_after

    async def reconnect(self) -> None:
        """Count the attempt."""
        self.reconnects += 1

    async def ping(self) -> None:
        """Fail until the game is back."""
        if self.reconnects < self._alive_after:
            raise TimeoutError("no answer")


def _recover(renderer: LiveRenderer) -> None:
    asyncio.run(renderer.recover(wait_seconds=0.0, attempts=3))


def test_relaunches_once_then_reconnects() -> None:
    """The first failed ping runs the relaunch command, a later ping succeeds."""
    backend: Any = DeadBackend(2)
    renderer = LiveRenderer(backend, relaunch_command=["start-game"])
    with mock.patch("src.orchestration.live_render.subprocess.run") as run:
        _recover(renderer)
    run.assert_called_once_with(["start-game"], check=False)


def test_no_relaunch_without_command() -> None:
    """Without a command the old behaviour holds: wait, then give up."""
    backend: Any = DeadBackend(99)
    renderer = LiveRenderer(backend)
    with mock.patch("src.orchestration.live_render.subprocess.run") as run:
        with pytest.raises(GameUnavailableError):
            _recover(renderer)
    run.assert_not_called()
