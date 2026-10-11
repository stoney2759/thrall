"""One rotating log file per running process — Windows can't rotate a file two processes share."""
from __future__ import annotations
import logging
from bootstrap.startup import log_file_name, log_level
from constants.launcher import LAUNCH_LOG_NAMES, MODE_ALL, MODE_WEB, MODE_TELEGRAM
from constants.log_files import LOG_FILE_MAIN, LOG_FILE_WEB, LOG_FILE_TELEGRAM


class TestLogLevel:
    def test_release_default_is_info(self):
        assert log_level({}) == logging.INFO

    def test_config_override_and_bad_value(self):
        assert log_level({"logging": {"level": "debug"}}) == logging.DEBUG
        assert log_level({"logging": {"level": "LOUD"}}) == logging.INFO


class TestLogFileName:
    def test_launch_modes_map_to_their_files(self):
        assert log_file_name(LAUNCH_LOG_NAMES[MODE_ALL]) == LOG_FILE_MAIN == "thrall.log"
        assert log_file_name(LAUNCH_LOG_NAMES[MODE_WEB]) == LOG_FILE_WEB
        assert log_file_name(LAUNCH_LOG_NAMES[MODE_TELEGRAM]) == LOG_FILE_TELEGRAM

    def test_every_mode_has_its_own_file(self):
        names = [log_file_name(n) for n in LAUNCH_LOG_NAMES.values()]
        assert len(set(names)) == len(names)

    def test_names_already_ending_in_log_are_kept(self):
        assert log_file_name("custom.log") == "custom.log"
