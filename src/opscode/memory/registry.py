"""Discovery and mapping of persistent user and project memories."""

import threading
from pathlib import Path
from opscode.config.settings import settings

class MemoryRegistry:
    """Discovers and manages memory files across user and project scopes."""
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "MemoryRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_memory_paths_for_scope(self, scope: str) -> list[Path]:
        """Resolve physical paths for a given scope ('user', 'project', 'auto')."""
        paths = []
        
        # User scope
        if scope in ("user", "auto"):
            # ~/.opscode/opscode/AGENTS.md
            user_md = settings.user_opscode_dir / "opscode" / "AGENTS.md"
            paths.append(user_md)
            # ~/.agents/AGENTS.md
            paths.append(Path.home() / ".agents" / "AGENTS.md")
            
        # Project scope
        if scope in ("project", "auto"):
            if settings.project_root:
                # {project_root}/.opscode/AGENTS.md
                paths.append(settings.project_root / ".opscode" / "AGENTS.md")
                # {project_root}/.agents/AGENTS.md
                paths.append(settings.project_root / ".agents" / "AGENTS.md")
                # {project_root}/AGENTS.md
                paths.append(settings.project_root / "AGENTS.md")
                
        # Resolve physical paths to absolute paths
        resolved_paths = []
        for p in paths:
            try:
                abs_p = p.expanduser().resolve()
                if abs_p not in resolved_paths:
                    resolved_paths.append(abs_p)
            except Exception:
                # Ignore resolve errors for non-existent system paths
                pass
                
        # Add auto-memories from memories directory
        if scope == "auto":
            memories_dir = settings.user_opscode_dir / "opscode" / "memories"
            if memories_dir.is_dir():
                for entry in memories_dir.glob("*.md"):
                    try:
                        resolved_entry = entry.resolve()
                        if resolved_entry not in resolved_paths:
                            resolved_paths.append(resolved_entry)
                    except Exception:
                        pass
                        
        return resolved_paths

    def resolve_virtual_path(self, virtual_path: str) -> Path:
        """Map a virtual path to a physical path."""
        normalized = virtual_path.replace("\\", "/")
        if normalized == "/memories/user/AGENTS.md":
            return settings.user_opscode_dir / "opscode" / "AGENTS.md"
        if normalized == "/memories/project/AGENTS.md" and settings.project_root:
            for p in [
                settings.project_root / ".opscode" / "AGENTS.md",
                settings.project_root / ".agents" / "AGENTS.md",
                settings.project_root / "AGENTS.md",
            ]:
                if p.is_file():
                    return p
            return settings.project_root / ".opscode" / "AGENTS.md"
            
        return Path(virtual_path).expanduser().resolve()

    def get_all_memory_sources(self, agent_id: str) -> list[str]:
        """Return a list of all physical AGENTS.md paths to feed to MemoryMiddleware."""
        paths = self.get_memory_paths_for_scope("auto")
        return [str(p) for p in paths]
