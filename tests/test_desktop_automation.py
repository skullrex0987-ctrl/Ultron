"""Tests for desktop automation layer."""
import sys
import os
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "laptop", "core"))

# Import after path setup
import desktop_automation as da
from desktop_automation import (
    WindowInfo, AppInfo, WindowManager, AppController,
    BrowserAutomation, ScreenCapture, GlobalHotkeys, DesktopAutomation
)
import asyncio


class TestWindowInfo(unittest.TestCase):
    def test_window_info_creation(self):
        win = WindowInfo(
            handle=12345,
            title="Test Window",
            class_name="TestClass",
            process_id=100,
            process_name="test.exe",
            rect=(0, 0, 800, 600),
            is_visible=True,
            is_minimized=False,
            is_maximized=False
        )
        self.assertEqual(win.title, "Test Window")
        self.assertEqual(win.rect, (0, 0, 800, 600))


class TestAppInfo(unittest.TestCase):
    def test_app_info_creation(self):
        win = WindowInfo(1, "Win1", "Class", 100, "app.exe", (0,0,100,100), True, False, False)
        app = AppInfo(name="test", pid=100, exe_path="/path", windows=[win])
        self.assertEqual(app.name, "test")
        self.assertEqual(len(app.windows), 1)


class TestWindowManager(unittest.TestCase):
    @mock.patch("desktop_automation.sys.platform", "win32")
    @mock.patch("desktop_automation._HAVE_WIN32", True)
    @mock.patch("desktop_automation.win32gui")
    @mock.patch("desktop_automation.win32process")
    @mock.patch("desktop_automation.win32con")
    def test_list_windows_win32(self, mock_win32con, mock_win32process, mock_win32gui):
        mock_win32con.SW_SHOWMINIMIZED = 2
        mock_win32con.SW_SHOWMAXIMIZED = 3
        
        def enum_side_effect(cb, _):
            cb(1001, None)
            cb(1002, None)
        mock_win32gui.EnumWindows.side_effect = enum_side_effect
        mock_win32gui.GetWindowText.side_effect = ["Window 1", "Window 2"]
        mock_win32gui.GetClassName.side_effect = ["Class1", "Class2"]
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetWindowRect.side_effect = [(0,0,800,600), (100,100,900,700)]
        mock_win32gui.GetWindowPlacement.side_effect = [(0,1,0,0,0), (0,1,0,0,0)]
        mock_win32process.GetWindowThreadProcessId.side_effect = [(0, 100), (0, 200)]

        with mock.patch("psutil.Process") as mock_proc:
            mock_proc.return_value.name.return_value = "test.exe"
            wm = WindowManager()
            windows = wm.list_windows()

        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0].title, "Window 1")
        self.assertEqual(windows[0].process_id, 100)

    @mock.patch("desktop_automation.sys.platform", "linux")
    @mock.patch("subprocess.run")
    def test_list_windows_unix(self, mock_run):
        mock_result = mock.MagicMock()
        mock_result.stdout = "0x00100001  0 1234  0 0 800 600  Test Window"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        wm = WindowManager()
        windows = wm.list_windows()

        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].title, "Test Window")

    def test_find_window(self):
        wm = WindowManager()
        wm.list_windows = mock.MagicMock(return_value=[
            WindowInfo(1, "Chrome Browser", "Chrome", 100, "chrome.exe", (0,0,800,600), True, False, False),
            WindowInfo(2, "Notepad", "Notepad", 200, "notepad.exe", (0,0,600,400), True, False, False),
        ])

        found = wm.find_window(title_contains="chrome")
        self.assertIsNotNone(found)
        self.assertEqual(found.title, "Chrome Browser")

        found = wm.find_window(process_name="notepad")
        self.assertIsNotNone(found)
        self.assertEqual(found.title, "Notepad")

        not_found = wm.find_window(title_contains="nonexistent")
        self.assertIsNone(not_found)


class TestAppController(unittest.TestCase):
    @mock.patch("desktop_automation.subprocess.Popen")
    def test_launch(self, mock_popen):
        mock_proc = mock.MagicMock()
        mock_proc.pid = 1234
        mock_popen.return_value = mock_proc

        ac = AppController()
        pid = ac.launch("notepad", ["test.txt"])
        self.assertEqual(pid, 1234)
        mock_popen.assert_called_once()

    @mock.patch("desktop_automation.WindowManager")
    def test_get_running_apps(self, mock_wm_class):
        mock_wm = mock.MagicMock()
        mock_wm.list_windows.return_value = [
            WindowInfo(1, "Win1", "Class1", 100, "app.exe", (0,0,100,100), True, False, False),
            WindowInfo(2, "Win2", "Class1", 100, "app.exe", (0,0,200,200), True, False, False),
            WindowInfo(3, "Win3", "Class2", 200, "other.exe", (0,0,300,300), True, False, False),
        ]
        mock_wm_class.return_value = mock_wm

        ac = AppController()
        apps = ac.get_running_apps()

        self.assertEqual(len(apps), 2)
        app_names = {a.name for a in apps}
        self.assertIn("app.exe", app_names)
        self.assertIn("other.exe", app_names)


class TestBrowserAutomation(unittest.TestCase):
    @mock.patch("desktop_automation._HAVE_CDP", True)
    @mock.patch("websockets.connect")
    @mock.patch("urllib.request.urlopen")
    def test_connect(self, mock_urlopen, mock_ws_connect):
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b'[{"type": "page", "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/1"}]'
        # Mock websockets connect returning an async context manager
        mock_ws = mock.MagicMock()
        mock_ws_connect.return_value = mock_ws
        # Make it work as async context manager
        type(mock_ws).__aenter__ = mock.MagicMock(return_value=mock_ws)
        type(mock_ws).__aexit__ = mock.MagicMock(return_value=None)

        ba = BrowserAutomation()
        result = asyncio.run(ba.connect())

        self.assertTrue(result)
        mock_ws_connect.assert_called_once()

    @mock.patch("desktop_automation._HAVE_CDP", False)
    def test_connect_no_cdp(self):
        ba = BrowserAutomation()
        result = asyncio.run(ba.connect())
        self.assertFalse(result)


class TestScreenCapture(unittest.TestCase):
    @mock.patch("desktop_automation.sys.platform", "win32")
    @mock.patch("desktop_automation.ScreenCapture._have_mss", True)
    @mock.patch("mss.mss")
    def test_capture_screen(self, mock_mss_class):
        mock_sct = mock.MagicMock()
        mock_mss_class.return_value.__enter__.return_value = mock_sct
        mock_sct.monitors = [{}, {"left": 0, "top": 0, "width": 1920, "height": 1080}]
        mock_sct.grab.return_value = mock.MagicMock(rgb=b"rgbdata", size=(1920, 1080))

        with mock.patch("mss.tools.to_png") as mock_to_png:
            with mock.patch("io.BytesIO") as mock_bytesio:
                mock_bytesio.return_value.getvalue.return_value = b"pngdata"
                sc = ScreenCapture()
                data = sc.capture_screen()

        self.assertEqual(data, b"pngdata")

    def test_capture_screen_no_mss(self):
        """Test graceful handling when mss is not available."""
        sc = ScreenCapture()
        with mock.patch("desktop_automation.ScreenCapture._have_mss", False):
            data = sc.capture_screen()
        self.assertEqual(data, b"")


class TestDesktopAutomation(unittest.TestCase):
    def test_find_and_focus(self):
        desk = DesktopAutomation()
        mock_win = WindowInfo(1, "Chrome", "Chrome", 100, "chrome.exe", (0,0,800,600), True, False, False)
        desk.windows.find_window = mock.MagicMock(return_value=mock_win)
        desk.windows.focus_window = mock.MagicMock(return_value=True)

        result = desk.find_and_focus("chrome")
        self.assertTrue(result)
        desk.windows.find_window.assert_called_with(title_contains="chrome")
        desk.windows.focus_window.assert_called_with(mock_win)

    def test_arrange_windows(self):
        desk = DesktopAutomation()
        wins = [
            WindowInfo(1, "Win1", "C1", 100, "a.exe", (0,0,800,600), True, False, False),
            WindowInfo(2, "Win2", "C2", 200, "b.exe", (0,0,800,600), True, False, False),
        ]
        desk.windows.list_windows = mock.MagicMock(return_value=wins)
        desk.windows.move_resize_window = mock.MagicMock(return_value=True)

        with mock.patch("desktop_automation.sys.platform", "win32"):
            with mock.patch("desktop_automation.win32api.GetSystemMetrics", side_effect=[1920, 1080]):
                result = desk.arrange_windows("side_by_side")

        self.assertTrue(result)
        self.assertEqual(desk.windows.move_resize_window.call_count, 2)


class TestGlobalHotkeys(unittest.TestCase):
    def test_register_unregister(self):
        hk = GlobalHotkeys()
        callback = mock.MagicMock()

        result = hk.register("ctrl+alt+u", callback)
        self.assertTrue(result)
        self.assertIn("ctrl+alt+u", hk._hotkeys)

        result = hk.unregister("ctrl+alt+u")
        self.assertTrue(result)
        self.assertNotIn("ctrl+alt+u", hk._hotkeys)

        result = hk.unregister("nonexistent")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)