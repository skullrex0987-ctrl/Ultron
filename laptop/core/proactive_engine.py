"""Proactive assistant engine - continuous observation and context-aware suggestions.

Monitors calendar, email, system state and provides suggestions without user prompting.
Follows SHIELD "fail closed" and SKULL "architecture-first" principles.
"""
from __future__ import annotations
import os
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from config import CFG
from google_workspace import GoogleWorkspace, GoogleAuth, GmailClient, CalendarClient
from memory import UserMemory, SessionContext, Fact, SessionSummary
from desktop_automation import DesktopAutomation, WindowManager, AppController

# Observation intervals (in seconds)
CALENDAR_CHECK_INTERVAL = 300  # 5 minutes
EMAIL_CHECK_INTERVAL = 600  # 10 minutes
SYSTEM_HEALTH_INTERVAL = 60  # 1 minute
PROACTIVE_SUGGESTION_INTERVAL = 120  # 2 minutes


@dataclass
class ObservationResult:
    """Result from a single observation cycle."""
    type: str  # "calendar", "email", "system", "suggestion"
    timestamp: str
    data: dict
    actionable: bool
    suggested_action: Optional[dict] = None


@dataclass
class ProactiveSchedule:
    """Upcoming schedule events for proactive behavior."""
    events: List[dict] = field(default_factory=list)
    next_event: Optional[dict] = None
    time_until_next: Optional[timedelta] = None


class ProactiveEngine:
    """Core proactive assistant engine."""

    def __init__(self, memory: UserMemory, google_ws: GoogleWorkspace = None,
                 desktop: DesktopAutomation = None):
        self.memory = memory
        self.google_ws = google_ws or GoogleWorkspace()
        self.desktop = desktop or DesktopAutomation()
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

        # Observers registered
        self.observers: List[str] = []

        # Scheduled tasks
        self._scheduled_tasks: Dict[str, float] = {}

        # Context for suggestions
        self.current_context: dict = {"time_of_day": "unknown", "day_of_week": "unknown"}

        # Initialize memory tracking
        self._init_context()

    def _init_context(self):
        """Initialize or restore context from persistent memory."""
        # Load last known context
        latest = self.memory.get_latest_session()
        if latest and latest.mood:
            self.current_context["last_mood"] = latest.mood
        if latest and latest.summary:
            # Extract context hints from summary
            self._extract_context_from_summary(latest.summary)

    def _extract_context_from_summary(self, summary: str):
        """Extract contextual hints from session summary."""
        s = summary.lower()
        if "morning" in s or "good morning" in s:
            self.current_context["typical_time"] = "morning"
        if "evening" in s or "good evening" in s:
            self.current_context["typical_time"] = "evening"
        if "meeting" in s:
            self.current_context["has_meetings"] = True

    def start(self):
        """Start the proactive engine background thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            self._log("proactive", {"event": "started"})

    def stop(self):
        """Stop the proactive engine."""
        with self._lock:
            self._running = False
            if self._thread:
                self._thread.join(timeout=5)
            self._log("proactive", {"event": "stopped"})

    def _log(self, side: str, data: dict):
        """Log to audit system."""
        try:
            from audit import log as audit_log
            audit_log(side, data)
        except Exception:
            pass

    def _run_loop(self):
        """Main observation loop running in background thread."""
        calendar_interval = self._schedule_observer("calendar", CALENDAR_CHECK_INTERVAL)
        email_interval = self._schedule_observer("email", EMAIL_CHECK_INTERVAL)
        system_interval = self._schedule_observer("system", SYSTEM_HEALTH_INTERVAL)
        suggestion_interval = self._schedule_observer("suggestion", PROACTIVE_SUGGESTION_INTERVAL)

        try:
            while self._running:
                time.sleep(1)
        except Exception as e:
            self._log("proactive", {"event": "loop-error", "err": str(e)})
        finally:
            # Intervals are just numbers; actual tasks are asyncio tasks
            pass

    def _schedule_observer(self, obs_type: str, interval: int):
        """Schedule an observation task."""

        import asyncio

        async def observer():
            while self._running:
                try:
                    await asyncio.sleep(interval)
                    if not self._running:
                        break
                    result = await self._observe(obs_type)
                    self._handle_observation_result(result)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._log("proactive", {"event": "observer-error", "type": obs_type, "err": str(e)})

        asyncio.create_task(observer())
        return interval

    async def _observe(self, obs_type: str) -> ObservationResult:
        """Perform a single observation of the given type."""
        now = datetime.now()

        if obs_type == "calendar":
            return await self._observe_calendar(now)
        elif obs_type == "email":
            return await self._observe_email(now)
        elif obs_type == "system":
            return await self._observe_system(now)
        elif obs_type == "suggestion":
            return await self._generate_suggestion(now)
        else:
            return ObservationResult(type=obs_type, timestamp=now.isoformat(),
                                     data={}, actionable=False)

    async def _observe_calendar(self, now: datetime) -> ObservationResult:
        """Observe calendar for upcoming events."""
        try:
            events = self.google_ws.calendar.list_events(
                max_results=5, time_min=now, time_max=now + timedelta(days=1)
            )

            if not events:
                return ObservationResult(
                    type="calendar", timestamp=now.isoformat(),
                    data={"upcoming": []}, actionable=False
                )

            # Find the next event
            next_event = None
            for evt in events:
                if evt.get("start"):
                    start_str = evt["start"].get("dateTime", evt["start"].get("date", ""))
                    try:
                        start_time = datetime.fromisoformat(
                            start_str.replace("Z", "+00:00")
                        )
                        if start_time > now:
                            if next_event is None or start_time < next_event["start_time"]:
                                next_event = {
                                    "title": evt.get("summary", "Untitled"),
                                    "start": start_time,
                                    "duration": evt.get("duration", {}).get(
                                        "dateMinutes", 60
                                    ),
                                    "attendees": len(evt.get("attendees", [])),
                                    "location": evt.get("location", ""),
                                }
                    except Exception:
                        pass

            return ObservationResult(
                type="calendar",
                timestamp=now.isoformat(),
                data={
                    "upcoming": [e.get("summary", "") for e in events[:3]],
                    "next_event": next_event,
                },
                actionable=next_event is not None,
                suggested_action=self._calendar_suggested_action(next_event)
                if next_event
                else None
            )
        except Exception as e:
            self._log("proactive", {"event": "calendar-observation-error", "err": str(e)})
            return ObservationResult(
                type="calendar", timestamp=now.isoformat(),
                data={"error": str(e)}, actionable=False
            )

    async def _observe_email(self, now: datetime) -> ObservationResult:
        """Observe email for important messages."""
        try:
            # Get recent emails (last 24h, unread)
            emails = self.google_ws.gmail.list_messages(
                query="is:unread newer_than:1d", max_results=5
            )

            if not emails:
                return ObservationResult(
                    type="email", timestamp=now.isoformat(),
                    data={"unread_count": 0, "important": []}, actionable=False
                )

            # Filter for potentially important emails
            important = []
            for email in emails[:5]:
                # Check for common important patterns
                subject = email.get("subject", "").lower()
                body = email.get("body", "").lower()[:200]

                importance_score = 0
                if any(kw in subject for kw in ["urgent", "asap", "important", "action required"]):
                    importance_score += 3
                if any(kw in subject for kw in ["meeting", "deadline", "follow-up"]):
                    importance_score += 2
                if any(kw in body for kw in ["urgent", "asap", "important"]):
                    importance_score += 2

                if importance_score >= 3:
                    important.append({
                        "subject": email.get("subject", ""),
                        "preview": email.get("preview", "")[:150],
                        "time": email.get("time", ""),
                    })

            return ObservationResult(
                type="email",
                timestamp=now.isoformat(),
                data={"unread_count": len(emails), "important": important},
                actionable=len(important) > 0,
                suggested_action=self._email_suggested_action(important[0])
                if important
                else None
            )
        except Exception as e:
            self._log("proactive", {"event": "email-observation-error", "err": str(e)})
            return ObservationResult(
                type="email", timestamp=now.isoformat(),
                data={"error": str(e)}, actionable=False
            )

    async def _observe_system(self, now: datetime) -> ObservationResult:
        """Observe system health and state."""
        try:
            # Check Ollama availability
            from ollama_client import BrainClient
            brain = BrainClient()
            brain_healthy = brain.health()

            # Check memory state
            mem_healthy = self.memory.get_latest_session() is not None

            # Check wake word availability
            voice_healthy = False
            try:
                from stt_tts import VoiceListener
                voice_healthy = True
            except Exception:
                voice_healthy = False

            return ObservationResult(
                type="system",
                timestamp=now.isoformat(),
                data={
                    "brain_healthy": brain_healthy,
                    "memory_persistent": mem_healthy,
                    "voice_available": voice_healthy,
                },
                actionable=not brain_healthy,
                suggested_action=self._system_suggested_action(not brain_healthy)
                if not brain_healthy
                else None
            )
        except Exception as e:
            self._log("proactive", {"event": "system-observation-error", "err": str(e)})
            return ObservationResult(
                type="system", timestamp=now.isoformat(),
                data={"error": str(e)}, actionable=False
            )

    async def _generate_suggestion(self, now: datetime) -> ObservationResult:
        """Generate proactive suggestions based on context."""
        suggestions = []

        # Time-based suggestions
        hour = now.hour
        minute = now.minute

        # Morning routine (7-9 AM)
        if 7 <= hour <= 9 and minute % 30 == 0:
            suggestions.append({
                "type": "routine",
                "text": "Good morning! Your calendar shows:",
                "data": {"calendar_items": self._get_todays_calendar()},
            })

        # Lunch time (12-1 PM)
        if 12 <= hour <= 13 and minute % 30 == 0:
            suggestions.append({
                "type": "routine",
                "text": "Lunchtime! Anything on your calendar?",
                "data": {"prompt": "lunch_question"},
            })

        # End of work day (5-6 PM)
        if 17 <= hour <= 18 and minute % 30 == 0:
            suggestions.append({
                "type": "routine",
                "text": "Almost end of work day. Last calendar event:",
                "data": {"last_event": self._get_last_calendar_event()},
            })

        # Meeting reminders (check if starting in 15 min)
        if self._is_soon_to_meet(now):
            suggestions.append({
                "type": "reminder",
                "text": "Meeting starting in 15 minutes:",
                "data": {"meeting_prep": self._meeting_prep(now)},
            })

        if not suggestions:
            return ObservationResult(
                type="suggestion", timestamp=now.isoformat(),
                data={"suggestions": []}, actionable=False
            )

        # Return the most relevant suggestion
        primary = suggestions[0]
        return ObservationResult(
            type="suggestion",
            timestamp=now.isoformat(),
            data={"suggestions": suggestions},
            actionable=True,
            suggested_action=self._build_suggestion_action(primary)
        )

    def _is_soon_to_meet(self, now: datetime) -> bool:
        """Check if a meeting starts within 15 minutes."""
        try:
            events = self.google_ws.calendar.list_events(
                max_results=3, time_min=now,
                time_max=now + timedelta(minutes=30)
            )
            for evt in events:
                start = evt.get("start", {}).get("dateTime", "")
                if start:
                    start_time = datetime.fromisoformat(
                        start.replace("Z", "+00:00")
                    )
                    delta = (start_time - now).total_seconds()
                    if 0 < delta < 900:  # Within 15 minutes
                        return True
            return False
        except Exception:
            return False

    def _get_todays_calendar(self) -> List[str]:
        """Get today's calendar events."""
        try:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            events = self.google_ws.calendar.list_events(
                time_min=today_start, time_max=today_end, max_results=20
            )
            return [e.get("summary", "") for e in events]
        except Exception:
            return []

    def _get_last_calendar_event(self) -> Optional[dict]:
        """Get the most recent calendar event."""
        try:
            events = self.google_ws.calendar.list_events(
                max_results=10, order_by="startTime"
            )
            if events:
                last = events[-1]
                start = last.get("start", {}).get("dateTime", "")
                if start:
                    return {"title": last.get("summary", ""), "start": start}
        except Exception:
            pass
        return None

    def _meeting_prep(self, now: datetime) -> dict:
        """Prepare meeting summary and suggestions."""
        try:
            events = self.google_ws.calendar.list_events(
                max_results=1, time_min=now,
                time_max=now + timedelta(hours=2)
            )
            if not events:
                return {"status": "no_meeting"}

            meeting = events[0]
            title = meeting.get("summary", "")
            start = meeting.get("start", {}).get("dateTime", "")
            location = meeting.get("location", "")

            attendees = meeting.get("attendees", [])
            attendee_emails = [a.get("email", "") for a in attendees]

            email_context = []
            for email_addr in attendee_emails[:3]:
                try:
                    emails = self.google_ws.gmail.list_messages(
                        query=f"from:{email_addr}", max_results=1
                    )
                    if emails:
                        email_context.append({
                            "from": email_addr,
                            "preview": emails[0].get("preview", "")[:100],
                        })
                except Exception:
                    pass

            return {
                "title": title,
                "start": start,
                "location": location,
                "attendees": attendee_emails,
                "email_context": email_context,
                "suggested_agenda": self._generate_meeting_agenda(meeting),
            }
        except Exception as e:
            return {"status": "error", "err": str(e)}

    def _generate_meeting_agenda(self, meeting: dict) -> List[str]:
        """Generate suggested meeting agenda."""
        agenda = []
        title = meeting.get("summary", "").lower()

        if "standup" in title:
            agenda = [
                "What did you do yesterday?",
                "What are you doing today?",
                "Any blockers?"
            ]
        if "project" in title or "discussion" in title:
            agenda = [
                "Project update",
                "Key discussion points",
                "Decisions needed",
                "Action items"
            ]
        if "review" in title:
            agenda = [
                "Review of previous items",
                "Current status",
                "Future direction",
                "Next steps"
            ]
        if not agenda:
            agenda = [
                "Opening", "Discussion items", "Decisions",
                "Action items", "Closing"
            ]

        return agenda

    def _calendar_suggested_action(self, event: Optional[dict]) -> Optional[dict]:
        """Generate suggested action for calendar event."""
        if not event:
            return None
        return {
            "type": "prepare_for_meeting",
            "title": event["title"],
            "start": event["start"].isoformat() if hasattr(event["start"], "isoformat") else str(event["start"]),
            "estimated_duration": event.get("duration", 60),
        }

    def _email_suggested_action(self, email: dict) -> Optional[dict]:
        """Generate suggested action for important email."""
        if not email:
            return None
        return {
            "type": "read_and_respond",
            "subject": email["subject"],
            "preview": email["preview"],
            "suggested_response": self._draft_response_preview(email),
        }

    def _system_suggested_action(self, brain_unhealthy: bool) -> Optional[dict]:
        """Generate suggested action for system issues."""
        if brain_unhealthy:
            return {
                "type": "restart_brain",
                "message": "Brain appears unhealthy, attempting restart",
            }
        return None

    def _build_suggestion_action(self, suggestion: dict) -> dict:
        """Build actionable item from a suggestion."""
        return {
            "type": suggestion.get("type", "inform"),
            "content": suggestion.get("text", ""),
            "data": suggestion.get("data", {}),
        }

    def _handle_observation_result(self, result: ObservationResult):
        """Handle an observation result - trigger actions if actionable."""
        with self._lock:
            if not result.actionable:
                self._log("proactive", {"event": "observation", "type": result.type,
                                          "actionable": False})
                return

            r = result.data
            r_type = result.type

            if r_type == "calendar" and r.get("next_event"):
                self._trigger_proactive_action("calendar_prep", r["next_event"])
            elif r_type == "email" and r.get("important"):
                self._trigger_proactive_action("email_flag", r["important"][0])
            elif r_type == "system" and r.get("brain_healthy") is False:
                self._trigger_proactive_action("system_recovery", {})
            elif r_type == "suggestion" and r.get("suggestions"):
                self._trigger_proactive_action("suggestion_present", r["suggestions"][0])
            elif r_type == "system":
                self._log("proactive", {"event": "system_health", "data": r.data})

    def _trigger_proactive_action(self, action_type: str, data: dict):
        """Trigger a proactive action."""
        self._log("proactive", {"event": "trigger", "action": action_type, "data": data})
        self.memory.set_fact("proactive", action_type, json.dumps(data),
                             source="proactive_engine", confidence=0.8)

    # --- Public API for HUD integration ---

    def get_current_context(self) -> dict:
        """Get current context for HUD or agent use."""
        with self._lock:
            return dict(self.current_context)

    def add_observation(self, obs_type: str, data: dict,
                        actionable: bool = False,
                        suggested_action: dict = None):
        """Manually add an observation result."""
        with self._lock:
            from datetime import datetime
            result = ObservationResult(
                type=obs_type,
                timestamp=datetime.now().isoformat(),
                data=data,
                actionable=actionable,
                suggested_action=suggested_action
            )
            self._handle_observation_result(result)

    def set_context_hint(self, key: str, value: any):
        """Set a context hint from outside."""
        with self._lock:
            self.current_context[key] = value

    def get_suggested_actions(self) -> List[dict]:
        """Get all currently actionable suggestions."""
        with self._lock:
            facts = self.memory.search_facts("proactive", limit=5)
            actions = []
            for fact in facts:
                try:
                    data = json.loads(fact.value)
                    actions.append({"type": fact.key, "data": data,
                                    "confidence": fact.confidence})
                except Exception:
                    pass
            return actions


def get_proactive_engine(memory: UserMemory = None,
                         google_ws: GoogleWorkspace = None,
                         desktop: DesktopAutomation = None) -> ProactiveEngine:
    """Get a ProactiveEngine instance."""
    return ProactiveEngine(memory or UserMemory(),
                         google_ws or GoogleWorkspace(),
                         desktop or DesktopAutomation())