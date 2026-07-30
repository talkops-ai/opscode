import pytest
from pathlib import Path
from dcoder.skills.registry import SkillRegistry
from dcoder.skills.trust import SkillTrustStore
from dcoder.skills.loader import load_skill_content

def test_skills_registry_singleton():
    reg1 = SkillRegistry.get_instance()
    reg2 = SkillRegistry.get_instance()
    assert reg1 is reg2

def test_skills_trust_store(tmp_path):
    trust_file = tmp_path / "skill_trust.json"
    store = SkillTrustStore(trust_file_path=trust_file)
    
    test_path = tmp_path / "custom_skill"
    test_path.mkdir()
    
    assert not store.is_trusted("custom_skill", test_path)
    
    store.trust_skill("custom_skill", test_path)
    assert store.is_trusted("custom_skill", test_path)
    
    # Check that another instance reads the same trust configuration
    store2 = SkillTrustStore(trust_file_path=trust_file)
    assert store2.is_trusted("custom_skill", test_path)

def test_skills_auto_trust():
    store = SkillTrustStore()
    built_in = Path(__file__).parent.parent.parent / "src" / "dcoder" / "built_in_skills"
    assert store.is_trusted("dummy", built_in)

def test_load_skill_content_traversal_prevention(tmp_path):
    root_dir = tmp_path / "skills"
    root_dir.mkdir()
    
    safe_file = root_dir / "SKILL.md"
    safe_file.write_text("Safe content", encoding="utf-8")
    
    unsafe_file = tmp_path / "secret.txt"
    unsafe_file.write_text("Sensitive data", encoding="utf-8")
    
    # Loading safe file under allowed root succeeds
    content = load_skill_content(str(safe_file), allowed_roots=[root_dir])
    assert content == "Safe content"
    
    # Loading unsafe file outside allowed root raises PermissionError (SSRF prevention)
    with pytest.raises(PermissionError):
        load_skill_content(str(unsafe_file), allowed_roots=[root_dir])
