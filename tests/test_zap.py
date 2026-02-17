"""Tests for zap."""

import asyncio
import pytest
from zap import run, run_async, Result, ZapError


# --- Basic ---

def test_simple_command():
    r = run("echo hello")
    assert r.stdout.strip() == "hello"
    assert r.ok is True
    assert r.code == 0


def test_str_returns_stdout():
    assert str(run("echo hello")) == "hello"


def test_bool_returns_ok():
    assert bool(run("echo ok")) is True
    assert bool(run("exit 1", check=False)) is False


def test_lines():
    r = run("printf 'a\\nb\\nc\\n'")
    assert r.lines == ["a", "b", "c"]


def test_empty_lines_filtered():
    r = run("printf 'a\\n\\nb\\n'")
    assert r.lines == ["a", "b"]


# --- Error handling ---

def test_raises_on_nonzero():
    with pytest.raises(ZapError) as exc_info:
        run("exit 1")
    assert exc_info.value.code == 1
    assert exc_info.value.result.code == 1


def test_check_false_no_raise():
    r = run("exit 42", check=False)
    assert r.ok is False
    assert r.code == 42


def test_stderr_captured():
    r = run("echo oops >&2 && exit 1", check=False)
    assert "oops" in r.stderr


def test_zap_error_message():
    try:
        run("echo bad >&2 && exit 1")
    except ZapError as e:
        assert "bad" in str(e)


# --- Pipes ---

def test_pipe():
    r = run("echo hello world") | "wc -w"
    assert str(r).strip() == "2"


def test_pipe_with_run():
    r = run("echo hello world") | run("wc -w")
    assert str(r).strip() == "2"


def test_multi_pipe():
    r = run("printf 'a\\nb\\nc\\n'") | "grep b" | "wc -l"
    assert str(r).strip() == "1"


# --- Options ---

def test_cwd():
    r = run("pwd", cwd="/tmp")
    assert "/tmp" in str(r)


def test_env():
    r = run("echo $ZAP_VAR", env={"ZAP_VAR": "works"})
    assert str(r) == "works"


def test_stdin():
    r = run("cat", stdin="hello from stdin")
    assert str(r) == "hello from stdin"


def test_timeout():
    with pytest.raises(TimeoutError):
        run("sleep 10", timeout=0.1)


def test_list_command():
    r = run(["echo", "hello"])
    assert str(r) == "hello"


# --- Result ---

def test_repr():
    r = run("echo hi")
    assert "ok" in repr(r)


def test_json():
    r = run('echo \'{"a": 1}\'')
    assert r.json() == {"a": 1}


# --- Async ---

def test_async_basic():
    async def _test():
        r = await run_async("echo async works")
        assert str(r) == "async works"
        assert r.ok is True
    asyncio.run(_test())


def test_async_error():
    async def _test():
        with pytest.raises(ZapError):
            await run_async("exit 1")
    asyncio.run(_test())


def test_async_timeout():
    async def _test():
        with pytest.raises(TimeoutError):
            await run_async("sleep 10", timeout=0.1)
    asyncio.run(_test())


def test_async_stdin():
    async def _test():
        r = await run_async("cat", stdin="async stdin")
        assert str(r) == "async stdin"
    asyncio.run(_test())
