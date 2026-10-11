"""Skills — SKILL.md discovery, catalog, and skill_load."""
from __future__ import annotations
from uuid import uuid4
import pytest
from bootstrap import state
from schemas.tool import ToolCall
from services import skills
from thrall.tools.skills import load as skill_load
from constants.skills import SKILL_CATALOG_DESC_CHARS


def _write_skill(base, rel: str, name: str, description: str, body: str = "Do the thing.") -> None:
    folder = base / rel
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f'---\nname: {name}\ndescription: "{description}"\n---\n\n{body}\n', encoding="utf-8")


@pytest.fixture
def skill_dirs(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    _write_skill(first, "banana", "banana-pro-director", "Image prompt director")
    (first / "banana" / "references").mkdir()
    (first / "banana" / "references" / "stack.md").write_text("photoreal stack", encoding="utf-8")
    _write_skill(second, "synced/x1/seedance", "seedance-director", "Seedance video prompts " + "y" * 300)
    _write_skill(second, "dupe", "banana-pro-director", "older copy — should lose to the first dir")
    state.set_config({"skills": {"dirs": [str(first), str(second)]}})
    skills.refresh(skills.configured_dirs(state.get_config()))
    yield
    skills.refresh([])


def _load(name: str):
    return skill_load.execute(ToolCall(session_id=uuid4(), name=skill_load.NAME, args={"name": name}, caller="thrall"))


class TestDiscovery:
    def test_finds_nested_skills_first_dir_wins(self, skill_dirs):
        found = skills.all_skills(skills.configured_dirs(state.get_config()))
        assert set(found) == {"banana-pro-director", "seedance-director"}
        assert found["banana-pro-director"].description == "Image prompt director"

    def test_catalog_trims_long_descriptions(self, skill_dirs):
        cat = skills.catalog(skills.configured_dirs(state.get_config()), [])
        assert "- banana-pro-director: Image prompt director" in cat
        seedance_line = next(l for l in cat.splitlines() if "seedance-director" in l)
        assert len(seedance_line) <= len("- seedance-director: ") + SKILL_CATALOG_DESC_CHARS + 1

    def test_missing_dirs_are_ignored(self, tmp_path):
        assert skills.discover([tmp_path / "nope"]) == {}

    def test_folder_name_used_when_frontmatter_missing(self, tmp_path):
        (tmp_path / "plain").mkdir()
        (tmp_path / "plain" / "SKILL.md").write_text("just instructions", encoding="utf-8")
        assert "plain" in skills.discover([tmp_path])


class TestSkillLoad:
    def test_loads_body_and_lists_resources(self, skill_dirs):
        result = _load("banana-pro-director")
        assert result.error is None
        assert "Do the thing." in result.output
        assert "stack.md" in result.output

    def test_unknown_skill_lists_available(self, skill_dirs):
        result = _load("nope")
        assert result.error and "seedance-director" in result.error

    def test_ignored_skills_hidden_from_catalog_and_load(self, skill_dirs):
        state.set_config({"skills": {"dirs": state.get_config()["skills"]["dirs"], "ignore": ["seedance-director"]}})
        cat = skills.catalog(skills.configured_dirs(state.get_config()), skills.ignored_names(state.get_config()))
        assert "seedance-director" not in cat and "banana-pro-director" in cat
        result = _load("seedance-director")
        assert result.error and "seedance-director" not in result.error.split("Available:")[1]

    def test_picks_up_skill_added_after_first_scan(self, skill_dirs, tmp_path):
        _write_skill(tmp_path / "a", "fresh", "fresh-skill", "new")
        assert _load("fresh-skill").error is None
