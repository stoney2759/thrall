from __future__ import annotations
import pytest
from schemas.message import Transport
from services.auth import auth
from bootstrap import state


class TestAuthIsAuthorised:
    def test_cli_always_authorised(self):
        assert auth.is_authorised("anyone", Transport.CLI) is True

    def test_scheduler_always_authorised(self):
        assert auth.is_authorised("anyone", Transport.SCHEDULER) is True

    def test_telegram_authorised_user(self):
        assert auth.is_authorised("authorized_user", Transport.TELEGRAM) is True

    def test_telegram_unknown_user_denied(self):
        assert auth.is_authorised("hacker_99", Transport.TELEGRAM) is False

    def test_telegram_numeric_user_id_matches(self):
        state.set_config({"transports": {"telegram": {"allowed_user_ids": [12345]}}})
        assert auth.is_authorised("12345", Transport.TELEGRAM) is True

    def test_telegram_no_allowed_list_denies_all(self):
        state.set_config({"transports": {"telegram": {}}})
        assert auth.is_authorised("anyone", Transport.TELEGRAM) is False


class TestAuthAddAllowedUser:
    def test_add_user_grants_access(self):
        auth.add_allowed_user("new_user", Transport.TELEGRAM)
        assert auth.is_authorised("new_user", Transport.TELEGRAM) is True

    def test_add_duplicate_user_not_duplicated(self):
        auth.add_allowed_user("authorized_user", Transport.TELEGRAM)
        auth.add_allowed_user("authorized_user", Transport.TELEGRAM)
        cfg = state.get_config()
        ids = cfg["transports"]["telegram"]["allowed_user_ids"]
        assert ids.count("authorized_user") == 1
