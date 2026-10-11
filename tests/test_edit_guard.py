"""Edit guard — filesystem_edit only works on files read this session and unchanged since."""
from __future__ import annotations
import os
from uuid import uuid4
from schemas.tool import ToolCall
from thrall.tools.filesystem import edit, read, write


def _call(tool, sid, **args) -> ToolCall:
    return ToolCall(session_id=sid, name=tool.NAME, args=args, caller="thrall")


def _edit(sid, path):
    return edit.execute(_call(edit, sid, path=str(path), old_string="red", new_string="blue"))


class TestEditGuard:
    def test_unread_file_is_refused(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("red")
        result = _edit(uuid4(), f)
        assert result.error and "read" in result.error
        assert f.read_text() == "red"

    def test_read_then_edit_works(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("red")
        sid = uuid4()
        read.execute(_call(read, sid, path=str(f)))
        assert _edit(sid, f).error is None
        assert f.read_text() == "blue"

    def test_changed_on_disk_since_read_is_refused(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("red")
        sid = uuid4()
        read.execute(_call(read, sid, path=str(f)))
        f.write_text("red red")
        st = f.stat()
        os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))  # make the change visible on coarse clocks
        result = _edit(sid, f)
        assert result.error and "changed on disk" in result.error

    def test_own_write_counts_as_read_and_repeat_edits_allowed(self, tmp_path):
        f = tmp_path / "b.txt"
        sid = uuid4()
        write.execute(_call(write, sid, path=str(f), content="red green red"))
        assert edit.execute(_call(edit, sid, path=str(f), old_string="green", new_string="blue")).error is None
        assert edit.execute(_call(edit, sid, path=str(f), old_string="blue", new_string="gold")).error is None

    def test_reads_are_per_session(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("red")
        read.execute(_call(read, uuid4(), path=str(f)))
        assert _edit(uuid4(), f).error
