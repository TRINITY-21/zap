"""Zap — Python subprocess, but actually nice."""

from __future__ import annotations

import asyncio
import os
import subprocess
from typing import Any, Dict, List, Optional, Union


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
) -> Result:
    """Run a shell command and return a Result.

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
    use_shell = isinstance(command, str)
    full_env = None
    if env is not None:
        full_env = {**os.environ, **env}

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

    result = Result(
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        code=proc.returncode,
        command=command,
        kwargs={"check": check, "timeout": timeout, "cwd": cwd, "env": env},
    )

    if check and not result.ok:
        raise ZapError(result)

    return result


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
