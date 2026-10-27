"""Attach the local Agent control service to a running application window."""
from __future__ import annotations

from pathlib import Path


def start_agent_control(window, app, discovery_path: Path | None = None):
    """Start after the singleton check; leave the desktop app usable on failure."""
    try:
        from src.agent_api import AgentAPI
        from src.agent_transport import AgentServer
        from src.paths import app_root

        path = discovery_path if discovery_path is not None else app_root() / "data" / "agent-control.json"
        api = AgentAPI(window)
        server = AgentServer(api.dispatch, path, parent=window)
        server.start()
        app.aboutToQuit.connect(server.close)
        window._agent_control_error = ""
        return server
    except Exception as exc:
        window._agent_control_error = f"Agent 接口未启动：{exc}"
        window._refresh_status()
        return None
