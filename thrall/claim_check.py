"""Claim check — compare what a final reply claims with what tools actually did this turn.

Pure functions (no I/O except path existence checks) so the coordinator stays readable
and this ports cleanly. Two checks:
  1. Every file path named in the reply exists on disk, was written this turn, or was
     named by the user.
  2. Every past-tense action claim ("saved", "logged", "scheduled", "sent", "deleted") is
     backed by a successful tool call whose name fits that kind of action.
"""
from __future__ import annotations
import os
import re
from pathlib import Path
from constants.claims import (
    CLAIM_CATEGORIES, CLAIM_ANY_EVIDENCE_TOOLS, CLAIM_SUBJECTS, CLAIM_ADVERBS, CLAIM_PATH_EXT_MAX,
    CLAIM_COMPLETION_WORDS, CLAIM_NON_WORK_TOOLS, CLAIM_READ_ONLY_WORDS, CLAIM_ARTIFACT_WORDS,
)

_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
_ABS_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s`*\"'<>|?]+")
_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1," + str(CLAIM_PATH_EXT_MAX) + r"}$")
_SUBJECT = "|".join(re.escape(s).replace(r"\ ", r"\s+") for s in CLAIM_SUBJECTS)
_ADVERBS = "|".join(re.escape(a) for a in CLAIM_ADVERBS)


def _claim_regex(vocab: list[str]) -> re.Pattern:
    """A claim word reporting Thrall's own action: after I/I've/we (+adverbs), or starting a clause."""
    return re.compile(
        r"(?:\b(?:" + _SUBJECT + r")\s+(?:(?:" + _ADVERBS + r")\s+)*"   # "I've just saved"
        + r"|(?:^|[\n.!?:;—–]|\s-\s|\*\*)\s*(?:[-*•]\s*)?"              # "Saved to …" / "Done." at a clause start
        + r"(?:(?:" + _ADVERBS + r")\s+)*"                                # "All done", "Now fixed"
        + r"|\band\s+)"                                                  # "Noted and stored"
        + r"(" + "|".join(vocab) + r")\b",
        re.IGNORECASE | re.MULTILINE,
    )


_CLAIM_RE = _claim_regex(sorted({w for words, _ in CLAIM_CATEGORIES.values() for w in words}))
_COMPLETION_RE = _claim_regex(sorted(CLAIM_COMPLETION_WORDS))
_ALL_EVIDENCE_WORDS = frozenset().union(*(evidence for _, evidence in CLAIM_CATEGORIES.values()))
_FILENAME_RE = re.compile(r"\b[\w-]+\.[a-z][a-z0-9]{1,4}\b", re.IGNORECASE)  # splat-deck.pptx (not 3.14)
_WORDS_RE = re.compile(r"[A-Za-z]+")


def tool_words(name: str) -> set[str]:
    """'deckcraft__save_presentation' -> {'deckcraft', 'save', 'presentation'}."""
    return {w for w in name.lower().replace("__", "_").replace(".", "_").split("_") if w}


def normalise(path: str) -> str:
    return os.path.normcase(os.path.normpath(path.strip().strip(".,;:")))


def _looks_like_file_path(text: str) -> bool:
    t = text.strip().strip(".,;:")
    return ("\\" in t or "/" in t) and "://" not in t and bool(_EXT_RE.search(t))


def extract_paths(reply: str) -> list[str]:
    """File paths named in a reply: backticked spans that look like paths, plus bare absolute paths."""
    found: list[str] = []
    for span in _BACKTICK_RE.findall(reply):
        if _looks_like_file_path(span):
            found.append(span.strip().strip(".,;:"))
    without_code = _BACKTICK_RE.sub(" ", reply)
    for match in _ABS_PATH_RE.findall(without_code):
        if _looks_like_file_path(match):
            found.append(match.strip().strip(".,;:"))
    seen: set[str] = set()
    unique = []
    for p in found:
        key = normalise(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def missing_paths(reply: str, user_text: str, written: set[str], roots: list[Path]) -> list[str]:
    """Paths the reply names that don't exist, weren't written this turn, and weren't named by the user."""
    user_norm = normalise(user_text) if user_text else ""
    missing = []
    for path in extract_paths(reply):
        key = normalise(path)
        if user_norm and key in user_norm:
            continue  # the user named it — Thrall may be saying it doesn't exist
        # Either form may be the longer one: written "vtest\one.txt", reply "workspace\vtest\one.txt"
        if any(w == key or w.endswith(os.sep + key) or key.endswith(os.sep + w) for w in written):
            continue
        candidate = Path(path)
        if candidate.is_absolute():
            if candidate.exists():
                continue
        elif any((root / path).exists() for root in roots):
            continue
        missing.append(path)
    return missing


def claim_words(reply: str) -> list[str]:
    """Lower-cased claim words that report Thrall's own action (first person or clause-initial)."""
    return [m.group(1).lower() for m in _CLAIM_RE.finditer(_BACKTICK_RE.sub(" ", reply))]


def is_work_tool(name: str) -> bool:
    """True if a tool changes something (not just reading, searching, loading or planning)."""
    if name in CLAIM_NON_WORK_TOOLS:
        return False
    if name in CLAIM_ANY_EVIDENCE_TOOLS:
        return True
    words = tool_words(name)
    return bool(words & _ALL_EVIDENCE_WORDS) or not (words & CLAIM_READ_ONLY_WORDS)


def mentions_artifact(reply: str) -> bool:
    """Reply refers to something outside the chat: a file path/name or an artifact word."""
    if extract_paths(reply) or _FILENAME_RE.search(reply):
        return True
    return bool({w.lower() for w in _WORDS_RE.findall(reply)} & CLAIM_ARTIFACT_WORDS)


def unbacked_completion(reply: str, this_turn_tools: list[str]) -> list[str]:
    """'Done / completed / fixed / updated…' about a file or other artifact, with no tool that
    changed anything THIS turn. Pure text revisions ("Updated — here's the new prompt") pass."""
    hits = [m.group(1).lower() for m in _COMPLETION_RE.finditer(_BACKTICK_RE.sub(" ", reply))]
    if not hits or not mentions_artifact(reply) or any(is_work_tool(t) for t in this_turn_tools):
        return []
    return [f"reply says '{hits[0]}' but no tool that changes anything ran this turn"]


def unbacked_claims(reply: str, succeeded_tools: list[str]) -> list[str]:
    """Claim categories made in the reply with no successful tool call this turn to back them."""
    if any(t in CLAIM_ANY_EVIDENCE_TOOLS for t in succeeded_tools):
        return []
    evidence_words: set[str] = set()
    for t in succeeded_tools:
        evidence_words |= tool_words(t)
    claimed = set(claim_words(reply))
    problems = []
    for category, (words, evidence) in CLAIM_CATEGORIES.items():
        hits = sorted(claimed & set(words))
        if hits and not (evidence_words & evidence):
            problems.append(f"reply says '{hits[0]}' ({category}) but no tool that does that succeeded this turn")
    return problems
