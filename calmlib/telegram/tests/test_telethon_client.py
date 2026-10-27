from calmlib.telegram.telethon_client import (
    _describe_sent_code,
    _sent_code_prompt,
    _sent_code_wait_timeout,
    _should_remove_session_file_after_auth_failure,
)


def test_session_is_exclusive_until_disconnect_and_on_reconnect(tmp_path, monkeypatch):
    import asyncio
    from calmlib.telegram import telethon_client as tc

    async def scenario():
        connections = []

        async def connect(client):
            connections.append(client)

        async def authorized(client):
            return True

        async def disconnect(client):
            client.session.close()

        monkeypatch.setattr(tc.TelegramClient, "connect", connect)
        monkeypatch.setattr(tc.TelegramClient, "is_user_authorized", authorized)
        monkeypatch.setattr(tc.TelegramClient, "_disconnect_coro", disconnect)
        kwargs = dict(api_id=123, api_hash="test", phone="test", session_name="test",
                      session_dir=tmp_path, lock_timeout_sec=1, lock_poll_sec=.01)
        first = await tc.authenticate_telethon_client(**kwargs)
        second_task = asyncio.create_task(tc.authenticate_telethon_client(**kwargs))
        try:
            await asyncio.sleep(.05)
            assert not second_task.done(), "second client entered while the first still owned the session"
            assert len(connections) == 1
            await first.disconnect()
            second = await asyncio.wait_for(second_task, .5)
            reconnect = asyncio.create_task(first.connect())
            await asyncio.sleep(.05)
            assert not reconnect.done(), "cached reconnect bypassed the session lock"
            await second.disconnect()
            await asyncio.wait_for(reconnect, .5)
            await first.disconnect()
        finally:
            second_task.cancel()
            await asyncio.gather(second_task, return_exceptions=True)
            await first.disconnect()

    asyncio.run(scenario())


def test_failed_connect_disconnects_before_retry(tmp_path, monkeypatch):
    import asyncio
    import sqlite3
    import pytest
    from calmlib.telegram import telethon_client as tc

    async def scenario():
        closed = []

        async def connect(client):
            raise sqlite3.OperationalError("database is locked")

        async def disconnect(client):
            closed.append(client)
            client.session.close()

        monkeypatch.setattr(tc.TelegramClient, "connect", connect)
        monkeypatch.setattr(tc.TelegramClient, "_disconnect_coro", disconnect)
        monkeypatch.setattr(tc, "DATABASE_LOCK_RETRY_ATTEMPTS", 1)
        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
            await tc.authenticate_telethon_client(api_id=123, api_hash="test", phone="test",
                                                session_name="test", session_dir=tmp_path)
        assert closed, "failed connection left its client and SQLite session open"

    asyncio.run(scenario())


def test_cancelled_waiter_preserves_the_current_owner(tmp_path):
    import asyncio
    import pytest
    from calmlib.telegram.telethon_client import _SessionFileLock

    async def scenario():
        path = tmp_path / "test.session.lock"
        owner = _SessionFileLock(path, 1, .01)
        waiter = _SessionFileLock(path, 1, .01)
        await owner.acquire()
        task = asyncio.create_task(waiter.acquire())
        await asyncio.sleep(.03)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        probe = _SessionFileLock(path, .03, .01)
        with pytest.raises(TimeoutError):
            await probe.acquire()
        owner.release()
        await probe.acquire()
        probe.release()

    asyncio.run(scenario())


def test_zero_idle_timeout_closes_before_context_exit(monkeypatch):
    import asyncio
    from calmlib.telegram import telethon_client as tc

    async def scenario():
        class Client:
            closed = False
            def is_connected(self):
                return not self.closed
            async def disconnect(self):
                self.closed = True

        client = Client()
        async def get_client(account):
            return client
        monkeypatch.setattr(tc, "get_telethon_client", get_client)
        manager = tc.TelethonClientLeaseManager("test", idle_timeout=0)
        await manager.acquire()
        await manager.release()
        assert client.closed
        assert manager._idle_task is None

    asyncio.run(scenario())


def test_auth_failure_preserves_preexisting_session_file() -> None:
    assert not _should_remove_session_file_after_auth_failure(
        ValueError("Verification code is required"),
        session_file_existed_before_auth=True,
    )


def test_auth_failure_removes_new_failed_session_file() -> None:
    assert _should_remove_session_file_after_auth_failure(
        ValueError("Verification code is required"),
        session_file_existed_before_auth=False,
    )


def test_lock_failure_preserves_new_session_file() -> None:
    assert not _should_remove_session_file_after_auth_failure(
        TimeoutError("Timed out waiting for session lock"),
        session_file_existed_before_auth=False,
    )


def test_describe_sent_code_omits_sensitive_hash() -> None:
    class SentCode:
        type = object()
        next_type = None
        timeout = 120
        phone_code_hash = "secret-hash"

    description = _describe_sent_code(SentCode())

    assert description == "type=object, next_type=NoneType, timeout=120"
    assert "secret-hash" not in description


def test_sent_code_prompt_explains_delivery_channel() -> None:
    class SentCodeTypeApp:
        pass

    class CodeTypeSms:
        pass

    class SentCode:
        type = SentCodeTypeApp()
        next_type = CodeTypeSms()
        timeout = 120

    assert (
        _sent_code_prompt(SentCode())
        == "Code (delivery: Telegram app, next: SMS, timeout: 120s)"
    )


def test_sent_code_wait_timeout_uses_default_without_next_delivery() -> None:
    class SentCode:
        next_type = None
        timeout = 120

    assert _sent_code_wait_timeout(SentCode()) == 1200.0


def test_sent_code_wait_timeout_waits_for_next_delivery_window() -> None:
    class CodeTypeSms:
        pass

    class SentCode:
        next_type = CodeTypeSms()
        timeout = 120

    assert _sent_code_wait_timeout(SentCode()) == 300.0
