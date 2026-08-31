# Contributing to ULTRON

Thanks for wanting to help! ULTRON is an offline-first, two-device (laptop + phone)
AI assistant. Contributions that keep it **local, private, and safe** are most
welcome — new tools, new model providers, bug fixes, and docs.

## Getting set up

```bash
# Laptop brain
cd laptop/core
python3 -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install websockets
ollama pull qwen3.5:4b

# Orb HUD
cd ../../hud && npm install

# Phone (in Termux)
cd phone/agent && pip install websockets fastapi uvicorn vosk piper
```

See [RUNBOOK.md](RUNBOOK.md) for the full run commands.

## Running the tests

Tests live in `tests/` (unit + E2E). Run them from the repo root:

```bash
python3 -m unittest discover -s tests -v
```

This currently covers: agent perceive→act→verify, `am start` app launch,
provider cloud auto-reroute, model-choice parsing (local/cloud/custom),
HUD↔brain WebSocket round-trips, and the mesh pair + goal-relay handshake.
Please add or update a test for any behavior you change.

## Code style

- **Python**: PEP 8, 4-space indent, `from __future__ import annotations` at the
  top of every module, and type hints on public functions.
- **No secrets / no hardcoded paths**: anything environment-specific (model names,
  ports, ADB host, pair code, kill-switch path) must be a `Config` field with an
  `os.getenv(...)` default (see `laptop/core/config.py` and
  `phone/agent/config_phone.py`). Document the env var in `RUNBOOK.md`.
- **Log everything**: call `from audit import log` and record tool/agent actions
  so they land in the audit JSONL. Destructive shell commands must go through the
  existing `DESTRUCTIVE` guard in `tools.py` (they are blocked without a confirm
  callback).
- **Offline-first**: new features should work with a local Ollama model. Any
  network/cloud use must be opt-in (default off).
- **Next.js HUD**: follow the existing component layout under `hud/`; keep the orb
  a self-contained component.

## How to add a tool

Tools are plain functions registered in the tool dispatcher.

**Laptop** — `laptop/core/tools.py`:

```python
from audit import log

def my_tool(arg: str) -> dict:
    log("tool", {"tool": "my_tool", "arg": arg})
    # ... do the work ...
    return {"ok": True, "result": ...}
```

Then expose it in `dispatch()` (in the same file) so the agent can call it by name:

```python
def dispatch(tool_call: dict, confirm=None, **kw):
    name = tool_call.get("name")
    if name == "my_tool":
        return my_tool(tool_call.get("arguments", {}).get("arg", ""))
    # ... existing tools ...
```

**Phone** — mirror the same pattern in `phone/agent/tools_phone.py` and its
`dispatch()`.

Add a test in `tests/` that exercises the new tool (including the destructive-guard
path if it shells out).

## How to add a model provider

Model selection is centralized in two files:

1. **`laptop/core/providers.py`** — add a preset to the `PROVIDERS` dict:

   ```python
   PROVIDERS = {
       # ...
       "mycloud": {"base": "https://api.mycloud.com/v1",
                   "auth": "bearer", "path": "/chat/completions"},
   }
   ```

   All providers speak the OpenAI chat-completions shape, so most need only a
   `base` URL + `auth` style (`none` / `bearer` / `x-api-key`) + `path`.

2. **`laptop/core/models.py`** — register the preset in `CLOUD_PROVIDERS` so it is
   selectable:

   ```python
   CLOUD_PROVIDERS = {
       # ...
       "mycloud": "https://api.mycloud.com/v1",
   }
   ```

That's it — `choose("mycloud:some-model")` will now resolve the right provider. Add
a parsing test in `tests/test_core.py` (the `custom|url|key|model` form should keep
working).

## Reporting issues

- Use GitHub Issues for bugs/feature requests.
- For security-sensitive reports, follow **[SECURITY.md](SECURITY.md)** (do **not**
  open a public issue for vulnerabilities).

## License

By contributing, you agree your contributions are licensed under the MIT License
(see [LICENSE](LICENSE)).
