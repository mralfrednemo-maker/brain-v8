#!/usr/bin/env python3
"""ein-parallel.py — Run ChatGPT, Claude, and Gemini in true parallel.

Usage:
    python ein-parallel.py --action ask --prompt "Hello" --fresh --upload file.md
    python ein-parallel.py --action new_chat
    python ein-parallel.py --action screenshot --screenshot-dir ./shots
    python ein-parallel.py --action status
    python ein-parallel.py --action ask --prompt "Hi" --only chatgpt,gemini

Outputs JSON to stdout. Logs to stderr.
"""
import argparse
import asyncio
import base64
import json
import logging
import re
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path

log = logging.getLogger("ein")

# ---------------------------------------------------------------------------
# Abstract driver
# ---------------------------------------------------------------------------

class LLMDriver(ABC):
    name: str

    @abstractmethod
    async def connect(self) -> None: ...
    @abstractmethod
    async def close(self) -> None: ...
    @abstractmethod
    async def new_chat(self) -> dict: ...
    @abstractmethod
    async def upload_file(self, path: str) -> dict: ...
    @abstractmethod
    async def set_model(self, model: str) -> dict: ...
    @abstractmethod
    async def _ask(self, prompt: str, timeout: int = 120) -> dict: ...
    @abstractmethod
    async def screenshot(self, out_dir: str) -> dict: ...
    @abstractmethod
    async def status(self) -> dict: ...

    async def restart_browser(self) -> dict:
        """Restart the underlying browser. No-op by default; override in bridge drivers."""
        return {"success": True, "info": "restart_browser not supported for this driver"}

    def _ts(self, label: str):
        log.info("[%s] %s at %s", self.name, label, time.strftime("%H:%M:%S"))

    async def execute(self, action: str, params: dict) -> dict:
        t0 = time.time()
        try:
            if action == "new_chat":
                result = await self.new_chat()
            elif action == "upload_file":
                result = await self.upload_file(params["path"])
            elif action == "set_model":
                result = await self.set_model(params["model"])
            elif action == "ask":
                # Always: new_chat + optional model + optional upload + send
                result = {}
                self._ts("new_chat START")
                r = await self.new_chat()
                self._ts("new_chat DONE")
                result["new_chat"] = r
                if not r.get("success", True):
                    result.update({"success": False, "error": "new_chat failed"})
                    raise RuntimeError("new_chat failed")

                # Set model after new_chat (Gemini resets on new chat)
                if params.get("model"):
                    self._ts("set_model START")
                    r = await self.set_model(params["model"])
                    self._ts("set_model DONE")
                    if not r.get("success", True):
                        log.warning("[%s] set_model '%s' failed, continuing anyway", self.name, params["model"])

                if params.get("path"):
                    self._ts("upload START")
                    r = await self.upload_file(params["path"])
                    self._ts("upload DONE")
                    result["upload"] = r
                    if not r.get("success", True):
                        result.update({"success": False, "error": "upload failed"})
                        raise RuntimeError("upload failed")

                self._ts("ask START")
                r = await self._ask(params["prompt"], params.get("timeout", 120))
                self._ts("ask DONE")
                result.update(r)
            elif action == "ask_continue":
                # Send without new_chat (continue existing thread)
                result = {}
                if params.get("path"):
                    self._ts("upload START")
                    r = await self.upload_file(params["path"])
                    self._ts("upload DONE")
                    result["upload"] = r
                    if not r.get("success", True):
                        result.update({"success": False, "error": "upload failed"})
                        raise RuntimeError("upload failed")
                self._ts("ask START")
                r = await self._ask(params["prompt"], params.get("timeout", 120))
                self._ts("ask DONE")
                result.update(r)
            elif action == "restart_browser":
                result = await self.restart_browser()
            elif action == "screenshot":
                result = await self.screenshot(params.get("screenshot_dir", "."))
            elif action == "status":
                result = await self.status()
            else:
                result = {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            log.exception("Error in %s.%s", self.name, action)
            result = {"success": False, "error": str(e)}
        result["llm"] = self.name
        result["elapsed_seconds"] = round(time.time() - t0, 1)
        return result


# ---------------------------------------------------------------------------
# WebSocket Bridge Driver — shared base for ChatGPT and Claude
# ---------------------------------------------------------------------------

class WSBridgeDriver(LLMDriver):
    """Base driver that talks to a WebSocket bridge server.

    Subclasses just set name, BRIDGE_URL, and override response cleanup.
    Same protocol as GeminiDriver — the bridges all speak the same language.
    """
    BRIDGE_URL: str = ""
    MIME_MAP = {
        ".txt": "text/plain", ".md": "text/markdown", ".py": "text/x-python",
        ".js": "text/javascript", ".json": "application/json", ".csv": "text/csv",
        ".html": "text/html", ".xml": "text/xml", ".yaml": "text/yaml",
        ".yml": "text/yaml", ".pdf": "application/pdf", ".png": "image/png",
    }

    def __init__(self):
        self._ws = None
        self._pending = {}
        self._reader_task = None

    async def connect(self):
        import websockets
        # Retry connection — bridge may not be ready yet
        for attempt in range(10):
            try:
                self._ws = await websockets.connect(self.BRIDGE_URL)
                self._reader_task = asyncio.create_task(self._reader())
                return
            except (ConnectionRefusedError, OSError) as e:
                if attempt < 9:
                    log.info("[%s] Bridge not ready, retrying in 2s... (%s)", self.name, e)
                    await asyncio.sleep(2)
                else:
                    raise RuntimeError(
                        f"{self.name} bridge not reachable at {self.BRIDGE_URL} — "
                        f"is the MCP server running?"
                    )

    async def _reader(self):
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                msg_id = msg.get("id")
                if msg_id and msg_id in self._pending:
                    self._pending[msg_id].set_result(msg)
                    del self._pending[msg_id]
        except Exception:
            pass

    async def _send(self, action: str, params: dict = None, timeout: float = 120) -> dict:
        import uuid
        msg_id = str(uuid.uuid4())
        cmd = {"id": msg_id, "action": action, "params": params or {}}
        future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = future
        try:
            await self._ws.send(json.dumps(cmd))
        except Exception:
            del self._pending[msg_id]
            raise
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            return {"success": False, "error": "Timeout"}

    async def close(self):
        if self._reader_task:
            self._reader_task.cancel()
            try: await self._reader_task
            except: pass
        if self._ws:
            await self._ws.close()
        self._ws = self._reader_task = None

    async def new_chat(self):
        resp = await self._send("new_chat")
        return {"success": resp.get("success", False)}

    async def upload_file(self, path: str):
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}
        content_b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        mime = self.MIME_MAP.get(p.suffix.lower(), "application/octet-stream")
        resp = await self._send("upload_file", {
            "filename": p.name, "content_base64": content_b64, "mime_type": mime,
        })
        if resp.get("success"):
            return {"success": True, "filename": p.name}
        return {"success": False, "filename": p.name, "error": resp.get("error", "Upload failed")}

    async def set_model(self, model: str):
        resp = await self._send("set_model", {"model": model})
        return {"success": resp.get("success", False), "model": model}

    async def _ask(self, prompt: str, timeout: int = 120):
        resp = await self._send("send_prompt", {"text": prompt})
        if not resp.get("success"):
            return {"success": False, "error": resp.get("error", "send_prompt failed")}

        resp = await self._send("stream_response", {"timeout": timeout * 1000}, timeout=timeout + 10)
        data = resp.get("data", {})
        text = data.get("text", "") if isinstance(data, dict) else str(data)

        if not resp.get("success"):
            return {"success": False, "error": f"stream_response failed: {resp.get('error', '?')}"}

        text = self._clean_response(text)
        if not text or len(text.strip()) < 5:
            return {"success": False, "error": f"Response too short ({len(text.strip())} chars) — likely empty or broken"}

        current_resp = await self._send("get_current_model")
        model_data = current_resp.get("data", "unknown")
        model_used = model_data.get("model", "unknown") if isinstance(model_data, dict) else str(model_data)

        return {"success": True, "response": text, "model_used": model_used}

    async def restart_browser(self) -> dict:
        resp = await self._send("restart_browser", {}, timeout=120)
        return {"success": resp.get("success", False)}

    def _clean_response(self, text: str) -> str:
        """Override in subclasses for response cleanup."""
        return text

    async def screenshot(self, out_dir: str):
        return {"success": False, "error": "screenshot via bridge not yet implemented"}

    async def status(self):
        resp = await self._send("is_logged_in")
        data = resp.get("data", False)
        logged_in = data is True or (isinstance(data, dict) and any(v is True for v in data.values()))
        model_resp = await self._send("get_current_model")
        model_data = model_resp.get("data", "unknown")
        model = model_data.get("model", "unknown") if isinstance(model_data, dict) else str(model_data)
        return {"success": True, "logged_in": logged_in, "model": model}


# ---------------------------------------------------------------------------
# ChatGPT Driver (WebSocket bridge on port 9401)
# ---------------------------------------------------------------------------

class ChatGPTDriver(WSBridgeDriver):
    name = "chatgpt"
    BRIDGE_URL = "ws://localhost:9401"

    async def _ask(self, prompt: str, timeout: int = 120):
        """Override: poll get_response with drop-detection for ask_continue.

        On ask_continue, get_response (which returns the last assistant div)
        transitions: old_text -> 0/empty -> new_text. We detect the drop to
        know the new response has started, then wait for stability.
        """
        # Snapshot baseline BEFORE sending prompt
        resp = await self._send("get_response", {})
        pre_text = ""
        if resp.get("success"):
            data = resp.get("data", "")
            pre_text = data.get("text", "") if isinstance(data, dict) else str(data)
        pre_len = len(pre_text)

        resp = await self._send("send_prompt", {"text": prompt})
        if not resp.get("success"):
            return {"success": False, "error": resp.get("error", "send_prompt failed")}

        deadline = time.time() + timeout
        last_text = ""
        last_len = 0
        stable_seconds = 0
        saw_drop = (pre_len == 0)  # If no prior text, skip drop detection

        while time.time() < deadline:
            resp = await self._send("get_response", {})
            text = ""
            if resp.get("success"):
                data = resp.get("data", "")
                text = data.get("text", "") if isinstance(data, dict) else str(data)
            current_len = len(text)

            # Detect drop: length significantly decreased from baseline = new container
            if not saw_drop and pre_len > 0 and current_len < pre_len * 0.5:
                saw_drop = True
                last_text = ""
                last_len = 0
                stable_seconds = 0

            if saw_drop:
                if current_len > last_len:
                    last_text = text
                    last_len = current_len
                    stable_seconds = 0
                elif current_len >= 1000 and current_len > 0:
                    # 1000-char minimum: ChatGPT Thinking emits short preambles
                    # then pauses for reasoning before the real response flows
                    stable_seconds += 1
                    if stable_seconds >= 10:
                        break

            await asyncio.sleep(1)

        if not last_text or len(last_text.strip()) < 5:
            return {"success": False, "error": f"Response too short ({len(last_text.strip())} chars)"}

        last_text = self._clean_response(last_text)

        current_resp = await self._send("get_current_model")
        model_data = current_resp.get("data", "unknown")
        model_used = model_data.get("model", "unknown") if isinstance(model_data, dict) else str(model_data)

        return {"success": True, "response": last_text, "model_used": model_used}


# ---------------------------------------------------------------------------
# Claude Driver (WebSocket bridge on port 9402)
# ---------------------------------------------------------------------------

class ClaudeDriver(WSBridgeDriver):
    name = "claude"
    BRIDGE_URL = "ws://localhost:9402"

    async def _ask(self, prompt: str, timeout: int = 120):
        """Override: poll get_response with drop-detection for ask_continue.

        Same approach as ChatGPT: detect when get_response length drops
        significantly (= new response container appeared), then wait for
        the new content to stabilize. Higher stability threshold (500 chars)
        because Claude's extended thinking produces short noise initially.
        """
        # Snapshot baseline BEFORE sending prompt
        resp = await self._send("get_response", {})
        pre_text = ""
        if resp.get("success"):
            data = resp.get("data", "")
            pre_text = data.get("text", "") if isinstance(data, dict) else str(data)
        pre_len = len(pre_text)

        resp = await self._send("send_prompt", {"text": prompt})
        if not resp.get("success"):
            return {"success": False, "error": resp.get("error", "send_prompt failed")}

        deadline = time.time() + timeout
        last_text = ""
        last_len = 0
        stable_seconds = 0
        saw_drop = (pre_len == 0)  # If no prior text, skip drop detection

        while time.time() < deadline:
            resp = await self._send("get_response", {})
            text = ""
            if resp.get("success"):
                data = resp.get("data", "")
                text = data.get("text", "") if isinstance(data, dict) else str(data)
            current_len = len(text)

            # Detect drop: length significantly decreased from baseline = new container
            if not saw_drop and pre_len > 0 and current_len < pre_len * 0.5:
                saw_drop = True
                last_text = ""
                last_len = 0
                stable_seconds = 0

            if saw_drop:
                if current_len > last_len:
                    last_text = text
                    last_len = current_len
                    stable_seconds = 0
                elif current_len >= 500:
                    # Higher threshold for Claude: extended thinking noise is < 500 chars
                    stable_seconds += 1
                    if stable_seconds >= 10:
                        break

            await asyncio.sleep(1)

        if not last_text or len(last_text.strip()) < 5:
            return {"success": False, "error": f"Response too short ({len(last_text.strip())} chars)"}

        current_resp = await self._send("get_current_model")
        model_data = current_resp.get("data", "unknown")
        model_used = model_data.get("model", "unknown") if isinstance(model_data, dict) else str(model_data)

        return {"success": True, "response": last_text, "model_used": model_used}


# ---------------------------------------------------------------------------
# Gemini Driver (WebSocket bridge)
# ---------------------------------------------------------------------------

# Gemini response cleanup regexes
_MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_PREFIX_RE = re.compile(
    r"^(?:Show thinking\n)?"
    r"(?:Gemini said\n\n)?"
    r"(?:(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,\s+)?"
    + _MONTH +
    r"\s+\d{1,2},?\s+\d{4}[,\s]+(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?"
    r"\s*(?:AM|PM)?(?:\s+\w+)?\n\n)?",
    re.IGNORECASE,
)
_SUFFIX_RE = re.compile(r"\n+Sources\s*$")


def _clean_gemini(text: str) -> str:
    if not text:
        return text
    text = _PREFIX_RE.sub("", text)
    text = _SUFFIX_RE.sub("", text)
    return text.strip()


class GeminiDriver(LLMDriver):
    name = "gemini"
    BRIDGE_URL = "ws://localhost:8785"

    MIME_MAP = {
        ".txt": "text/plain", ".md": "text/markdown", ".py": "text/x-python",
        ".js": "text/javascript", ".json": "application/json", ".csv": "text/csv",
        ".html": "text/html", ".xml": "text/xml", ".yaml": "text/yaml",
        ".yml": "text/yaml", ".pdf": "application/pdf", ".png": "image/png",
    }

    def __init__(self):
        self._ws = None
        self._pending = {}
        self._reader_task = None

    async def connect(self):
        import websockets
        self._ws = await websockets.connect(self.BRIDGE_URL)
        await self._ws.send(json.dumps({"role": "mcp"}))
        self._reader_task = asyncio.create_task(self._reader())

    async def _reader(self):
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                msg_id = msg.get("id")
                if msg_id and msg_id in self._pending:
                    self._pending[msg_id].set_result(msg)
                    del self._pending[msg_id]
        except Exception:
            pass

    async def _send(self, action: str, params: dict = None, timeout: float = 120) -> dict:
        import uuid
        msg_id = str(uuid.uuid4())
        cmd = {"id": msg_id, "action": action, "params": params or {}}
        future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = future
        try:
            await self._ws.send(json.dumps(cmd))
        except Exception:
            del self._pending[msg_id]
            raise
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            return {"success": False, "error": "Timeout"}

    async def close(self):
        if self._reader_task:
            self._reader_task.cancel()
            try: await self._reader_task
            except: pass
        if self._ws:
            await self._ws.close()
        self._ws = self._reader_task = None

    async def new_chat(self):
        resp = await self._send("new_chat")
        return {"success": resp.get("success", False)}

    async def upload_file(self, path: str):
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}
        content_b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        mime = self.MIME_MAP.get(p.suffix.lower(), "application/octet-stream")
        resp = await self._send("upload_file", {
            "filename": p.name, "content_base64": content_b64, "mime_type": mime,
        })
        if resp.get("success"):
            return {"success": True, "filename": p.name}
        error = resp.get("error", "")
        data = resp.get("data", {})
        if isinstance(data, dict):
            error = error or data.get("error", "Upload failed")
        return {"success": False, "filename": p.name, "error": error}

    async def set_model(self, model: str):
        resp = await self._send("set_model", {"model": model})
        if resp.get("success"):
            return {"success": True, "model": model}
        return {"success": False, "error": resp.get("error", f"Model '{model}' not found")}

    async def _ask(self, prompt: str, timeout: int = 120):
        resp = await self._send("send_prompt", {"text": prompt})
        if not resp.get("success"):
            return {"success": False, "error": resp.get("error", "send_prompt failed")}

        resp = await self._send("stream_response", {"timeout": timeout * 1000}, timeout=timeout + 10)
        if not resp.get("success"):
            return {"success": False, "error": f"stream_response failed: {resp.get('error', '?')}"}

        data = resp.get("data", "")
        text = data.get("text", "") if isinstance(data, dict) else str(data)
        text = _clean_gemini(text)

        if not text or len(text.strip()) < 5:
            return {"success": False, "error": f"Response too short ({len(text.strip())} chars) — likely empty or broken"}

        current_resp = await self._send("get_current_model")
        model_data = current_resp.get("data", "unknown")
        model_used = model_data.get("model", "unknown") if isinstance(model_data, dict) else str(model_data)

        return {"success": True, "response": text, "model_used": model_used}

    async def screenshot(self, out_dir: str):
        import subprocess
        p = Path(out_dir) / "gemini.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["docker", "exec", "gemini-firefox", "sh", "-c", "DISPLAY=:99 scrot /tmp/ein-screenshot.png"],
            timeout=5, capture_output=True,
        )
        subprocess.run(
            ["docker", "cp", "gemini-firefox:/tmp/ein-screenshot.png", str(p)],
            timeout=5, capture_output=True,
        )
        return {"success": True, "path": str(p)}

    async def status(self):
        resp = await self._send("is_logged_in")
        data = resp.get("data", False)
        logged_in = data is True or (isinstance(data, dict) and any(v is True for v in data.values()))
        model_resp = await self._send("get_current_model")
        model_data = model_resp.get("data", "unknown")
        model = model_data.get("model", "unknown") if isinstance(model_data, dict) else str(model_data)
        return {"success": True, "logged_in": logged_in, "model": model}


# ---------------------------------------------------------------------------
# Parallel dispatch
# ---------------------------------------------------------------------------

DRIVERS = {
    "chatgpt": ChatGPTDriver,
    "claude": ClaudeDriver,
    "gemini": GeminiDriver,
}

DEFAULT_MODELS = {
    "chatgpt": "Thinking",
    "claude": "Opus 4.6",
    "gemini": "Pro",
}


async def run_driver(driver: LLMDriver, action: str, params: dict) -> dict:
    try:
        log.info("[%s] connect START at %s", driver.name, time.strftime("%H:%M:%S"))
        await driver.connect()
        log.info("[%s] connect DONE at %s", driver.name, time.strftime("%H:%M:%S"))
        return await driver.execute(action, params)
    except Exception as e:
        log.exception("Driver %s failed", driver.name)
        return {"llm": driver.name, "success": False, "error": str(e), "elapsed_seconds": 0}
    finally:
        try:
            await driver.close()
        except Exception:
            pass


async def dispatch_single(action: str, params: dict, target: str) -> dict:
    """Run a single LLM driver."""
    cls = DRIVERS.get(target)
    if not cls:
        return {"llm": target, "success": False, "error": f"Unknown LLM: {target}"}

    p = dict(params)
    if target in DEFAULT_MODELS and not p.get("model"):
        p["model"] = DEFAULT_MODELS[target]

    driver = cls()
    return await run_driver(driver, action, p)


async def dispatch_all(action: str, params, targets: list[str]) -> dict:
    """Run all LLM drivers in parallel via asyncio.gather — all WebSocket bridges.
    params can be a single dict (same for all) or a dict-of-dicts keyed by engine name.
    """
    drivers = []
    driver_params = []
    for name in targets:
        cls = DRIVERS.get(name)
        if not cls:
            log.warning("Unknown LLM: %s", name)
            continue
        drivers.append(cls())
        # Support both single params dict and per-engine params dict
        if isinstance(params, dict) and name in params and isinstance(params[name], dict):
            p = dict(params[name])
        else:
            p = dict(params)
        if name in DEFAULT_MODELS and not p.get("model"):
            p["model"] = DEFAULT_MODELS[name]
        driver_params.append(p)

    t0 = time.time()
    # Stagger launches: first driver starts immediately, rest wait 3s
    # This ensures the first target in --only list launches its browser first
    async def staggered_run(driver, params, delay):
        if delay > 0:
            await asyncio.sleep(delay)
        return await run_driver(driver, action, params)

    results = await asyncio.gather(
        *(staggered_run(d, p, i * 3) for i, (d, p) in enumerate(zip(drivers, driver_params)))
    )
    return {
        "action": action,
        "results": {r["llm"]: r for r in results},
        "total_elapsed_seconds": round(time.time() - t0, 1),
    }


def dispatch_parallel(action: str, params: dict, targets: list[str]) -> dict:
    """Spawn separate processes for each LLM — true OS-level parallelism."""
    import subprocess

    script = str(Path(__file__).resolve())
    procs = {}
    t0 = time.time()

    for name in targets:
        cmd = [sys.executable, script, "--action", action, "--only", name,
               "--timeout", str(params.get("timeout", 120))]
        if params.get("prompt"):
            cmd += ["--prompt", params["prompt"]]
        if params.get("path"):
            cmd += ["--upload", params["path"]]
        if params.get("model"):
            cmd += ["--model", params["model"]]
        if params.get("screenshot_dir") and params["screenshot_dir"] != ".":
            cmd += ["--screenshot-dir", params["screenshot_dir"]]

        procs[name] = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        log.info("Spawned %s (pid %d)", name, procs[name].pid)

    # Wait for all to complete
    results = {}
    for name, proc in procs.items():
        stdout, stderr = proc.communicate(timeout=params.get("timeout", 120) + 30)
        try:
            data = json.loads(stdout.decode())
            # Extract the single result from the nested output
            if "results" in data and name in data["results"]:
                results[name] = data["results"][name]
            else:
                results[name] = data
        except (json.JSONDecodeError, Exception) as e:
            results[name] = {
                "llm": name, "success": False,
                "error": f"Process failed: {e}\nstderr: {stderr.decode()[-500:]}",
            }

    return {
        "action": action,
        "results": results,
        "total_elapsed_seconds": round(time.time() - t0, 1),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ein parallel LLM driver")
    parser.add_argument("--action", required=True,
                        choices=["ask", "ask_continue", "new_chat", "upload_file",
                                 "set_model", "screenshot", "status"],
                        help="Action to perform")
    parser.add_argument("--prompt", help="Prompt text (for ask/full)")
    parser.add_argument("--prompts-json", help="JSON file mapping engine names to per-engine prompts (overrides --prompt)")
    parser.add_argument("--upload", help="File path to upload (for upload_file/full)")
    parser.add_argument("--model", help="Model override (applies to all LLMs)")
    parser.add_argument("--model-chatgpt", help="ChatGPT model override")
    parser.add_argument("--model-claude", help="Claude model override")
    parser.add_argument("--model-gemini", help="Gemini model override", default="Pro")
    parser.add_argument("--fresh", action="store_true", help="Start fresh chats before ask")
    parser.add_argument("--fresh-browsers", action="store_true",
                        help="Restart browsers before running (clears stale DOM state)")
    parser.add_argument("--timeout", type=int, default=120, help="Response timeout in seconds")
    parser.add_argument("--only", help="Comma-separated list of LLMs to use (chatgpt,claude,gemini)")
    parser.add_argument("--screenshot-dir", default=".", help="Directory for screenshots")
    # Zero-tolerance is always on. No opt-out. If any engine fails, the run dies.
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    # Load per-engine prompts if provided
    per_engine_prompts = {}
    if args.prompts_json:
        pj_path = Path(args.prompts_json).expanduser().resolve()
        if not pj_path.exists():
            print(f"PREFLIGHT FAIL: prompts-json file not found: {args.prompts_json}", file=sys.stderr)
            sys.exit(1)
        per_engine_prompts = json.loads(pj_path.read_text(encoding="utf-8"))

    params = {
        "prompt": args.prompt or "",
        "path": args.upload or "",
        "model": args.model or "",
        "timeout": args.timeout,
        "screenshot_dir": args.screenshot_dir,
    }

    # Apply per-LLM model overrides to DEFAULT_MODELS
    if args.model_chatgpt:
        DEFAULT_MODELS["chatgpt"] = args.model_chatgpt
    if args.model_claude:
        DEFAULT_MODELS["claude"] = args.model_claude
    if args.model_gemini:
        DEFAULT_MODELS["gemini"] = args.model_gemini

    only = [x.strip() for x in args.only.split(",")] if args.only else None
    targets = only or list(DRIVERS.keys())

    if args.fresh_browsers:
        restart_targets = [t for t in targets if t in ("chatgpt", "claude")]
        if restart_targets:
            log.info("Restarting browsers for: %s", restart_targets)
            asyncio.run(dispatch_all("restart_browser", {}, restart_targets))
            log.info("Browser restart complete")

    # --- PREFLIGHT CHECKS (for ask/ask_continue only) ---
    if args.action in ("ask", "ask_continue"):
        # 1. Upload file must exist if specified
        if args.upload:
            upload_path = Path(args.upload).expanduser().resolve()
            if not upload_path.exists():
                print(f"PREFLIGHT FAIL: upload file not found: {args.upload}", file=sys.stderr)
                sys.exit(1)

        # 2. Prompt must not be empty (unless per-engine prompts provided)
        if not per_engine_prompts and (not args.prompt or not args.prompt.strip()):
            print("PREFLIGHT FAIL: --prompt or --prompts-json is required", file=sys.stderr)
            sys.exit(1)

        # 3. All bridges must be reachable and logged in
        log.info("PREFLIGHT: verifying all %d engines are reachable and logged in...", len(targets))
        preflight = asyncio.run(dispatch_all("status", {}, targets))
        preflight_failed = []
        for name, r in preflight.get("results", {}).items():
            if not r.get("success"):
                preflight_failed.append(f"{name}: bridge unreachable — {r.get('error', '?')}")
            elif not r.get("logged_in"):
                preflight_failed.append(f"{name}: not logged in")
        if preflight_failed:
            print("PREFLIGHT FAIL: not all engines ready:", file=sys.stderr)
            for f in preflight_failed:
                print(f"  - {f}", file=sys.stderr)
            sys.exit(1)
        log.info("PREFLIGHT: all %d engines OK", len(targets))

    # --- Apply per-engine prompt overrides ---
    if per_engine_prompts:
        per_engine_params = {}
        for name in targets:
            p = dict(params)
            if name in per_engine_prompts:
                p["prompt"] = per_engine_prompts[name]
            elif not p["prompt"]:
                print(f"PREFLIGHT FAIL: no prompt for engine '{name}' in --prompts-json and no --prompt fallback",
                      file=sys.stderr)
                sys.exit(1)
            per_engine_params[name] = p
    else:
        per_engine_params = {name: params for name in targets}

    # --- DISPATCH ---
    if len(targets) == 1:
        t = targets[0]
        result = asyncio.run(dispatch_single(args.action, per_engine_params[t], t))
        result = {"action": args.action, "results": {result["llm"]: result},
                  "total_elapsed_seconds": result.get("elapsed_seconds", 0)}
    else:
        # All drivers use WebSocket bridges — true parallelism in one process
        result = asyncio.run(dispatch_all(args.action, per_engine_params, targets))
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Zero-tolerance: if any engine failed, the run is dead. No degraded mode.
    if args.action in ("ask", "ask_continue"):
        failed = [
            name for name, r in result.get("results", {}).items()
            if not r.get("success", False)
        ]
        if failed:
            print(f"FATAL: engines failed: {', '.join(failed)}. "
                  f"Zero-tolerance policy: all engines must succeed. Run aborted.",
                  file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
