"""Desktop automation layer for ULTRON - Window management, app control, browser automation.

Provides cross-platform desktop control capabilities for JARVIS-level assistance.
"""
from __future__ import annotations
import os
import sys
import subprocess
import json
import time
import threading
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

# Platform-specific imports
if sys.platform == "win32":
    try:
        import win32gui
        import win32con
        import win32api
        import win32process
        _HAVE_WIN32 = True
    except ImportError:
        _HAVE_WIN32 = False
else:
    _HAVE_WIN32 = False

# Optional: browser automation via CDP (Chrome DevTools Protocol)
try:
    import websockets
    import asyncio
    _HAVE_CDP = True
except ImportError:
    _HAVE_CDP = False


@dataclass
class WindowInfo:
    """Information about a desktop window."""
    handle: int
    title: str
    class_name: str
    process_id: int
    process_name: str
    rect: Tuple[int, int, int, int]  # left, top, right, bottom
    is_visible: bool
    is_minimized: bool
    is_maximized: bool


@dataclass
class AppInfo:
    """Information about a running application."""
    name: str
    pid: int
    exe_path: str
    windows: List[WindowInfo]


class WindowManager:
    """Cross-platform window management."""

    def __init__(self):
        self._lock = threading.Lock()

    def list_windows(self, filter_visible: bool = True) -> List[WindowInfo]:
        """List all windows (optionally only visible)."""
        if sys.platform == "win32" and _HAVE_WIN32:
            return self._list_windows_win32(filter_visible)
        else:
            return self._list_windows_unix(filter_visible)

    def _list_windows_win32(self, filter_visible: bool) -> List[WindowInfo]:
        windows = []

        def enum_callback(hwnd, _):
            if filter_visible and not win32gui.IsWindowVisible(hwnd):
                return True
            if not win32gui.GetWindowText(hwnd):
                return True

            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process_name = ""
                try:
                    import psutil
                    process_name = psutil.Process(pid).name()
                except Exception:
                    pass

                rect = win32gui.GetWindowRect(hwnd)
                placement = win32gui.GetWindowPlacement(hwnd)
                is_minimized = placement[1] == win32con.SW_SHOWMINIMIZED
                is_maximized = placement[1] == win32con.SW_SHOWMAXIMIZED

                windows.append(WindowInfo(
                    handle=hwnd,
                    title=win32gui.GetWindowText(hwnd),
                    class_name=win32gui.GetClassName(hwnd),
                    process_id=pid,
                    process_name=process_name,
                    rect=rect,
                    is_visible=win32gui.IsWindowVisible(hwnd),
                    is_minimized=is_minimized,
                    is_maximized=is_maximized
                ))
            except Exception:
                pass
            return True

        win32gui.EnumWindows(enum_callback, None)
        return windows

    def _list_windows_unix(self, filter_visible: bool) -> List[WindowInfo]:
        """List windows on Linux using wmctrl/xdotool."""
        windows = []
        try:
            # Try wmctrl first
            result = subprocess.run(["wmctrl", "-l", "-G", "-p"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = line.split(None, 6)
                    if len(parts) >= 7:
                        handle = int(parts[0], 16)
                        desktop = parts[1]
                        pid = int(parts[2])
                        x, y, w, h = map(int, parts[3:7])
                        title = parts[7] if len(parts) > 7 else ""
                        windows.append(WindowInfo(
                            handle=handle,
                            title=title,
                            class_name="",
                            process_id=pid,
                            process_name="",
                            rect=(x, y, x + w, y + h),
                            is_visible=True,
                            is_minimized=False,
                            is_maximized=False
                        ))
        except Exception:
            pass
        return windows

    def find_window(self, title_contains: str = "", class_name: str = "",
                    process_name: str = "") -> Optional[WindowInfo]:
        """Find a window by title, class, or process name."""
        for w in self.list_windows():
            if title_contains and title_contains.lower() not in w.title.lower():
                continue
            if class_name and class_name.lower() not in w.class_name.lower():
                continue
            if process_name and process_name.lower() not in w.process_name.lower():
                continue
            return w
        return None

    def focus_window(self, window: WindowInfo) -> bool:
        """Bring window to foreground and focus."""
        if sys.platform == "win32" and _HAVE_WIN32:
            return self._focus_window_win32(window)
        else:
            return self._focus_window_unix(window)

    def _focus_window_win32(self, window: WindowInfo) -> bool:
        try:
            if window.is_minimized:
                win32gui.ShowWindow(window.handle, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(window.handle)
            return True
        except Exception:
            return False

    def _focus_window_unix(self, window: WindowInfo) -> bool:
        try:
            subprocess.run(["wmctrl", "-i", "-a", hex(window.handle)],
                           capture_output=True, timeout=3)
            return True
        except Exception:
            return False

    def move_resize_window(self, window: WindowInfo,
                           x: int, y: int, width: int, height: int) -> bool:
        """Move and resize a window."""
        if sys.platform == "win32" and _HAVE_WIN32:
            try:
                win32gui.MoveWindow(window.handle, x, y, width, height, True)
                return True
            except Exception:
                return False
        else:
            try:
                subprocess.run(["wmctrl", "-i", "-r", hex(window.handle),
                                "-e", f"0,{x},{y},{width},{height}"],
                               capture_output=True, timeout=3)
                return True
            except Exception:
                return False

    def minimize_window(self, window: WindowInfo) -> bool:
        """Minimize a window."""
        if sys.platform == "win32" and _HAVE_WIN32:
            try:
                win32gui.ShowWindow(window.handle, win32con.SW_MINIMIZE)
                return True
            except Exception:
                return False
        else:
            try:
                subprocess.run(["wmctrl", "-i", "-r", hex(window.handle),
                                "-b", "add,hidden"], capture_output=True, timeout=3)
                return True
            except Exception:
                return False

    def maximize_window(self, window: WindowInfo) -> bool:
        """Maximize a window."""
        if sys.platform == "win32" and _HAVE_WIN32:
            try:
                win32gui.ShowWindow(window.handle, win32con.SW_MAXIMIZE)
                return True
            except Exception:
                return False
        else:
            try:
                subprocess.run(["wmctrl", "-i", "-r", hex(window.handle),
                                "-b", "add,maximized_vert,maximized_horz"],
                               capture_output=True, timeout=3)
                return True
            except Exception:
                return False

    def close_window(self, window: WindowInfo) -> bool:
        """Close a window gracefully."""
        if sys.platform == "win32" and _HAVE_WIN32:
            try:
                win32gui.PostMessage(window.handle, win32con.WM_CLOSE, 0, 0)
                return True
            except Exception:
                return False
        else:
            try:
                subprocess.run(["wmctrl", "-i", "-c", hex(window.handle)],
                               capture_output=True, timeout=3)
                return True
            except Exception:
                return False


class AppController:
    """Application launch and control."""

    def __init__(self):
        self._lock = threading.Lock()

    def launch(self, app_name: str, args: List[str] = None) -> Optional[int]:
        """Launch an application, return PID."""
        args = args or []
        try:
            if sys.platform == "win32":
                # Try common Windows app paths
                app_paths = {
                    "chrome": ["chrome.exe"] + args,
                    "firefox": ["firefox.exe"] + args,
                    "edge": ["msedge.exe"] + args,
                    "notepad": ["notepad.exe"] + args,
                    "calculator": ["calc.exe"] + args,
                    "terminal": ["cmd.exe"] + args,
                    "powershell": ["powershell.exe"] + args,
                    "explorer": ["explorer.exe"] + args,
                    "vscode": ["code.exe"] + args,
                }
                cmd = app_paths.get(app_name.lower(), [app_name] + args)
                proc = subprocess.Popen(cmd, shell=True)
            else:
                proc = subprocess.Popen([app_name] + args)
            return proc.pid
        except Exception as e:
            print(f"Failed to launch {app_name}: {e}")
            return None

    def get_running_apps(self) -> List[AppInfo]:
        """Get list of running applications with their windows."""
        apps = {}
        wm = WindowManager()
        for win in wm.list_windows():
            key = win.process_name or win.class_name
            if key not in apps:
                apps[key] = AppInfo(
                    name=key,
                    pid=win.process_id,
                    exe_path="",
                    windows=[]
                )
            apps[key].windows.append(win)
        return list(apps.values())

    def kill_app(self, app_name: str) -> bool:
        """Kill all processes matching app name."""
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", f"{app_name}.exe"],
                               capture_output=True)
            else:
                subprocess.run(["pkill", "-f", app_name], capture_output=True)
            return True
        except Exception:
            return False

    def get_app_path(self, app_name: str) -> Optional[str]:
        """Find the executable path for an app."""
        common_paths = {
            "chrome": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ],
            "firefox": [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
            ],
            "edge": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            ],
            "vscode": [
                r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\Code.exe".format(os.getenv("USERNAME", "")),
            ],
        }
        for path in common_paths.get(app_name.lower(), []):
            if os.path.exists(path):
                return path
        return None


class BrowserAutomation:
    """Browser automation via Chrome DevTools Protocol (CDP)."""

    def __init__(self, debug_port: int = 9222):
        self.debug_port = debug_port
        self._ws = None
        self._msg_id = 0
        self._lock = threading.Lock()

    async def connect(self) -> bool:
        """Connect to Chrome via CDP."""
        if not _HAVE_CDP:
            return False
        try:
            # Get list of targets
            import urllib.request
            with urllib.request.urlopen(f"http://localhost:{self.debug_port}/json") as resp:
                targets = json.loads(resp.read().decode())

            # Find first page target
            page_target = next((t for t in targets if t.get("type") == "page"), None)
            if not page_target:
                return False

            ws_url = page_target.get("webSocketDebuggerUrl")
            if not ws_url:
                return False

            self._ws = await websockets.connect(ws_url)
            return True
        except Exception:
            return False

    async def _send(self, method: str, params: Dict = None) -> Dict:
        """Send CDP command and wait for response."""
        if not self._ws:
            return {"error": "not connected"}

        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method, "params": params or {}}
        await self._ws.send(json.dumps(msg))

        # Wait for response
        async for raw in self._ws:
            resp = json.loads(raw)
            if resp.get("id") == self._msg_id:
                return resp
        return {"error": "no response"}

    async def navigate(self, url: str) -> Dict:
        """Navigate to URL."""
        return await self._send("Page.navigate", {"url": url})

    async def evaluate(self, expression: str) -> Dict:
        """Evaluate JavaScript in page context."""
        return await self._send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True
        })

    async def click(self, selector: str) -> Dict:
        """Click element by CSS selector."""
        # Get element position
        pos_result = await self.evaluate(f"""
            (() => {{
                const el = document.querySelector('{selector}');
                if (!el) return {{error: 'not found'}};
                const rect = el.getBoundingClientRect();
                return {{x: rect.left + rect.width/2, y: rect.top + rect.height/2}};
            }})()
        """)
        if "error" in pos_result.get("result", {}).get("result", {}).get("value", {}):
            return {"error": "element not found"}

        pos = pos_result["result"]["result"]["value"]
        # Dispatch click via Input domain
        await self._send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": pos["x"], "y": pos["y"],
            "button": "left", "clickCount": 1
        })
        await self._send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": pos["x"], "y": pos["y"],
            "button": "left", "clickCount": 1
        })
        return {"ok": True}

    async def type_text(self, selector: str, text: str) -> Dict:
        """Type text into element."""
        await self._send("Input.insertText", {"text": text})
        return {"ok": True}

    async def screenshot(self) -> bytes:
        """Take screenshot."""
        result = await self._send("Page.captureScreenshot", {"format": "png"})
        import base64
        return base64.b64decode(result.get("result", {}).get("data", ""))

    async def get_page_content(self) -> str:
        """Get page HTML."""
        result = await self.evaluate("document.documentElement.outerHTML")
        return result.get("result", {}).get("result", {}).get("value", "")

    async def close(self):
        """Close connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None


class ScreenCapture:
    """Screen capture and OCR."""

    _have_mss = True

    def __init__(self):
        try:
            import mss
        except ImportError:
            self._have_mss = False

    def capture_screen(self, region: Tuple[int, int, int, int] = None) -> bytes:
        """Capture screen to PNG bytes."""
        if not self._have_mss:
            return b""
        if sys.platform == "win32":
            try:
                import mss
                with mss.mss() as sct:
                    monitor = region or sct.monitors[1]  # Primary monitor
                    if region:
                        monitor = {"left": region[0], "top": region[1],
                                   "width": region[2], "height": region[3]}
                    img = sct.grab(monitor)
                    import mss.tools
                    import io
                    output = io.BytesIO()
                    mss.tools.to_png(img.rgb, img.size, output)
                    return output.getvalue()
            except Exception:
                pass
        else:
            try:
                import subprocess
                cmd = ["import", "-window", "root"]
                if region:
                    cmd += ["-crop", f"{region[2]}x{region[3]}+{region[0]}+{region[1]}"]
                cmd.append("png:-")
                return subprocess.check_output(cmd, timeout=5)
            except Exception:
                pass
        return b""

    def capture_window(self, window: WindowInfo) -> bytes:
        """Capture specific window."""
        return self.capture_screen(window.rect)

    def ocr_image(self, image_bytes: bytes) -> str:
        """Extract text from image using OCR (requires tesseract)."""
        try:
            import pytesseract
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_bytes))
            return pytesseract.image_to_string(img)
        except Exception:
            return ""


class GlobalHotkeys:
    """Global hotkey registration and handling."""

    def __init__(self):
        self._hotkeys: Dict[str, callable] = {}
        self._running = False
        self._thread = None

    def register(self, key_combo: str, callback: callable) -> bool:
        """Register a global hotkey (e.g., 'ctrl+alt+u')."""
        if sys.platform == "win32" and _HAVE_WIN32:
            # Would need RegisterHotKey - simplified for now
            self._hotkeys[key_combo] = callback
            return True
        else:
            # Linux: would use xbindkeys or similar
            self._hotkeys[key_combo] = callback
            return True

    def unregister(self, key_combo: str) -> bool:
        """Unregister a hotkey."""
        if key_combo in self._hotkeys:
            del self._hotkeys[key_combo]
            return True
        return False

    def start_listening(self):
        """Start listening for hotkeys (background thread)."""
        # Placeholder - actual implementation needs platform-specific code
        pass

    def stop_listening(self):
        """Stop listening."""
        pass


class DesktopAutomation:
    """Unified desktop automation interface."""

    def __init__(self):
        self.windows = WindowManager()
        self.apps = AppController()
        self.browser = BrowserAutomation()
        self.screen = ScreenCapture()
        self.hotkeys = GlobalHotkeys()

    def find_and_focus(self, query: str) -> bool:
        """Find window by title/process and focus it."""
        win = self.windows.find_window(title_contains=query)
        if win:
            return self.windows.focus_window(win)
        # Try process name
        win = self.windows.find_window(process_name=query)
        if win:
            return self.windows.focus_window(win)
        return False

    def launch_and_wait(self, app_name: str, timeout: float = 10.0) -> Optional[WindowInfo]:
        """Launch app and wait for its window to appear."""
        pid = self.apps.launch(app_name)
        if not pid:
            return None

        start = time.time()
        while time.time() - start < timeout:
            win = self.windows.find_window(process_name=app_name)
            if win:
                return win
            time.sleep(0.5)
        return None

    def arrange_windows(self, layout: str = "side_by_side") -> bool:
        """Arrange windows in a layout."""
        wins = self.windows.list_windows(filter_visible=True)
        if len(wins) < 2:
            return False

        if sys.platform == "win32":
            import win32api
            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)
        else:
            screen_w, screen_h = 1920, 1080  # Default

        if layout == "side_by_side":
            mid = screen_w // 2
            self.windows.move_resize_window(wins[0], 0, 0, mid, screen_h)
            if len(wins) > 1:
                self.windows.move_resize_window(wins[1], mid, 0, screen_w - mid, screen_h)
            return True
        elif layout == "stacked":
            mid = screen_h // 2
            self.windows.move_resize_window(wins[0], 0, 0, screen_w, mid)
            if len(wins) > 1:
                self.windows.move_resize_window(wins[1], 0, mid, screen_w, screen_h - mid)
            return True
        return False


# Convenience functions
def get_desktop() -> DesktopAutomation:
    """Get desktop automation singleton."""
    return DesktopAutomation()


if __name__ == "__main__":
    desk = get_desktop()
    print("Windows:")
    for w in desk.windows.list_windows()[:10]:
        print(f"  {w.title[:50]} | {w.process_name} | {w.rect}")
    print("\nApps:")
    for a in desk.apps.get_running_apps()[:5]:
        print(f"  {a.name} (PID: {a.pid}) - {len(a.windows)} windows")