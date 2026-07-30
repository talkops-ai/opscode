from pathlib import Path
import json
import logging
from typing import TypedDict, Any

logger = logging.getLogger("dcoder")

class MCPServerConfig(TypedDict, total=False):
    command: str | None
    args: list[str] | None
    env: dict[str, str] | None
    url: str | None
    transport: str | None
    headers: dict[str, str] | None
    source: str | None

class MCPDiscovery:
    """Discovers and parses .mcp.json configs."""

    def __init__(self) -> None:
        pass

    def discover(self, project_root: Path | None = None) -> dict[str, MCPServerConfig]:
        """Merge configs. Precedence: project > user (~/.dcoder/mcp.json) > global (~/.agents/mcp.json)."""
        from dcoder.config.settings import settings
        
        effective_project_root = project_root or settings.project_root or Path.cwd()
        
        # 1. Global configs
        global_paths = [
            Path.home() / ".agents" / "mcp.json",
            Path.home() / ".agents" / ".mcp.json",
        ]
        # 2. User configs (~/.dcoder/mcp.json or ~/.dcoder/.mcp.json)
        user_paths = [
            settings.user_dcoder_dir / "mcp.json",
            settings.user_dcoder_dir / ".mcp.json",
        ]
        # 3. Project subdirectory configs ({project_root}/.dcoder/mcp.json or .mcp.json)
        project_subdir_paths = [
            effective_project_root / ".dcoder" / "mcp.json",
            effective_project_root / ".dcoder" / ".mcp.json",
        ]
        # 4. Project root configs ({project_root}/.mcp.json or mcp.json)
        project_root_paths = [
            effective_project_root / "mcp.json",
            effective_project_root / ".mcp.json",
        ]
        
        merged_servers: dict[str, MCPServerConfig] = {}
        
        candidates: list[tuple[Path, str]] = []
        for p in global_paths:
            candidates.append((p, "global"))
        for p in user_paths:
            candidates.append((p, "user"))
        for p in project_subdir_paths:
            candidates.append((p, "project"))
        for p in project_root_paths:
            candidates.append((p, "project"))

        # Load from lowest to highest precedence
        for path, source_name in candidates:
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    servers = data.get("mcpServers")
                    if isinstance(servers, dict):
                        for name, config in servers.items():
                            if isinstance(config, dict):
                                # Clean / cast the parsed config to matching type
                                clean_config: MCPServerConfig = {}
                                if "command" in config:
                                    clean_config["command"] = config["command"]
                                if "args" in config:
                                    clean_config["args"] = config["args"]
                                if "env" in config:
                                    clean_config["env"] = config["env"]
                                if "url" in config:
                                    clean_config["url"] = config["url"]
                                if "transport" in config:
                                    clean_config["transport"] = config["transport"]
                                if "headers" in config:
                                    clean_config["headers"] = config["headers"]
                                clean_config["source"] = source_name
                                
                                # Merge with overwrite
                                if name not in merged_servers:
                                    merged_servers[name] = clean_config
                                else:
                                    merged_servers[name] = {**merged_servers[name], **clean_config}
                except Exception as e:
                    logger.warning("Failed to parse MCP config at %s: %s", path, e)

        # 5. Discover plugin-declared MCP servers
        try:
            from dcoder.plugins.adapters.mcp import discover_plugin_mcp_configs

            plugin_layers = discover_plugin_mcp_configs(project_dir=effective_project_root)
            for layer in plugin_layers:
                servers = layer.get("mcpServers")
                if isinstance(servers, dict):
                    for name, config in servers.items():
                        if isinstance(config, dict):
                            clean_config: MCPServerConfig = {}
                            if "command" in config:
                                clean_config["command"] = config["command"]
                            if "args" in config:
                                clean_config["args"] = config["args"]
                            if "env" in config:
                                clean_config["env"] = config["env"]
                            if "url" in config:
                                clean_config["url"] = config["url"]
                            if "transport" in config:
                                clean_config["transport"] = config["transport"]
                            if "headers" in config:
                                clean_config["headers"] = config["headers"]
                            clean_config["source"] = "plugin"
                            merged_servers[name] = clean_config
        except Exception as e:
            logger.warning("Failed to discover plugin MCP configs: %s", e)

        return merged_servers

