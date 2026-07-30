"""CLI commands for managing dcoder skills."""

from pathlib import Path
from dcoder.skills.loader import list_skills
from dcoder.skills.trust import SkillTrustStore

def list_skills_command() -> list[dict[str, str]]:
    """List all discovered skills and their trust status."""
    discovered = list_skills()
    store = SkillTrustStore()
    
    results = []
    for skill in discovered:
        path = Path(skill["path"])
        trusted = store.is_trusted(skill["name"], path)
        results.append({
            "name": skill["name"],
            "description": skill.get("description", ""),
            "source": skill["source"],
            "path": str(path),
            "trusted": "Yes" if trusted else "No"
        })
    return results

def trust_skill_command(name: str, path_str: str) -> bool:
    """Trust a skill directory."""
    path = Path(path_str)
    if not path.exists():
        return False
    print(
        f"\033[93mWARNING: Trusting skill '{name}' at '{path_str}' allows the agent "
        "to run potentially untrusted scripts defined in this skill directory. "
        "Make sure you trust the source of this skill before proceeding.\033[0m"
    )
    store = SkillTrustStore()
    store.trust_skill(name, path)
    return True
