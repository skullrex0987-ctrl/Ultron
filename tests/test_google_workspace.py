"""Tests for Google Workspace integration."""
import sys
import os
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "laptop", "core"))

from google_workspace import (
    GoogleConfig, GoogleAuth, GmailClient, CalendarClient,
    DriveClient, DocsClient, SheetsClient, GoogleWorkspace, SCOPES
)


class TestGoogleConfig(unittest.TestCase):
    def test_default_paths(self):
        config = GoogleConfig()
        self.assertIn("google_credentials.json", config.credentials_file)
        self.assertIn("google_token.pickle", config.token_file)


class TestGoogleAuth(unittest.TestCase):
    @mock.patch("google_workspace._HAVE_GOOGLE", True)
    @mock.patch("google_workspace.InstalledAppFlow")
    @mock.patch("google_workspace.Credentials")
    @mock.patch("google_workspace.Request")
    @mock.patch("google_workspace.pickle.dump")
    def test_creds_refresh(self, mock_pickle_dump, mock_request, mock_creds_class, mock_flow_class):
        # Mock expired credentials with refresh token
        mock_creds = mock.MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds.refresh = mock.MagicMock()

        # Mock the flow to not be called since refresh should work
        mock_flow = mock.MagicMock()
        mock_flow.run_local_server.return_value = mock.MagicMock()
        mock_flow_class.from_client_secrets_file.return_value = mock_flow

        config = GoogleConfig(
            credentials_file="/fake/creds.json",
            token_file="/fake/token.pickle"
        )

        with mock.patch("os.path.exists", side_effect=[True, True]):  # token exists, creds file exists
            with mock.patch("builtins.open", mock.mock_open(read_data=b"pickled_creds")):
                with mock.patch("pickle.load", return_value=mock_creds):
                    auth = GoogleAuth(config)
                    creds = auth.get_credentials()

        self.assertEqual(creds, mock_creds)
        mock_creds.refresh.assert_called_once_with(mock_request.return_value)
        # Flow should NOT be called since refresh worked
        mock_flow_class.from_client_secrets_file.assert_not_called()
        mock_pickle_dump.assert_called_once()


class TestGmailClient(unittest.TestCase):
    @mock.patch("google_workspace._HAVE_GOOGLE", True)
    @mock.patch("google_workspace.build")
    def test_list_messages(self, mock_build):
        mock_service = mock.MagicMock()
        mock_build.return_value = mock_service

        # Mock list response
        mock_list = mock.MagicMock()
        mock_list.execute.return_value = {"messages": [{"id": "msg1"}, {"id": "msg2"}]}
        mock_service.users().messages().list.return_value = mock_list

        # Mock get response
        mock_get = mock.MagicMock()
        mock_get.execute.return_value = {"id": "msg1", "payload": {}}
        mock_service.users().messages().get.return_value = mock_get

        auth = mock.MagicMock()
        auth.config = mock.MagicMock()
        auth.config.user_id = "me"
        auth.get_credentials.return_value = mock.MagicMock()

        client = GmailClient(auth)
        client._service = mock_service

        messages = client.list_messages(query="test", max_results=2)
        self.assertEqual(len(messages), 2)

    @mock.patch("google_workspace._HAVE_GOOGLE", True)
    def test_extract_body(self):
        auth = mock.MagicMock()
        auth.config = mock.MagicMock()
        auth.config.user_id = "me"
        client = GmailClient(auth)

        # Test multipart message
        payload = {
            "parts": [
                {"mimeType": "text/plain", "body": {"data": "SGVsbG8gV29ybGQ="}}  # "Hello World" base64
            ]
        }
        text = client._extract_body(payload)
        self.assertEqual(text, "Hello World")

        # Test nested multipart
        payload = {
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": "TmVzdGVk"}}  # "Nested"
                    ]
                }
            ]
        }
        text = client._extract_body(payload)
        self.assertEqual(text, "Nested")


class TestCalendarClient(unittest.TestCase):
    @mock.patch("google_workspace._HAVE_GOOGLE", True)
    @mock.patch("google_workspace.build")
    def test_list_events(self, mock_build):
        mock_service = mock.MagicMock()
        mock_build.return_value = mock_service

        mock_events = mock.MagicMock()
        mock_events.execute.return_value = {"items": [{"id": "evt1", "summary": "Meeting"}]}
        mock_service.events().list.return_value = mock_events

        auth = mock.MagicMock()
        auth.get_credentials.return_value = mock.MagicMock()

        client = CalendarClient(auth)
        client._service = mock_service

        events = client.list_events(max_results=10)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["summary"], "Meeting")


class TestDriveClient(unittest.TestCase):
    @mock.patch("google_workspace._HAVE_GOOGLE", True)
    @mock.patch("google_workspace.build")
    def test_list_files(self, mock_build):
        mock_service = mock.MagicMock()
        mock_build.return_value = mock_service

        mock_files = mock.MagicMock()
        mock_files.execute.return_value = {"files": [{"id": "file1", "name": "test.txt"}]}
        mock_service.files().list.return_value = mock_files

        auth = mock.MagicMock()
        auth.get_credentials.return_value = mock.MagicMock()

        client = DriveClient(auth)
        client._service = mock_service

        files = client.list_files(max_results=5)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["name"], "test.txt")


class TestDocsClient(unittest.TestCase):
    @mock.patch("google_workspace._HAVE_GOOGLE", True)
    @mock.patch("google_workspace.build")
    def test_extract_text(self, mock_build):
        mock_service = mock.MagicMock()
        mock_build.return_value = mock_service

        auth = mock.MagicMock()
        auth.get_credentials.return_value = mock.MagicMock()

        client = DocsClient(auth)
        client._service = mock_service

        # Test paragraph text extraction
        elements = [{
            "paragraph": {
                "elements": [
                    {"textRun": {"content": "Hello "}},
                    {"textRun": {"content": "World"}}
                ]
            }
        }]
        text = client._extract_text(elements)
        self.assertEqual(text, "Hello World")


class TestSheetsClient(unittest.TestCase):
    @mock.patch("google_workspace._HAVE_GOOGLE", True)
    @mock.patch("google_workspace.build")
    def test_read_range(self, mock_build):
        mock_service = mock.MagicMock()
        mock_build.return_value = mock_service

        mock_values = mock.MagicMock()
        mock_values.execute.return_value = {"values": [["A1", "B1"], ["A2", "B2"]]}
        mock_service.spreadsheets().values().get.return_value = mock_values

        auth = mock.MagicMock()
        auth.get_credentials.return_value = mock.MagicMock()

        client = SheetsClient(auth)
        client._service = mock_service

        values = client.read_range("spreadsheet_id", "A1:B2")
        self.assertEqual(values, [["A1", "B1"], ["A2", "B2"]])


class TestGoogleWorkspace(unittest.TestCase):
    @mock.patch("google_workspace._HAVE_GOOGLE", False)
    def test_missing_libs_raises(self):
        with self.assertRaises(RuntimeError) as cm:
            GoogleWorkspace()
        self.assertIn("not installed", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)