"""Zap — Python subprocess, but actually nice."""

from zap.core import Result, ZapError, run, run_async

__all__ = ["run", "run_async", "Result", "ZapError"]
__version__ = "0.1.0"
