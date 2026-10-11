from __future__ import annotations

# Skills — folders holding a SKILL.md (frontmatter name + description, then instructions).
# A one-line catalog is injected each turn; the full instructions load on demand via skill_load.
SKILL_FILENAME = "SKILL.md"
SKILL_SEARCH_DEPTH = 4             # folder levels searched below each configured skills dir
SKILL_CATALOG_DESC_CHARS = 160     # description length shown per skill in the context catalog
SKILL_MAX_CHARS = 60_000           # skill_load output cap — skills are long by design, not cut at the normal tool cap
SKILL_RESOURCE_LIST_MAX = 20       # extra files in a skill folder listed after its instructions
