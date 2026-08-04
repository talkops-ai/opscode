"""Subagent branch memory storage for isolated learning persistence."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from dcoder.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BranchMemoryEntry:
    """An isolated memory entry generated during a subagent run."""

    run_id: str
    subagent_name: str
    content: str
    path: Path
    created_at: float


class BranchMemoryStore:
    """Manages branch memory files under .dcoder/memories/{subagent_name}-{run_id}.md"""

    def __init__(
        self,
        subagent_name: str,
        *,
        run_id: str | None = None,
        project_root: Path | None = None,
    ) -> None:
        self.subagent_name = subagent_name
        self.run_id = run_id or uuid.uuid4().hex[:8]
        root = project_root or settings.project_root or Path.cwd()
        self.memories_dir = root / ".dcoder" / "memories"
        self.branch_file = self.memories_dir / f"{self.subagent_name}-{self.run_id}.md"

    def write_observation(self, content: str) -> Path:
        """Append an observation to the subagent's branch memory file."""
        self.memories_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry_text = f"\n\n### [{timestamp}] Observation ({self.subagent_name})\n{content.strip()}"

        if not self.branch_file.exists():
            header = f"# Branch Memory: {self.subagent_name} (Run ID: {self.run_id})\nCreated at: {timestamp}"
            self.branch_file.write_text(header + entry_text, encoding="utf-8")
        else:
            with self.branch_file.open("a", encoding="utf-8") as f:
                f.write(entry_text)

        logger.debug("Wrote branch memory observation for %s to %s", self.subagent_name, self.branch_file)
        return self.branch_file

    def get_content(self) -> str:
        """Return the raw branch memory text if present."""
        if self.branch_file.is_file():
            try:
                return self.branch_file.read_text(encoding="utf-8")
            except OSError:
                return ""
        return ""


def list_branch_memories(*, project_root: Path | None = None) -> list[BranchMemoryEntry]:
    """List all pending branch memory files for merge evaluation."""
    root = project_root or settings.project_root or Path.cwd()
    memories_dir = root / ".dcoder" / "memories"
    if not memories_dir.is_dir():
        return []

    entries: list[BranchMemoryEntry] = []
    for file_path in sorted(memories_dir.glob("*.md")):
        stem = file_path.stem
        parts = stem.rsplit("-", 1)
        subagent_name = parts[0] if len(parts) > 1 else stem
        run_id = parts[1] if len(parts) > 1 else "unknown"
        try:
            content = file_path.read_text(encoding="utf-8")
            mtime = file_path.stat().st_mtime
            entries.append(
                BranchMemoryEntry(
                    run_id=run_id,
                    subagent_name=subagent_name,
                    content=content,
                    path=file_path,
                    created_at=mtime,
                )
            )
        except OSError:
            continue

    return entries
