"""Persistent memory & context system for ULTRON JARVIS layer.

Provides:
- UserMemory: persistent personal facts, preferences, people, routines
- SessionContext: carries context across restarts
- SemanticMemory: vector-based knowledge retrieval (using sentence-transformers + FAISS)
- MemoryConsolidator: extracts structured facts from conversations
"""
from __future__ import annotations
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import hashlib


@dataclass
class Fact:
    """A single remembered fact about the user or world."""
    id: str
    category: str  # preference, person, routine, fact, goal, project
    key: str       # short key like "coffee", "mom", "standup_time"
    value: str     # human-readable value
    confidence: float = 1.0
    source: str = "conversation"  # conversation, explicit, inferred, import
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    tags: List[str] = field(default_factory=list)

    def touch(self):
        self.updated_at = datetime.now().isoformat()
        self.access_count += 1


@dataclass
class SessionSummary:
    """Summary of a conversation session for context carry-over."""
    session_id: str
    started_at: str
    ended_at: Optional[str] = None
    goals: List[str] = field(default_factory=list)
    key_facts_learned: List[str] = field(default_factory=list)
    decisions_made: List[str] = field(default_factory=list)
    pending_actions: List[str] = field(default_factory=list)
    mood: str = "neutral"
    summary: str = ""


class UserMemory:
    """SQLite-backed persistent memory for user facts."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.expanduser("~/ultron/memory.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'conversation',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    tags TEXT DEFAULT '[]',
                    UNIQUE(category, key)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    goals TEXT DEFAULT '[]',
                    key_facts_learned TEXT DEFAULT '[]',
                    decisions_made TEXT DEFAULT '[]',
                    pending_actions TEXT DEFAULT '[]',
                    mood TEXT DEFAULT 'neutral',
                    summary TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key)
            """)

    def _generate_id(self, category: str, key: str) -> str:
        return hashlib.md5(f"{category}:{key}".encode()).hexdigest()[:12]

    def set_fact(self, category: str, key: str, value: str,
                 confidence: float = 1.0, source: str = "explicit",
                 tags: Optional[List[str]] = None) -> Fact:
        """Store or update a fact."""
        fact_id = self._generate_id(category, key)
        now = datetime.now().isoformat()
        tags_json = json.dumps(tags or [])

        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT id FROM facts WHERE id = ?", (fact_id,))
            exists = cur.fetchone()

            if exists:
                conn.execute("""
                    UPDATE facts SET value=?, confidence=?, source=?, updated_at=?, tags=?
                    WHERE id=?
                """, (value, confidence, source, now, tags_json, fact_id))
            else:
                conn.execute("""
                    INSERT INTO facts (id, category, key, value, confidence, source, created_at, updated_at, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (fact_id, category, key, value, confidence, source, now, now, tags_json))

        return self.get_fact(category, key)

    def get_fact(self, category: str, key: str) -> Optional[Fact]:
        fact_id = self._generate_id(category, key)
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,))
            row = cur.fetchone()
            if not row:
                return None
            # touch access
            conn.execute("UPDATE facts SET access_count = access_count + 1 WHERE id = ?", (fact_id,))
            return self._row_to_fact(row)

    def get_facts(self, category: Optional[str] = None, limit: int = 100) -> List[Fact]:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            if category:
                cur = conn.execute("SELECT * FROM facts WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                                   (category, limit))
            else:
                cur = conn.execute("SELECT * FROM facts ORDER BY updated_at DESC LIMIT ?", (limit,))
            return [self._row_to_fact(r) for r in cur.fetchall()]

    def search_facts(self, query: str, limit: int = 20) -> List[Fact]:
        """Simple text search on key + value."""
        q = f"%{query.lower()}%"
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("""
                SELECT * FROM facts
                WHERE LOWER(key) LIKE ? OR LOWER(value) LIKE ?
                ORDER BY confidence DESC, access_count DESC
                LIMIT ?
            """, (q, q, limit))
            return [self._row_to_fact(r) for r in cur.fetchall()]

    def delete_fact(self, category: str, key: str) -> bool:
        fact_id = self._generate_id(category, key)
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
            return cur.rowcount > 0

    def _row_to_fact(self, row) -> Fact:
        return Fact(
            id=row[0], category=row[1], key=row[2], value=row[3],
            confidence=row[4], source=row[5], created_at=row[6],
            updated_at=row[7], access_count=row[8], tags=json.loads(row[9])
        )

    # --- Session context ---
    def save_session(self, summary: SessionSummary):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, started_at, ended_at, goals, key_facts_learned,
                 decisions_made, pending_actions, mood, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                summary.session_id, summary.started_at, summary.ended_at,
                json.dumps(summary.goals), json.dumps(summary.key_facts_learned),
                json.dumps(summary.decisions_made), json.dumps(summary.pending_actions),
                summary.mood, summary.summary
            ))

    def get_latest_session(self) -> Optional[SessionSummary]:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None
            return SessionSummary(
                session_id=row[0], started_at=row[1], ended_at=row[2],
                goals=json.loads(row[3] or "[]"),
                key_facts_learned=json.loads(row[4] or "[]"),
                decisions_made=json.loads(row[5] or "[]"),
                pending_actions=json.loads(row[6] or "[]"),
                mood=row[7], summary=row[8]
            )

    def get_sessions(self, limit: int = 10) -> List[SessionSummary]:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,))
            return [SessionSummary(
                session_id=r[0], started_at=r[1], ended_at=r[2],
                goals=json.loads(r[3] or "[]"),
                key_facts_learned=json.loads(r[4] or "[]"),
                decisions_made=json.loads(r[5] or "[]"),
                pending_actions=json.loads(r[6] or "[]"),
                mood=r[7], summary=r[8]
            ) for r in cur.fetchall()]


class SessionContext:
    """In-memory context for the current session, persisted on exit."""

    def __init__(self, memory: UserMemory):
        self.memory = memory
        self.session_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:12]
        self.started_at = datetime.now().isoformat()
        self.goals: List[str] = []
        self.key_facts_learned: List[str] = []
        self.decisions_made: List[str] = []
        self.pending_actions: List[str] = []
        self.mood = "neutral"
        self.current_topic: Optional[str] = None
        self.conversation_history: List[Dict[str, str]] = []  # {role, content}
        self._lock = threading.Lock()

    def add_exchange(self, role: str, content: str):
        with self._lock:
            self.conversation_history.append({"role": role, "content": content, "time": datetime.now().isoformat()})
            # Keep last 50 exchanges
            if len(self.conversation_history) > 50:
                self.conversation_history = self.conversation_history[-50:]

    def add_goal(self, goal: str):
        with self._lock:
            self.goals.append(goal)

    def add_fact_learned(self, fact: str):
        with self._lock:
            self.key_facts_learned.append(fact)

    def add_decision(self, decision: str):
        with self._lock:
            self.decisions_made.append(decision)

    def add_pending(self, action: str):
        with self._lock:
            self.pending_actions.append(action)

    def set_mood(self, mood: str):
        with self._lock:
            self.mood = mood

    def set_topic(self, topic: str):
        with self._lock:
            self.current_topic = topic

    def to_summary(self) -> SessionSummary:
        with self._lock:
            return SessionSummary(
                session_id=self.session_id,
                started_at=self.started_at,
                ended_at=datetime.now().isoformat(),
                goals=self.goals.copy(),
                key_facts_learned=self.key_facts_learned.copy(),
                decisions_made=self.decisions_made.copy(),
                pending_actions=self.pending_actions.copy(),
                mood=self.mood,
                summary=self._generate_summary()
            )

    def _generate_summary(self) -> str:
        parts = []
        if self.goals:
            parts.append(f"Goals: {'; '.join(self.goals[-3:])}")
        if self.key_facts_learned:
            parts.append(f"Learned: {'; '.join(self.key_facts_learned[-3:])}")
        if self.decisions_made:
            parts.append(f"Decided: {'; '.join(self.decisions_made[-3:])}")
        if self.pending_actions:
            parts.append(f"Pending: {'; '.join(self.pending_actions[-3:])}")
        return " | ".join(parts) if parts else "No significant activity."

    def persist(self):
        """Save session to persistent storage."""
        self.memory.save_session(self.to_summary())

    def get_context_for_prompt(self, max_chars: int = 2000) -> str:
        """Build a context string for LLM prompts."""
        parts = []
        s = self.to_summary()
        if s.summary:
            parts.append(f"[Session Summary] {s.summary}")
        if self.current_topic:
            parts.append(f"[Current Topic] {self.current_topic}")
        if self.pending_actions:
            parts.append(f"[Pending] {', '.join(self.pending_actions[-3:])}")
        # Recent conversation
        recent = self.conversation_history[-6:]
        if recent:
            parts.append("[Recent Conversation]")
            for ex in recent:
                parts.append(f"  {ex['role']}: {ex['content'][:200]}")
        ctx = "\n".join(parts)
        return ctx[:max_chars]


# --- Semantic Memory (Vector-based) ---
# Optional: requires sentence-transformers + faiss-cpu
# Falls back to text search if not available

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    import faiss
    _HAVE_SEMANTIC = True
except Exception:
    _HAVE_SEMANTIC = False
    np = None
    SentenceTransformer = None
    faiss = None


class SemanticMemory:
    """Vector-based semantic memory for knowledge retrieval."""

    def __init__(self, memory: UserMemory, model_name: str = "all-MiniLM-L6-v2"):
        self.memory = memory
        self.model_name = model_name
        self.model = None
        self.index = None
        self.fact_ids: List[str] = []
        self._initialized = False

        if _HAVE_SEMANTIC:
            self._init_model()

    def _init_model(self):
        try:
            self.model = SentenceTransformer(self.model_name)
            dim = self.model.get_sentence_embedding_dimension()
            self.index = faiss.IndexFlatIP(dim)  # Inner product = cosine with normalized vectors
            self._initialized = True
            self.rebuild_index()
        except Exception as e:
            print(f"Semantic memory init failed: {e}")
            self._initialized = False

    def rebuild_index(self):
        if not self._initialized:
            return
        facts = self.memory.get_facts(limit=1000)
        if not facts:
            return
        texts = [f"{f.category}: {f.key} - {f.value}" for f in facts]
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        self.index.reset()
        self.index.add(embeddings.astype(np.float32))
        self.fact_ids = [f.id for f in facts]

    def add_fact(self, fact: Fact):
        if not self._initialized:
            return
        text = f"{fact.category}: {fact.key} - {fact.value}"
        emb = self.model.encode([text], normalize_embeddings=True)
        self.index.add(emb.astype(np.float32))
        self.fact_ids.append(fact.id)

    def search(self, query: str, k: int = 5) -> List[Fact]:
        if not self._initialized or self.index.ntotal == 0:
            return self.memory.search_facts(query, limit=k)

        q_emb = self.model.encode([query], normalize_embeddings=True)
        scores, indices = self.index.search(q_emb.astype(np.float32), min(k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.fact_ids):
                fact = self.memory.get_fact_by_id(self.fact_ids[idx])
                if fact:
                    results.append(fact)
        return results


# Extend UserMemory with get_fact_by_id for semantic memory
def _get_fact_by_id(self, fact_id: str) -> Optional[Fact]:
    with self._lock, sqlite3.connect(self.db_path) as conn:
        cur = conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_fact(row)

UserMemory.get_fact_by_id = _get_fact_by_id


class MemoryConsolidator:
    """Extracts structured facts from conversation history."""

    def __init__(self, memory: UserMemory, llm_client=None):
        self.memory = memory
        self.llm = llm_client

    def consolidate_session(self, session: SessionContext) -> List[Fact]:
        """Extract facts from a session using LLM or heuristics."""
        if not session.conversation_history:
            return []

        # Simple heuristic extraction for now
        facts = []
        text = "\n".join(f"{e['role']}: {e['content']}" for e in session.conversation_history)

        # Extract preferences
        prefs = self._extract_preferences(text)
        for k, v in prefs.items():
            facts.append(self.memory.set_fact("preference", k, v, source="inferred"))

        # Extract people
        people = self._extract_people(text)
        for k, v in people.items():
            facts.append(self.memory.set_fact("person", k, v, source="inferred"))

        # Extract routines
        routines = self._extract_routines(text)
        for k, v in routines.items():
            facts.append(self.memory.set_fact("routine", k, v, source="inferred"))

        return facts

    def _extract_preferences(self, text: str) -> Dict[str, str]:
        prefs = {}
        # Simple pattern matching for preferences
        import re
        patterns = [
            r"(?:i (?:like|love|prefer|enjoy|hate|dislike) (?:to )?([^.!?\n]+))",
            r"(?:my favorite (\w+(?:\s+\w+){0,3}) is ([^.!?\n]+))",
            r"(?:i (?:usually|always|never) ([^.!?\n]+))",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                if len(m.groups()) == 1:
                    key = m.group(1).strip().lower().replace(" ", "_")[:50]
                    prefs[key] = m.group(1).strip()
                elif len(m.groups()) == 2:
                    key = m.group(1).strip().lower().replace(" ", "_")[:50]
                    prefs[key] = m.group(2).strip()
        return prefs

    def _extract_people(self, text: str) -> Dict[str, str]:
        people = {}
        import re
        patterns = [
            r"(?:my (\w+) (?:is|name is)\s+([^.!?\n]+))",
            r"(?:(\w+) is my (\w+))",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                if len(m.groups()) == 2:
                    rel = m.group(1).strip().lower()
                    name_part = m.group(2).strip()
                    # Handle "named X" or just "X"
                    words = name_part.split()
                    if words[0].lower() in ("named", "is", "called"):
                        name = words[1] if len(words) > 1 else words[0]
                    else:
                        name = words[0]
                    people[rel] = name
        return people

    def _extract_routines(self, text: str) -> Dict[str, str]:
        routines = {}
        import re
        patterns = [
            r"(?:i (?:usually|always) (\w+ at \d{1,2}(?::\d{2})?(?:\s*[ap]m)?))",
            r"(?:my (\w+) is at (\d{1,2}(?::\d{2})?(?:\s*[ap]m)?))",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                if len(m.groups()) == 1:
                    routines[m.group(1).strip().lower().replace(" ", "_")] = m.group(0)
                elif len(m.groups()) == 2:
                    routines[m.group(1).strip().lower().replace(" ", "_")] = m.group(2)
        return routines