MAX_EPISODES = 20       # max episodic memories injected into context per turn
MAX_FACTS = 10          # max semantic facts injected into context per turn
MAX_EPISODE_LENGTH = 8_000   # chars — episodes longer than this are rejected by memory_gate
MIN_EPISODE_LENGTH = 10      # chars — episodes shorter than this are rejected by memory_gate
MIN_FACT_CONFIDENCE = 0.5    # facts below this confidence are rejected by memory_gate
