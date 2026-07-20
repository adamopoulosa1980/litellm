import sys
import types
from unittest.mock import AsyncMock

import pytest

from litellm.proxy._experimental.mcp_server.config_watcher import watch_mcp_config_file


class _FakeAwatch:
    """Stands in for watchfiles.awatch: an async iterator that yields the given
    change batches once, then stops (so the watch loop terminates in-test)."""

    def __init__(self, batches):
        self._batches = list(batches)

    def __call__(self, *args, **kwargs):
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._batches:
            raise StopAsyncIteration
        return self._batches.pop(0)


def _install_fake_watchfiles(monkeypatch, batches):
    monkeypatch.setitem(sys.modules, "watchfiles", types.SimpleNamespace(awatch=_FakeAwatch(batches)))


@pytest.mark.asyncio
async def test_watch_reloads_on_each_change(monkeypatch):
    reload_fn = AsyncMock(return_value=("pollinations",))
    _install_fake_watchfiles(
        monkeypatch,
        [{("modified", "config.yaml")}, {("modified", "config.yaml")}],
    )

    await watch_mcp_config_file("config.yaml", reload_fn)

    assert reload_fn.await_count == 2


@pytest.mark.asyncio
async def test_watch_survives_reload_error(monkeypatch):
    reload_fn = AsyncMock(side_effect=[RuntimeError("half-written config"), ("pollinations",)])
    _install_fake_watchfiles(
        monkeypatch,
        [{("modified", "config.yaml")}, {("modified", "config.yaml")}],
    )

    await watch_mcp_config_file("config.yaml", reload_fn)

    assert reload_fn.await_count == 2


@pytest.mark.asyncio
async def test_watch_no_op_when_watchfiles_missing(monkeypatch):
    reload_fn = AsyncMock()
    monkeypatch.setitem(sys.modules, "watchfiles", None)

    await watch_mcp_config_file("config.yaml", reload_fn)

    reload_fn.assert_not_awaited()
