from typing import Awaitable, Callable

from litellm._logging import verbose_proxy_logger


async def watch_mcp_config_file(
    config_file_path: str,
    reload_fn: Callable[[], Awaitable[tuple[str, ...]]],
) -> None:
    """Watch ``config_file_path`` and hot-reload config-declared MCP servers on change.

    Relies on ``watchfiles`` (an optional ``uvicorn[standard]`` dependency) for debounced
    filesystem events, mirroring uvicorn's own reloader. A no-op with a warning when
    ``watchfiles`` is unavailable. Each reload is guarded so a transient failure (for
    example a half-written file caught mid-save) logs and keeps the watch loop alive
    rather than tearing the whole worker down.

    Args:
        config_file_path: Absolute or relative path to the proxy config file to watch.
        reload_fn: Awaitable that re-reads the config and rebuilds the MCP registry,
            returning the loaded server names.
    """
    try:
        from watchfiles import awatch  # pyright: ignore[reportUnknownVariableType]  # optional, untyped dep (uvicorn[standard])
    except ImportError:
        verbose_proxy_logger.warning(
            "mcp_config_hot_reload is enabled but the 'watchfiles' package is not installed; "
            "MCP config file watching is disabled. Install watchfiles (or uvicorn[standard]) to enable it."
        )
        return

    verbose_proxy_logger.info("Watching %s for MCP config changes (hot-reload enabled)", config_file_path)
    async for _changes in awatch(config_file_path):  # pyright: ignore[reportUnknownVariableType]  # awatch yields untyped change sets
        try:
            loaded = await reload_fn()
            verbose_proxy_logger.info(
                "MCP config hot-reload applied %d server(s): %s",
                len(loaded),
                ", ".join(loaded) or "<none>",
            )
        except Exception as e:  # noqa: BLE001  # a bad/partial config edit must not kill the watch loop
            verbose_proxy_logger.warning("MCP config hot-reload failed; keeping previously loaded servers: %s", e)
