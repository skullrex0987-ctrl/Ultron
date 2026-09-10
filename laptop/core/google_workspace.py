"""Google Workspace integration for ULTRON (Gmail, Calendar, Drive, Docs, Sheets).

Uses the official google-api-python-client with OAuth2. Tokens are stored
locally and refreshed automatically. All methods are thread-safe.
"""
from __future__ import annotations
import os
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# Google API imports (install via: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib)
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    _HAVE_GOOGLE = True
except ImportError:
    _HAVE_GOOGLE = False
    Request = None
    Credentials = None
    InstalledAppFlow = None
    build = None
    HttpError = Exception

from config import CFG


# Scopes needed for implemented features
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


@dataclass
class GoogleConfig:
    """Configuration for Google Workspace integration."""
    credentials_file: str = field(default_factory=lambda: os.getenv(
        "ULTRON_GOOGLE_CREDS", os.path.expanduser("~/ultron/google_credentials.json")))
    token_file: str = field(default_factory=lambda: os.getenv(
        "ULTRON_GOOGLE_TOKEN", os.path.expanduser("~/ultron/google_token.json")))
    user_id: str = "me"  # Gmail user ID


class GoogleAuth:
    """Handles OAuth2 authentication for Google APIs."""

    def __init__(self, config: GoogleConfig = None):
        self.config = config or GoogleConfig()
        self._creds: Optional[Credentials] = None
        self._lock = threading.Lock()

    def get_credentials(self) -> Credentials:
        """Get valid credentials, refreshing or re-authenticating as needed."""
        with self._lock:
            if self._creds and self._creds.valid:
                return self._creds

            # Try to load existing token
            if os.path.exists(self.config.token_file):
                with open(self.config.token_file, "r") as f:
                    self._creds = Credentials.from_authorized_user_info(json.load(f))

            # Refresh if expired
            if self._creds and self._creds.expired and self._creds.refresh_token:
                try:
                    self._creds.refresh(Request())
                    self._save_credentials()
                    return self._creds
                except Exception:
                    self._creds = None

            # Full OAuth flow if needed
            if not self._creds or not self._creds.valid:
                if not os.path.exists(self.config.credentials_file):
                    raise FileNotFoundError(
                        f"Google credentials file not found: {self.config.credentials_file}. "
                        "Download from Google Cloud Console > APIs & Services > Credentials."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.config.credentials_file, SCOPES
                )
                self._creds = flow.run_local_server(port=0)
                self._save_credentials()

            return self._creds

    def _save_credentials(self):
        Path(self.config.token_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.config.token_file, "w") as f:
            json.dump(json.loads(self._creds.to_json()), f, indent=2)
        # Set restrictive permissions (owner read/write only)
        try:
            os.chmod(self.config.token_file, 0o600)
        except Exception:
            pass

    def revoke(self):
        """Revoke and delete stored credentials."""
        with self._lock:
            if self._creds:
                try:
                    self._creds.revoke(Request())
                except Exception:
                    pass
            self._creds = None
            if os.path.exists(self.config.token_file):
                os.remove(self.config.token_file)


class GmailClient:
    """Gmail API wrapper for common operations."""

    def __init__(self, auth: GoogleAuth):
        self.auth = auth
        self._service = None
        self._lock = threading.Lock()

    def _get_service(self):
        with self._lock:
            if self._service is None:
                creds = self.auth.get_credentials()
                self._service = build("gmail", "v1", credentials=creds)
            return self._service

    def list_messages(self, query: str = "", max_results: int = 20,
                      label_ids: List[str] = None) -> List[Dict]:
        """List messages matching query."""
        try:
            service = self._get_service()
            req = service.users().messages().list(
                userId=self.config.user_id, q=query, maxResults=max_results,
                labelIds=label_ids
            )
            resp = req.execute()
            messages = resp.get("messages", [])
            # Get full message details
            return [self.get_message(m["id"]) for m in messages]
        except HttpError as e:
            raise RuntimeError(f"Gmail list failed: {e}")

    def get_message(self, msg_id: str, format: str = "full") -> Dict:
        """Get full message by ID."""
        try:
            service = self._get_service()
            req = service.users().messages().get(
                userId=self.config.user_id, id=msg_id, format=format
            )
            return req.execute()
        except HttpError as e:
            raise RuntimeError(f"Gmail get failed: {e}")

    def get_message_text(self, msg_id: str) -> str:
        """Extract plain text body from message."""
        msg = self.get_message(msg_id)
        return self._extract_body(msg.get("payload", {}))

    def _extract_body(self, payload: Dict) -> str:
        """Recursively extract text body from message payload."""
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    import base64
                    data = part.get("body", {}).get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                elif part.get("mimeType", "").startswith("multipart/"):
                    result = self._extract_body(part)
                    if result:
                        return result
        elif payload.get("mimeType") == "text/plain":
            import base64
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        return ""

    def send_message(self, to: str, subject: str, body: str,
                     cc: List[str] = None, bcc: List[str] = None,
                     thread_id: str = None, in_reply_to: str = None) -> Dict:
        """Send an email."""
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        try:
            msg = MIMEMultipart()
            msg["to"] = to
            msg["subject"] = subject
            if cc:
                msg["cc"] = ", ".join(cc)
            if bcc:
                msg["bcc"] = ", ".join(bcc)
            if in_reply_to:
                msg["In-Reply-To"] = in_reply_to
                msg["References"] = in_reply_to

            msg.attach(MIMEText(body, "plain"))
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

            service = self._get_service()
            body = {"raw": raw}
            if thread_id:
                body["threadId"] = thread_id

            return service.users().messages().send(
                userId=self.config.user_id, body=body
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"Gmail send failed: {e}")

    def reply_to_message(self, msg_id: str, body: str) -> Dict:
        """Reply to an existing message."""
        orig = self.get_message(msg_id, format="metadata")
        headers = {h["name"].lower(): h["value"] for h in orig.get("payload", {}).get("headers", [])}
        
        to = headers.get("from", "")
        subject = headers.get("subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        thread_id = orig.get("threadId")
        in_reply_to = headers.get("message-id", "")

        return self.send_message(to, subject, body, thread_id=thread_id, in_reply_to=in_reply_to)

    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search messages with Gmail query syntax."""
        return self.list_messages(query=query, max_results=max_results)

    def list_labels(self) -> List[Dict]:
        """List all labels."""
        try:
            service = self._get_service()
            return service.users().labels().list(userId=self.config.user_id).execute().get("labels", [])
        except HttpError as e:
            raise RuntimeError(f"Gmail labels failed: {e}")

    def modify_labels(self, msg_id: str, add: List[str] = None, remove: List[str] = None) -> Dict:
        """Add/remove labels on a message."""
        try:
            service = self._get_service()
            body = {}
            if add:
                body["addLabelIds"] = add
            if remove:
                body["removeLabelIds"] = remove
            return service.users().messages().modify(
                userId=self.config.user_id, id=msg_id, body=body
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"Gmail modify failed: {e}")

    # Config property for internal use
    @property
    def config(self) -> GoogleConfig:
        return self.auth.config


class CalendarClient:
    """Google Calendar API wrapper."""

    def __init__(self, auth: GoogleAuth):
        self.auth = auth
        self._service = None
        self._lock = threading.Lock()

    def _get_service(self):
        with self._lock:
            if self._service is None:
                creds = self.auth.get_credentials()
                self._service = build("calendar", "v3", credentials=creds)
            return self._service

    def list_events(self, calendar_id: str = "primary",
                    time_min: datetime = None, time_max: datetime = None,
                    max_results: int = 50, single_events: bool = True,
                    order_by: str = "startTime") -> List[Dict]:
        """List events in a calendar."""
        try:
            service = self._get_service()
            now = time_min or datetime.utcnow().isoformat() + "Z"
            later = time_max or (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=now,
                timeMax=later,
                maxResults=max_results,
                singleEvents=single_events,
                orderBy=order_by
            ).execute()
            return events_result.get("items", [])
        except HttpError as e:
            raise RuntimeError(f"Calendar list failed: {e}")

    def get_event(self, event_id: str, calendar_id: str = "primary") -> Dict:
        """Get a specific event."""
        try:
            service = self._get_service()
            return service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        except HttpError as e:
            raise RuntimeError(f"Calendar get failed: {e}")

    def create_event(self, summary: str, start: datetime, end: datetime,
                     calendar_id: str = "primary", description: str = "",
                     location: str = "", attendees: List[str] = None,
                     reminders: List[Dict] = None) -> Dict:
        """Create a new event."""
        try:
            service = self._get_service()
            event = {
                "summary": summary,
                "description": description,
                "location": location,
                "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
            }
            if attendees:
                event["attendees"] = [{"email": a} for a in attendees]
            if reminders:
                event["reminders"] = {"useDefault": False, "overrides": reminders}
            else:
                event["reminders"] = {"useDefault": True}

            return service.events().insert(calendarId=calendar_id, body=event).execute()
        except HttpError as e:
            raise RuntimeError(f"Calendar create failed: {e}")

    def update_event(self, event_id: str, calendar_id: str = "primary",
                     **kwargs) -> Dict:
        """Update an existing event."""
        try:
            service = self._get_service()
            event = self.get_event(event_id, calendar_id)
            for k, v in kwargs.items():
                if k in ("summary", "description", "location"):
                    event[k] = v
                elif k == "start" and isinstance(v, datetime):
                    event["start"] = {"dateTime": v.isoformat(), "timeZone": "UTC"}
                elif k == "end" and isinstance(v, datetime):
                    event["end"] = {"dateTime": v.isoformat(), "timeZone": "UTC"}
                elif k == "attendees":
                    event["attendees"] = [{"email": a} for a in v]
            return service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
        except HttpError as e:
            raise RuntimeError(f"Calendar update failed: {e}")

    def delete_event(self, event_id: str, calendar_id: str = "primary",
                     send_updates: str = "all") -> None:
        """Delete an event."""
        try:
            service = self._get_service()
            service.events().delete(
                calendarId=calendar_id, eventId=event_id, sendUpdates=send_updates
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"Calendar delete failed: {e}")

    def list_calendars(self) -> List[Dict]:
        """List all accessible calendars."""
        try:
            service = self._get_service()
            return service.calendarList().list().execute().get("items", [])
        except HttpError as e:
            raise RuntimeError(f"Calendar list failed: {e}")


class DriveClient:
    """Google Drive API wrapper."""

    def __init__(self, auth: GoogleAuth):
        self.auth = auth
        self._service = None
        self._lock = threading.Lock()

    def _get_service(self):
        with self._lock:
            if self._service is None:
                creds = self.auth.get_credentials()
                self._service = build("drive", "v3", credentials=creds)
            return self._service

    def list_files(self, query: str = "", max_results: int = 50,
                   fields: str = "files(id,name,mimeType,modifiedTime,size,parents,webViewLink)") -> List[Dict]:
        """List files matching query."""
        try:
            service = self._get_service()
            results = service.files().list(
                q=query, pageSize=max_results, fields=fields
            ).execute()
            return results.get("files", [])
        except HttpError as e:
            raise RuntimeError(f"Drive list failed: {e}")

    def get_file(self, file_id: str, fields: str = "*") -> Dict:
        """Get file metadata."""
        try:
            service = self._get_service()
            return service.files().get(fileId=file_id, fields=fields).execute()
        except HttpError as e:
            raise RuntimeError(f"Drive get failed: {e}")

    def download_file(self, file_id: str) -> bytes:
        """Download file content."""
        try:
            service = self._get_service()
            return service.files().get_media(fileId=file_id).execute()
        except HttpError as e:
            raise RuntimeError(f"Drive download failed: {e}")

    def upload_file(self, name: str, content: bytes, mime_type: str = "application/octet-stream",
                    parents: List[str] = None) -> Dict:
        """Upload a new file."""
        try:
            from googleapiclient.http import MediaIoBaseUpload
            import io

            service = self._get_service()
            metadata = {"name": name}
            if parents:
                metadata["parents"] = parents

            media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=True)
            return service.files().create(body=metadata, media_body=media, fields="id,name,webViewLink").execute()
        except HttpError as e:
            raise RuntimeError(f"Drive upload failed: {e}")

    def create_folder(self, name: str, parents: List[str] = None) -> Dict:
        """Create a new folder."""
        return self.upload_file(name, b"", "application/vnd.google-apps.folder", parents)

    def share_file(self, file_id: str, email: str, role: str = "reader",
                   type: str = "user") -> Dict:
        """Share a file with a user."""
        try:
            service = self._get_service()
            permission = {"type": type, "role": role, "emailAddress": email}
            return service.permissions().create(fileId=file_id, body=permission, fields="id").execute()
        except HttpError as e:
            raise RuntimeError(f"Drive share failed: {e}")

    def search_files(self, query: str, max_results: int = 20) -> List[Dict]:
        """Search files by name/content."""
        return self.list_files(query=f"name contains '{query}' or fullText contains '{query}'", max_results=max_results)


class DocsClient:
    """Google Docs API wrapper."""

    def __init__(self, auth: GoogleAuth):
        self.auth = auth
        self._service = None
        self._lock = threading.Lock()

    def _get_service(self):
        with self._lock:
            if self._service is None:
                creds = self.auth.get_credentials()
                self._service = build("docs", "v1", credentials=creds)
            return self._service

    def get_document(self, document_id: str) -> Dict:
        """Get full document."""
        try:
            service = self._get_service()
            return service.documents().get(documentId=document_id).execute()
        except HttpError as e:
            raise RuntimeError(f"Docs get failed: {e}")

    def get_document_text(self, document_id: str) -> str:
        """Extract plain text from document."""
        doc = self.get_document(document_id)
        return self._extract_text(doc.get("body", {}).get("content", []))

    def _extract_text(self, elements: List[Dict]) -> str:
        text = []
        for elem in elements:
            if "paragraph" in elem:
                for pe in elem["paragraph"].get("elements", []):
                    if "textRun" in pe:
                        text.append(pe["textRun"].get("content", ""))
            elif "table" in elem:
                for row in elem["table"].get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        text.append(self._extract_text(cell.get("content", [])))
        return "".join(text)

    def create_document(self, title: str, content: str = "") -> Dict:
        """Create a new document."""
        try:
            service = self._get_service()
            doc = service.documents().create(body={"title": title}).execute()
            doc_id = doc.get("documentId")
            if content:
                self.append_text(doc_id, content)
            return doc
        except HttpError as e:
            raise RuntimeError(f"Docs create failed: {e}")

    def append_text(self, document_id: str, text: str) -> Dict:
        """Append text to end of document."""
        try:
            service = self._get_service()
            requests = [{
                "insertText": {
                    "location": {"index": 1},  # After title
                    "text": text
                }
            }]
            return service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
        except HttpError as e:
            raise RuntimeError(f"Docs append failed: {e}")

    def replace_text(self, document_id: str, search: str, replace: str) -> Dict:
        """Replace all occurrences of text."""
        try:
            service = self._get_service()
            requests = [{
                "replaceAllText": {
                    "containsText": {"text": search, "matchCase": True},
                    "replaceText": replace
                }
            }]
            return service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
        except HttpError as e:
            raise RuntimeError(f"Docs replace failed: {e}")


class SheetsClient:
    """Google Sheets API wrapper."""

    def __init__(self, auth: GoogleAuth):
        self.auth = auth
        self._service = None
        self._lock = threading.Lock()

    def _get_service(self):
        with self._lock:
            if self._service is None:
                creds = self.auth.get_credentials()
                self._service = build("sheets", "v4", credentials=creds)
            return self._service

    def get_spreadsheet(self, spreadsheet_id: str) -> Dict:
        """Get full spreadsheet metadata."""
        try:
            service = self._get_service()
            return service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        except HttpError as e:
            raise RuntimeError(f"Sheets get failed: {e}")

    def read_range(self, spreadsheet_id: str, range_a1: str) -> List[List[Any]]:
        """Read values from a range (A1 notation)."""
        try:
            service = self._get_service()
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id, range=range_a1
            ).execute()
            return result.get("values", [])
        except HttpError as e:
            raise RuntimeError(f"Sheets read failed: {e}")

    def write_range(self, spreadsheet_id: str, range_a1: str, values: List[List[Any]],
                    value_input_option: str = "USER_ENTERED") -> Dict:
        """Write values to a range."""
        try:
            service = self._get_service()
            body = {"values": values}
            return service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range=range_a1,
                valueInputOption=value_input_option, body=body
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"Sheets write failed: {e}")

    def append_rows(self, spreadsheet_id: str, range_a1: str, values: List[List[Any]],
                    value_input_option: str = "USER_ENTERED") -> Dict:
        """Append rows to a sheet."""
        try:
            service = self._get_service()
            body = {"values": values}
            return service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id, range=range_a1,
                valueInputOption=value_input_option, body=body
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"Sheets append failed: {e}")

    def create_spreadsheet(self, title: str, sheets: List[Dict] = None) -> Dict:
        """Create a new spreadsheet."""
        try:
            service = self._get_service()
            body = {"properties": {"title": title}}
            if sheets:
                body["sheets"] = sheets
            return service.spreadsheets().create(body=body).execute()
        except HttpError as e:
            raise RuntimeError(f"Sheets create failed: {e}")

    def clear_range(self, spreadsheet_id: str, range_a1: str) -> Dict:
        """Clear values in a range."""
        try:
            service = self._get_service()
            return service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id, range=range_a1, body={}
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"Sheets clear failed: {e}")


class GoogleWorkspace:
    """Unified Google Workspace client."""

    def __init__(self, config: GoogleConfig = None):
        if not _HAVE_GOOGLE:
            raise RuntimeError(
                "Google API libraries not installed. "
                "Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )
        self.auth = GoogleAuth(config)
        self.gmail = GmailClient(self.auth)
        self.calendar = CalendarClient(self.auth)
        self.drive = DriveClient(self.auth)
        self.docs = DocsClient(self.auth)
        self.sheets = SheetsClient(self.auth)

    def health_check(self) -> Dict[str, bool]:
        """Check connectivity to all services."""
        results = {}
        try:
            self.gmail.list_labels()
            results["gmail"] = True
        except Exception:
            results["gmail"] = False

        try:
            self.calendar.list_calendars()
            results["calendar"] = True
        except Exception:
            results["calendar"] = False

        try:
            self.drive.list_files(max_results=1)
            results["drive"] = True
        except Exception:
            results["drive"] = False

        try:
            self.docs.get_document("invalid")  # Will fail but auth works
        except HttpError as e:
            if e.resp.status == 404:
                results["docs"] = True  # Auth works, doc just not found
            else:
                results["docs"] = False
        except Exception:
            results["docs"] = False

        try:
            self.sheets.get_spreadsheet("invalid")
        except HttpError as e:
            if e.resp.status == 404:
                results["sheets"] = True
            else:
                results["sheets"] = False
        except Exception:
            results["sheets"] = False

        return results


# Convenience function
def get_workspace(config: GoogleConfig = None) -> GoogleWorkspace:
    """Get a GoogleWorkspace instance (singleton pattern)."""
    return GoogleWorkspace(config)


if __name__ == "__main__":
    # Quick health check
    ws = GoogleWorkspace()
    print("Health check:", ws.health_check())