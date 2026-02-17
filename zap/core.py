"""Zap — Python subprocess, but actually nice."""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, Generator, List, Optional, Union


class ZapError(Exception):
    """Raised when a command exits with a non-zero status."""

    def __init__(self, result: Result) -> None:
        self.result = result
        self.stdout = result.stdout
        self.stderr = result.stderr
        self.code = result.code
        msg = result.stderr.strip() or f"Command failed with exit code {result.code}"
        super().__init__(msg)


class Result:
    """The result of running a shell command."""

    __slots__ = ("stdout", "stderr", "code", "_command", "_kwargs")

    def __init__(
        self,
        stdout: str,
        stderr: str,
        code: int,
        command: Any = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.code = code
        self._command = command
        self._kwargs = kwargs or {}

    @property
    def ok(self) -> bool:
        """True if the command exited with code 0."""
        return self.code == 0

    @property
    def lines(self) -> List[str]:
        """Stdout split into lines, empty lines removed."""
        return [line for line in self.stdout.strip().splitlines() if line]

    def __str__(self) -> str:
        return self.stdout.strip()

    def __repr__(self) -> str:
        status = "ok" if self.ok else f"err:{self.code}"
        preview = self.stdout.strip()[:60]
        return f"Result({status}, {preview!r})"

    def __bool__(self) -> bool:
        return self.ok

    def __or__(self, other: Union["Result", str, list]) -> "Result":
        """Pipe: feed this result's stdout as stdin to the next command.

        Supports both Result and string/list commands:
            run("echo hi") | "wc -w"
            run("echo hi") | run("wc -w")
        """
        if isinstance(other, str) or isinstance(other, list):
            return run(other, stdin=self.stdout, check=False)
        if isinstance(other, Result):
            cmd = other._command
            kwargs = {**other._kwargs, "stdin": self.stdout, "check": False}
            return run(cmd, **kwargs)
        return NotImplemented

    def json(self) -> Any:
        """Parse stdout as JSON."""
        import json

        return json.loads(self.stdout)


def run(
    command: Union[str, List[str]],
    *,
    check: bool = True,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    stdin: Optional[str] = None,
    live: bool = False,
    retries: int = 0,
    delay: float = 1.0,
) -> Result:
    """Run a shell command and return a Result.

    Args:
        command: Command string or list of args.
        check: Raise ZapError on non-zero exit (default True).
        timeout: Timeout in seconds.
        cwd: Working directory.
        env: Extra environment variables (merged with os.environ).
        stdin: String to feed as stdin.
        live: Print output in real-time while still capturing it.
        retries: Number of times to retry on failure (default 0).
        delay: Seconds between retries (default 1.0).

    Returns:
        Result object with stdout, stderr, code, ok, lines.

    Raises:
        ZapError: If check=True and command exits non-zero (after retries).
        TimeoutError: If the command exceeds the timeout.
    """
    last_err: Optional[Exception] = None

    for attempt in range(1 + retries):
        if attempt > 0:
            time.sleep(delay)

        try:
            result = _run_once(
                command, check=False, timeout=timeout, cwd=cwd,
                env=env, stdin=stdin, live=live,
            )
        except TimeoutError:
            if attempt < retries:
                last_err = TimeoutError(
                    f"Command timed out after {timeout}s: {command}"
                )
                continue
            raise

        if result.ok or not retries:
            break

        if not result.ok and attempt < retries:
            last_err = ZapError(result)
            continue

    if check and not result.ok:
        raise ZapError(result)

    return result


def _run_once(
    command: Union[str, List[str]],
    *,
    check: bool = True,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    stdin: Optional[str] = None,
    live: bool = False,
) -> Result:
    """Execute a single command run (no retries)."""
    use_shell = isinstance(command, str)
    full_env = None
    if env is not None:
        full_env = {**os.environ, **env}

    if live:
        return _run_live(command, use_shell, timeout, cwd, full_env, stdin)

    try:
        proc = subprocess.run(
            command,
            shell=use_shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=full_env,
            input=stdin,
        )
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(
            f"Command timed out after {timeout}s: {command}"
        ) from e

    return Result(
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        code=proc.returncode,
        command=command,
        kwargs={"check": check, "timeout": timeout, "cwd": cwd, "env": env},
    )


def _run_live(
    command: Union[str, List[str]],
    use_shell: bool,
    timeout: Optional[float],
    cwd: Optional[str],
    full_env: Optional[Dict[str, str]],
    stdin: Optional[str],
) -> Result:
    """Run a command with live output streaming."""
    proc = subprocess.Popen(
        command,
        shell=use_shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE if stdin else None,
        cwd=cwd,
        env=full_env,
        text=True,
    )

    stdout_lines: List[str] = []
    stderr_lines: List[str] = []

    if stdin:
        proc.stdin.write(stdin)  # type: ignore[union-attr]
        proc.stdin.close()  # type: ignore[union-attr]

    import selectors

    sel = selectors.DefaultSelector()
    if proc.stdout:
        sel.register(proc.stdout, selectors.EVENT_READ)
    if proc.stderr:
        sel.register(proc.stderr, selectors.EVENT_READ)

    start = time.monotonic()
    open_streams = 2

    while open_streams > 0:
        if timeout and (time.monotonic() - start) > timeout:
            proc.kill()
            proc.wait()
            sel.close()
            raise TimeoutError(f"Command timed out after {timeout}s: {command}")

        events = sel.select(timeout=0.1)
        for key, _ in events:
            line = key.fileobj.readline()  # type: ignore[union-attr]
            if not line:
                sel.unregister(key.fileobj)
                open_streams -= 1
                continue
            if key.fileobj is proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                stdout_lines.append(line)
            else:
                sys.stderr.write(line)
                sys.stderr.flush()
                stderr_lines.append(line)

    proc.wait()
    sel.close()

    return Result(
        stdout="".join(stdout_lines),
        stderr="".join(stderr_lines),
        code=proc.returncode,
        command=command,
        kwargs={"timeout": timeout, "cwd": cwd},
    )


async def run_async(
    command: Union[str, List[str]],
    *,
    check: bool = True,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    stdin: Optional[str] = None,
) -> Result:
    """Async version of run(). Same API, uses asyncio subprocess.

    Args:
        command: Command string or list of args.
        check: Raise ZapError on non-zero exit (default True).
        timeout: Timeout in seconds.
        cwd: Working directory.
        env: Extra environment variables (merged with os.environ).
        stdin: String to feed as stdin.

    Returns:
        Result object with stdout, stderr, code, ok, lines.

    Raises:
        ZapError: If check=True and command exits non-zero.
        TimeoutError: If the command exceeds the timeout.
    """
    full_env = None
    if env is not None:
        full_env = {**os.environ, **env}

    stdin_bytes = stdin.encode() if stdin else None

    if isinstance(command, str):
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if stdin_bytes else None,
            cwd=cwd,
            env=full_env,
        )
    else:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if stdin_bytes else None,
            cwd=cwd,
            env=full_env,
        )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=stdin_bytes),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(
            f"Command timed out after {timeout}s: {command}"
        )

    result = Result(
        stdout=(stdout_bytes or b"").decode(),
        stderr=(stderr_bytes or b"").decode(),
        code=proc.returncode or 0,
        command=command,
        kwargs={"check": check, "timeout": timeout, "cwd": cwd, "env": env},
    )

    if check and not result.ok:
        raise ZapError(result)

    return result


def which(command: str) -> Optional[str]:
    """Check if a command exists on PATH. Returns its path or None."""
    return shutil.which(command)


@contextlib.contextmanager
def cd(path: str) -> Generator[None, None, None]:
    """Temporarily change working directory.

    Usage:
        with cd("/my/project"):
            run("git status")
            run("npm install")
    """
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)
