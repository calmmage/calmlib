from calmlib.telegram.telethon_client import (
    _describe_sent_code,
    _sent_code_prompt,
    _sent_code_wait_timeout,
    _should_remove_session_file_after_auth_failure,
)


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
