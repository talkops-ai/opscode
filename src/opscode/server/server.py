"""LangGraph server lifecycle management for the app.

Handles starting/stopping a `langgraph dev` server process and generating the
required `langgraph.json` configuration file.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import subprocess  # noqa: S404
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import quote

from opscode.server import SERVER_ENV_PREFIX

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "127.0.0.1"
_EPHEMERAL_PORT = 0
_HEALTH_POLL_INTERVAL_LOCAL = 0.1
_HEALTH_POLL_INTERVAL_REMOTE = 0.3
_HEALTH_TIMEOUT = 60
_SHUTDOWN_TIMEOUT = 0.5
_LOG_TAIL_CHARS = 3000
_STARTUP_ERROR_MARKER = "OPSCODE_STARTUP_ERROR:"
_INHERITED_PYTHONPATH_ENV = "OPSCODE_INHERITED_PYTHONPATH"

_SERVER_ENV_DENYLIST = frozenset(
    {
        "DYLD_INSERT_LIBRARIES",
        "DYLD_LIBRARY_PATH",
        "GIT_ASKPASS",
        "LD_AUDIT",
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
        "NODE_OPTIONS",
        "PYTHONEXECUTABLE",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "SSH_ASKPASS",
    }
)


def _port_in_use(host: str, port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            return True
        else:
            return False


def _find_free_port(host: str) -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def get_server_url(host: str = _DEFAULT_HOST, port: int = _EPHEMERAL_PORT) -> str:
    return f"http://{host}:{port}"


def _extract_startup_error_marker(output: str) -> str | None:
    for line in reversed(output.splitlines()):
        if _STARTUP_ERROR_MARKER in line:
            _, summary = line.rsplit(_STARTUP_ERROR_MARKER, 1)
            return summary.strip() or None
    return None


def generate_langgraph_json(
    output_dir: str | Path,
    *,
    graph_ref: str = "./server_graph.py:make_graph",
    env_file: str | None = None,
    checkpointer_path: str | None = None,
) -> Path:
    config: dict[str, Any] = {
        "dependencies": ["."],
        "graphs": {
            "agent": graph_ref,
        },
    }
    if env_file:
        config["env"] = env_file
    if checkpointer_path:
        config["checkpointer"] = {"path": checkpointer_path}

    output_path = Path(output_dir) / "langgraph.json"
    output_path.write_text(json.dumps(config, indent=2))
    return output_path


@contextlib.contextmanager
def _scoped_env_overrides(
    overrides: dict[str, str],
) -> Iterator[None]:
    prev: dict[str, str | None] = {}
    for key, val in overrides.items():
        prev[key] = os.environ.get(key)
        os.environ[key] = val
    try:
        yield
    except Exception:
        for key, old_val in prev.items():
            if old_val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_val
        raise


async def wait_for_server_healthy(
    url: str,
    *,
    timeout: float = _HEALTH_TIMEOUT,
    process: subprocess.Popen | None = None,
    read_log: Callable[[], str] | None = None,
    local: bool = False,
) -> None:
    import httpx

    poll_interval = (
        _HEALTH_POLL_INTERVAL_LOCAL if local else _HEALTH_POLL_INTERVAL_REMOTE
    )
    health_url = f"{url}/ok"
    deadline = time.monotonic() + timeout
    last_status: int | None = None
    last_exc: Exception | None = None

    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            if process and process.poll() is not None:
                output = read_log() if read_log else ""
                msg = f"Server process exited with code {process.returncode}"
                if output:
                    summary = _extract_startup_error_marker(output)
                    if summary:
                        msg += f": {summary}"
                    msg += f"\n{output[-_LOG_TAIL_CHARS:]}"
                raise RuntimeError(msg)

            try:
                resp = await client.get(health_url, timeout=2)
                if resp.status_code == 200:
                    logger.info("Server is healthy at %s", url)
                    return
                last_status = resp.status_code
                logger.debug("Health check returned status %d", resp.status_code)
            except (httpx.TransportError, OSError) as exc:
                logger.debug("Health check attempt failed: %s", exc)
                last_exc = exc

            await asyncio.sleep(poll_interval)

    msg = f"Server did not become healthy within {timeout}s"
    if last_status is not None:
        msg += f" (last status: {last_status})"
    elif last_exc is not None:
        msg += f" (last error: {last_exc})"
    raise RuntimeError(msg)


def _build_server_cmd(config_path: Path, *, host: str, port: int) -> list[str]:
    # Use system python with langgraph dev server
    return [
        sys.executable,
        "-m",
        "langgraph_cli",
        "dev",
        "--host",
        host,
        "--port",
        str(port),
        "--no-browser",
        "--no-reload",
        "--config",
        str(config_path),
    ]


def _build_server_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["LANGGRAPH_AUTH_TYPE"] = "noop"

    env.pop(_INHERITED_PYTHONPATH_ENV, None)
    inherited_pythonpath = os.environ.get("PYTHONPATH")

    for key in (
        "LANGGRAPH_AUTH",
        "LANGGRAPH_CLOUD_LICENSE_KEY",
        "LANGSMITH_CONTROL_PLANE_API_KEY",
        "LANGSMITH_TENANT_ID",
        *_SERVER_ENV_DENYLIST,
    ):
        env.pop(key, None)

    if inherited_pythonpath is not None:
        env[_INHERITED_PYTHONPATH_ENV] = inherited_pythonpath
    return env


class ServerProcess:
    """Manages a `langgraph dev` server subprocess."""

    def __init__(
        self,
        *,
        host: str = _DEFAULT_HOST,
        port: int = _EPHEMERAL_PORT,
        config_dir: str | Path | None = None,
        owns_config_dir: bool = False,
        scaffold: Callable[[Path], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.config_dir = Path(config_dir) if config_dir else None
        self._owns_config_dir = owns_config_dir
        self._scaffold = scaffold
        self._process: subprocess.Popen[bytes] | None = None
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._log_file: Any = None
        self._env_overrides: dict[str, str] = {}
        self._persistent_env_overrides: dict[str, str] = {}

    @property
    def url(self) -> str:
        return get_server_url(self.host, self.port)

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _read_log_file(self) -> str:
        if self._log_file is None:
            return ""
        try:
            self._log_file.flush()
            return Path(self._log_file.name).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            logger.warning(
                "Failed to read server log file %s",
                self._log_file.name,
                exc_info=True,
            )
            return ""

    async def start(
        self,
        *,
        timeout: float = _HEALTH_TIMEOUT,
    ) -> None:
        if self.running:
            return

        work_dir = self.config_dir
        if work_dir is None:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="opscode_server_")
            work_dir = Path(self._temp_dir.name)

        config_path = work_dir / "langgraph.json"
        if not config_path.exists() and self._scaffold is not None:
            logger.info("langgraph.json missing in %s; rescaffolding", work_dir)
            try:
                work_dir.mkdir(parents=True, exist_ok=True)
                self._scaffold(work_dir)
            except OSError as exc:
                msg = f"Failed to rescaffold server workspace at {work_dir}: {exc}"
                raise RuntimeError(msg) from exc

        if not config_path.exists():
            msg = (
                f"langgraph.json not found in {work_dir}. "
                "Call generate_langgraph_json() first."
            )
            raise RuntimeError(msg)

        if self.port == _EPHEMERAL_PORT:
            self.port = _find_free_port(self.host)
            logger.info("Using ephemeral port %d for langgraph dev server", self.port)
        elif _port_in_use(self.host, self.port):
            self.port = _find_free_port(self.host)
            logger.info("Requested port in use, using port %d instead", self.port)

        cmd = _build_server_cmd(config_path, host=self.host, port=self.port)
        env = _build_server_env()
        env.update(self._persistent_env_overrides)
        env.update(self._env_overrides)

        logger.info("Starting langgraph dev server: %s", " ".join(cmd))
        self._log_file = tempfile.NamedTemporaryFile(
            prefix="opscode_server_log_",
            suffix=".txt",
            delete=False,
            mode="w",
            encoding="utf-8",
        )
        self._process = subprocess.Popen(
            cmd,
            cwd=str(work_dir),
            env=env,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
        )

        try:
            await wait_for_server_healthy(
                self.url,
                timeout=timeout,
                process=self._process,
                read_log=self._read_log_file,
                local=True,
            )
        except Exception:
            self.stop()
            raise

    async def wait_for_graph_ready(
        self,
        graph_name: str = "agent",
        *,
        timeout: float = _HEALTH_TIMEOUT,
    ) -> None:
        import httpx

        if self._process is None:
            msg = "Server process is not running"
            raise RuntimeError(msg)

        graph_url = f"{self.url}/assistants/{quote(graph_name, safe='')}/graph"
        deadline = time.monotonic() + timeout

        async with httpx.AsyncClient() as client:
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    msg = f"Server process exited with code {self._process.returncode}"
                    output = self._read_log_file()
                    if output:
                        summary = _extract_startup_error_marker(output)
                        if summary:
                            msg += f": {summary}"
                        msg += f"\n{output[-_LOG_TAIL_CHARS:]}"
                    raise RuntimeError(msg)

                remaining = max(0.1, deadline - time.monotonic())
                try:
                    resp = await client.get(graph_url, timeout=remaining)
                except (httpx.TransportError, httpx.TimeoutException, OSError) as exc:
                    output = self._read_log_file()
                    summary = _extract_startup_error_marker(output)
                    if self._process.poll() is not None:
                        msg = (
                            f"Server process exited with code "
                            f"{self._process.returncode}"
                        )
                    else:
                        msg = (
                            f"Server graph '{graph_name}' did not initialize within "
                            f"{timeout}s"
                        )
                    if summary:
                        msg += f": {summary}"
                    if output:
                        msg += f"\n{output[-_LOG_TAIL_CHARS:]}"
                    raise RuntimeError(msg) from exc

                if resp.status_code == 200:
                    logger.info("Server graph %s is ready at %s", graph_name, self.url)
                    return

                output = self._read_log_file()
                msg = (
                    f"Server graph '{graph_name}' failed readiness check "
                    f"(status: {resp.status_code})"
                )
                summary = _extract_startup_error_marker(output)
                if summary:
                    msg += f": {summary}"
                if output:
                    msg += f"\n{output[-_LOG_TAIL_CHARS:]}"
                raise RuntimeError(msg)

        msg = f"Server graph '{graph_name}' did not initialize within {timeout}s"
        raise RuntimeError(msg)

    def _stop_process(self) -> None:
        if self._process is None:
            return

        if self._process.poll() is None:
            logger.info("Stopping langgraph dev server (pid=%d)", self._process.pid)
            try:
                self._process.send_signal(signal.SIGTERM)
                self._process.wait(timeout=_SHUTDOWN_TIMEOUT)
            except subprocess.TimeoutExpired:
                logger.warning("Server did not stop gracefully, killing")
                self._process.kill()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    logger.warning(
                        "Server process pid=%d did not exit after SIGKILL",
                        self._process.pid,
                    )
            except OSError:
                logger.warning("Error stopping server", exc_info=True)

        self._process = None

        if self._log_file is not None:
            log_path = Path(self._log_file.name)
            try:
                self._log_file.close()
            except OSError:
                logger.debug("Failed to close log file", exc_info=True)

            try:
                log_path.unlink()
            except OSError:
                logger.debug("Failed to clean up log file", exc_info=True)
            self._log_file = None

    def stop(self) -> None:
        self._stop_process()

        if self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
            except OSError:
                logger.debug("Failed to clean up temp dir", exc_info=True)
            self._temp_dir = None

        if self._owns_config_dir and self.config_dir is not None:
            import shutil

            try:
                shutil.rmtree(self.config_dir)
            except OSError:
                logger.debug(
                    "Failed to clean up config dir %s", self.config_dir, exc_info=True
                )
            self._owns_config_dir = False

    def update_env(self, **overrides: str) -> None:
        self._env_overrides.update(overrides)

    def persist_env(self, **overrides: str) -> None:
        invalid = [key for key in overrides if not key.startswith(SERVER_ENV_PREFIX)]
        if invalid:
            msg = (
                "persistent server env overrides must use the "
                f"{SERVER_ENV_PREFIX!r} prefix"
            )
            raise ValueError(msg)
        self._persistent_env_overrides.update(overrides)

    async def restart(self, *, timeout: float = _HEALTH_TIMEOUT) -> None:
        logger.info("Restarting langgraph dev server")
        await asyncio.to_thread(self._stop_process)

        with _scoped_env_overrides(self._env_overrides):
            await self.start(timeout=timeout)

        self._env_overrides.clear()

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        self.stop()
