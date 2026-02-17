<div align="center">

# Zap

**Python subprocess, but actually nice.**

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-orange?style=flat-square)

</div>

---

**Before:**
```python
result = subprocess.run(["git", "status"], capture_output=True, text=True, check=True)
print(result.stdout)
```

**After:**
```python
from zap import run
print(run("git status"))
```

---

## Install

```bash
pip install zap-sh
```

## Quick Start

```python
from zap import run

# Run a command
result = run("git status")
print(result.stdout)   # raw stdout
print(result.ok)       # True if exit code 0
print(result.code)     # exit code
print(result.lines)    # stdout as list of lines

# Just print it — str() returns stdout
print(run("ls -la"))
```

## Pipe Chaining

```python
# Pipe with strings — clean and simple
result = run("cat logs.txt") | "grep ERROR" | "wc -l"
print(result)  # number of error lines
```

## Error Handling

```python
from zap import run, ZapError

# Raises ZapError on non-zero exit (default)
try:
    run("git push origin fake-branch")
except ZapError as e:
    print(e.stderr)
    print(e.code)

# Disable with check=False
result = run("might-fail", check=False)
if not result.ok:
    print("Failed:", result.stderr)
```

## Options

```python
# Timeout (seconds)
run("sleep 100", timeout=5)  # raises TimeoutError

# Working directory
run("ls", cwd="/tmp")

# Environment variables (merged with os.environ)
run("echo $API_KEY", env={"API_KEY": "secret"})

# Feed stdin
run("cat", stdin="hello from stdin")

# Safe mode — pass a list instead of string
run(["echo", "no shell injection"])
```

## Async

```python
from zap import run_async

result = await run_async("git status")
print(result.ok)
```

Same API as `run()` — just `await` it.

## Result Object

| Property | Type | Description |
|----------|------|-------------|
| `.stdout` | `str` | Captured stdout |
| `.stderr` | `str` | Captured stderr |
| `.code` | `int` | Exit code |
| `.ok` | `bool` | `True` if exit code is 0 |
| `.lines` | `list[str]` | Stdout split into lines |
| `.json()` | `Any` | Parse stdout as JSON |
| `str(r)` | `str` | Returns stdout stripped |
| `bool(r)` | `bool` | Returns `.ok` |
| `r \| "cmd"` | `Result` | Pipe stdout to next command |

## How It Works

- **String command** → runs with `shell=True` (convenience for scripting)
- **List command** → runs with `shell=False` (safe, no shell injection)
- **check=True** by default → raises `ZapError` on non-zero exit
- **Zero dependencies** → pure Python stdlib
- **~200 lines** → read the whole source in 5 minutes

## License

MIT
