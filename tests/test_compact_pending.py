"""An abandoned /compact draft must not block auto-compact forever."""
from __future__ import annotations
from datetime import timedelta
from uuid import uuid4
from services.compaction import compactor
from constants.memory import COMPACT_PENDING_BLOCK_SECONDS


class TestPendingBlock:
    def test_fresh_draft_blocks_auto(self):
        sid = uuid4()
        compactor.store_pending(sid, "summary")
        assert compactor.pending_blocks_auto(sid)
        compactor.discard_pending(sid)
        assert not compactor.pending_blocks_auto(sid)

    def test_abandoned_draft_stops_blocking_but_stays_confirmable(self):
        sid = uuid4()
        compactor.store_pending(sid, "summary")
        compactor._pending_at[sid] -= timedelta(seconds=COMPACT_PENDING_BLOCK_SECONDS + 1)
        assert not compactor.pending_blocks_auto(sid)
        assert compactor.get_pending(sid) == "summary"
        compactor.discard_pending(sid)
