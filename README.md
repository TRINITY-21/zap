<div align="center">

# Zap

**Python subprocess, but actually nice.**

[![PyPI](https://img.shields.io/pypi/v/zap-sh?style=flat-square&color=blue)](https://pypi.org/project/zap-sh/)
[![Downloads](https://img.shields.io/pypi/dm/zap-sh?style=flat-square&color=green)](https://pypi.org/project/zap-sh/)
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

# Run a command — returns a Result object
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

## Live Output

See output in real-time while still capturing it. No more staring at a blank screen during `pip install` or `docker build`.

```python
# Stream output live to terminal — still captured in result
result = run("pip install flask", live=True)

# Works with long builds too
run("docker build -t myapp .", live=True)
run("make all", live=True)
```

## Retry

Automatically retry flaky commands — network calls, API requests, CI scripts.

```python
# Retry up to 3 times with 2s delay between attempts
result = run("curl -f https://api.example.com/health", retries=3, delay=2)

# Only retries on failure (non-zero exit) — succeeds immediately if ok
run("flaky-deploy-script.sh", retries=5, delay=5)
```

## Check If a Command Exists

```python
from zap import which

# Returns the path if found, None if not
if which("docker"):
    run("docker ps")
else:
    print("Docker not installed")

# Great for setup scripts
for cmd in ["git", "node", "python3"]:
    path = which(cmd)
    print(f"{cmd}: {path or 'NOT FOUND'}")
```

## Temporary Directory

```python
from zap import cd

# Change directory temporarily — auto-restores when done
with cd("/my/project"):
    run("git status")
    run("npm install")
    run("npm run build")
# Back to original directory here

# Safe even if something errors
with cd("/tmp"):
    run("some-command")  # if this fails, directory still restores
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

## `run()` Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `command` | `str \| list` | *required* | Command to run |
| `check` | `bool` | `True` | Raise `ZapError` on non-zero exit |
| `timeout` | `float` | `None` | Timeout in seconds |
| `cwd` | `str` | `None` | Working directory |
| `env` | `dict` | `None` | Extra env vars (merged with `os.environ`) |
| `stdin` | `str` | `None` | String to feed as stdin |
| `live` | `bool` | `False` | Stream output in real-time |
| `retries` | `int` | `0` | Number of retry attempts on failure |
| `delay` | `float` | `1.0` | Seconds between retries |

## How It Works

- **String command** → runs with `shell=True` (convenience for scripting)
- **List command** → runs with `shell=False` (safe, no shell injection)
- **check=True** by default → raises `ZapError` on non-zero exit
- **live=True** → uses `Popen` with `selectors` for real-time streaming
- **retries** → catches failures and retries with configurable delay
- **Zero dependencies** → pure Python stdlib
- **~300 lines** → read the whole source in 5 minutes

## Support

If Zap saves you time, consider buying me a coffee.

<a href="https://buymeacoffee.com/trinity_21" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="40"></a>

## License

MIT
