"""Skill discovery — SKILL.md folders under the dirs listed in config [skills] dirs."""
from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from pathlib import Path
import yaml
from constants.skills import SKILL_FILENAME, SKILL_SEARCH_DEPTH, SKILL_CATALOG_DESC_CHARS

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    path: Path  # the SKILL.md file


_cache: dict[str, SkillInfo] = {}
_loaded = False


def resolve_dirs(configured: list[str]) -> list[Path]:
    """Config entries → absolute dirs. Relative entries are relative to the Thrall install root."""
    dirs: list[Path] = []
    for entry in configured:
        p = Path(os.path.expanduser(str(entry)))
        dirs.append(p if p.is_absolute() else _ROOT / p)
    return dirs


def parse_skill(path: Path) -> SkillInfo | None:
    """Read a SKILL.md's frontmatter. Returns None if it has no usable name."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Skill unreadable %s: %s", path, e)
        return None
    meta: dict = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                meta = yaml.safe_load(text[3:end]) or {}
            except yaml.YAMLError as e:
                logger.warning("Skill frontmatter invalid %s: %s", path, e)
    name = str(meta.get("name") or path.parent.name).strip()
    if not name:
        return None
    description = " ".join(str(meta.get("description") or "").split())
    return SkillInfo(name=name, description=description, path=path)


def discover(dirs: list[Path]) -> dict[str, SkillInfo]:
    """Every SKILL.md up to SKILL_SEARCH_DEPTH levels below each dir. First dir wins on duplicate names."""
    found: dict[str, SkillInfo] = {}
    for base in dirs:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob(SKILL_FILENAME)):
            if len(path.relative_to(base).parts) - 1 > SKILL_SEARCH_DEPTH:
                continue
            info = parse_skill(path)
            if info and info.name not in found:
                found[info.name] = info
    return found


def refresh(configured: list[str]) -> dict[str, SkillInfo]:
    global _loaded
    _cache.clear()
    _cache.update(discover(resolve_dirs(configured)))
    _loaded = True
    logger.info("Skills discovered: %d", len(_cache))
    return dict(_cache)


def all_skills(configured: list[str]) -> dict[str, SkillInfo]:
    """Cached skill list; discovered on first use."""
    if not _loaded:
        refresh(configured)
    return dict(_cache)


def catalog(configured: list[str], ignore: list[str]) -> str:
    """One line per skill (name — trimmed description) for Thrall's context, minus ignored names."""
    lines = []
    for name, info in sorted(all_skills(configured).items()):
        if name in ignore:
            continue
        desc = info.description
        if len(desc) > SKILL_CATALOG_DESC_CHARS:
            desc = desc[:SKILL_CATALOG_DESC_CHARS].rstrip() + "…"
        lines.append(f"- {name}: {desc}" if desc else f"- {name}")
    return "\n".join(lines)


def configured_dirs(config: dict) -> list[str]:
    return list(config.get("skills", {}).get("dirs", []))


def ignored_names(config: dict) -> list[str]:
    """Skills hidden from Thrall (e.g. ones written for another assistant's tools)."""
    return list(config.get("skills", {}).get("ignore", []))
