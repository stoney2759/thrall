from __future__ import annotations
from schemas.task import CapabilityProfile

# Predefined capability profiles.
# Thrall passes one of these (or a custom one) when spawning a worker.
# A profile is the boundary — the task cannot call tools outside its list.

RESEARCHER = CapabilityProfile(
    name="researcher",
    allowed_tools=[
        "web.search",
        "web.fetch",
        "web.scrape",
        "web.browse",
        "filesystem.read",
        "filesystem.cat",
        "filesystem.grep",
        "filesystem.find",
        "memory.read",
        "memory.write",
    ],
)

WRITER = CapabilityProfile(
    name="writer",
    allowed_tools=[
        "filesystem.read",
        "filesystem.cat",
        "filesystem.write",
        "filesystem.edit",
        "filesystem.diff",
        "memory.read",
        "memory.write",
    ],
)

CODER = CapabilityProfile(
    name="coder",
    allowed_tools=[
        "filesystem.read",
        "filesystem.cat",
        "filesystem.write",
        "filesystem.edit",
        "filesystem.glob",
        "filesystem.grep",
        "filesystem.find",
        "filesystem.diff",
        "filesystem.tree",
        "code.execute",
        "memory.read",
    ],
)

ANALYST = CapabilityProfile(
    name="analyst",
    allowed_tools=[
        "filesystem.read",
        "filesystem.cat",
        "filesystem.glob",
        "filesystem.grep",
        "filesystem.find",
        "filesystem.stat",
        "web.fetch",
        "web.search",
        "memory.read",
        "memory.write",
    ],
)

SHELL = CapabilityProfile(
    name="shell",
    allowed_tools=["code.execute"],
    sandbox=True,
)

DEFAULT = CapabilityProfile(
    name="default",
    allowed_tools=[
        "filesystem.read",
        "filesystem.cat",
        "filesystem.glob",
        "filesystem.grep",
        "filesystem.find",
        "web.search",
        "web.fetch",
        "web.scrape",
        "memory.read",
    ],
)

_REGISTRY: dict[str, CapabilityProfile] = {
    "researcher": RESEARCHER,
    "writer": WRITER,
    "coder": CODER,
    "analyst": ANALYST,
    "shell": SHELL,
    "default": DEFAULT,
}


def get(name: str) -> CapabilityProfile:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown capability profile: '{name}'. Available: {list(_REGISTRY)}")
    return _REGISTRY[name]


def list_profiles() -> list[str]:
    return list(_REGISTRY.keys())
