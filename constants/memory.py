MAX_EPISODES = 20            # max episodic memories injected into context per turn
MAX_FACTS = 10               # max semantic facts injected into context per turn
MAX_EPISODE_LENGTH = 8_000   # chars — episodes longer than this are rejected by memory_gate
MIN_EPISODE_LENGTH = 10      # chars — episodes shorter than this are rejected by memory_gate
MIN_FACT_CONFIDENCE = 0.5    # facts below this confidence are rejected by memory_gate
EPISODE_QUERY_LENGTH = 200   # chars — user message truncated to this for episode/fact search
MAX_EPISODE_DISPLAY_CHARS = 0  # chars — 0 = no truncation (full content injected); set in config to enable

# Always-loaded user memory — facts the user gave Thrall go into context EVERY turn, not only on a
# keyword match. A fact counts as the user's when its source mentions "user" (sources are free text).
USER_FACT_SOURCE_MARKER = "user"
USER_FACTS_SCAN = 500          # most recent facts scanned for user-given ones
USER_FACTS_MAX = 40            # newest user facts injected per turn
USER_FACTS_MAX_CHARS = 6_000   # block cap; oldest dropped first beyond this

# A manual /compact draft awaiting approval blocks auto-compact for at most this long
COMPACT_PENDING_BLOCK_SECONDS = 1_800
