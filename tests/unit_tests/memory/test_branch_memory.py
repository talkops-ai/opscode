import pytest
from pathlib import Path
from dcoder.memory.branch import BranchMemoryStore, list_branch_memories


def test_branch_memory_store(tmp_path):
    store = BranchMemoryStore(
        subagent_name="k8s-auditor",
        run_id="run123",
        project_root=tmp_path,
    )

    path = store.write_observation("Pods should have liveness probes configured.")
    assert path.exists()
    assert "k8s-auditor-run123.md" in str(path)

    content = store.get_content()
    assert "Branch Memory: k8s-auditor" in content
    assert "liveness probes" in content

    memories = list_branch_memories(project_root=tmp_path)
    assert len(memories) == 1
    assert memories[0].subagent_name == "k8s-auditor"
    assert memories[0].run_id == "run123"
