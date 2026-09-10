# 🗺️ Roadmap — ULTRON

> What's done, what's next, and what's possible.

---

## ✅ Done & Verified

### Core Platform
| Feature | Status | Details |
|---|---|---|
| Laptop brain | ✅ | Python agent loop (perceive → decide → act → verify) |
| Phone mini-brain | ✅ | Termux Python with qwen3.5:0.8b |
| Standalone APK | ✅ | Kotlin + llama.cpp, no Termux needed |
| Mesh linking | ✅ | mDNS discover + pair-code/QR + full state exchange |
| Self-healing | ✅ | Watchdog monitors brain + mic, auto-restart with backoff |

### Intelligence
| Feature | Status | Details |
|---|---|---|
| Multi-provider cloud | ✅ | Claude, GPT, DeepSeek, OpenRouter |
| Local Ollama | ✅ | qwen3.5:4b, qwen3.5:0.8b, smollm:135m |
| llama.cpp (APK) | ✅ | GGUF models: qwen3, gemma, llama, phi |
| Model download manager | ✅ | HuggingFace GGUF download with progress |
| Persistent memory | ✅ | SQLite + session context + semantic search |
| Proactive engine | ✅ | Calendar/email/system observation |

### Interface
| Feature | Status | Details |
|---|---|---|
| Orb HUD (laptop) | ✅ | Next.js + Three.js + MediaPipe gestures |
| Orb HUD (phone web) | ✅ | FastAPI + Three.js |
| Orb HUD (APK) | ✅ | Kotlin + audio-reactive animations |
| Voice activation | ✅ | Wake word "ultron" (offline Vosk) |
| Speech in/out | ✅ | Browser Web Speech + Vosk + Piper |
| Gesture recognition | ✅ | Pinch, zoom, palm, peace, thumbs-up, swipe |

### Integrations
| Feature | Status | Details |
|---|---|---|
| Google Workspace | ✅ | Gmail, Calendar, Drive, Docs, Sheets |
| Desktop automation | ✅ | Window management, app control, browser CDP |
| Screen perception | ✅ | OCR (Tesserator) + UiAutomator |
| Research mode | ✅ | DuckDuckGo + web fetch + citations |

### Safety
| Feature | Status | Details |
|---|---|---|
| Kill-switch | ✅ | File-based immediate stop |
| Step cap | ✅ | Max 200 steps per task |
| Destructive guards | ✅ | Confirmation for rm -rf, mkfs, dd, etc. |
| Audit log | ✅ | HMAC-SHA256 signed JSONL |
| File sandbox | ✅ | ULTRON_FS_ROOT restriction |
| SSRF protection | ✅ | Block private/loopback addresses |

### Tests
| Feature | Status | Details |
|---|---|---|
| Unit tests | ✅ | 44 tests passing |
| E2E tests | ✅ | Agent loop, mesh, WS links |
| Security tests | ✅ | Hardening regression tests |

---

## 🔜 Planned / Ideas

| Feature | Priority | Notes |
|---|---|---|
| Encrypted mesh pairing | High | TLS for laptop↔phone bridge |
| Plugin system | Medium | Custom tools without core changes |
| iOS orb | Medium | Capacitor cross-platform |
| Federated model sync | Low | Differential model updates |
| Smart home bridge | Low | MQTT/Home Assistant |
| Code execution sandbox | Low | Docker/WASM isolated env |

---

## 📊 Progress

```
Core Platform     ████████████████████ 100%
Intelligence      ████████████████████ 100%
Interface         ████████████████████ 100%
Integrations      ████████████████████ 100%
Safety            ████████████████████ 100%
Tests             ████████████████████ 100%
```

**Overall: 100% of v1.0 roadmap complete** ✅

---

## 🎯 v2.0 Vision

- **Fully encrypted mesh** — TLS 1.3 for all device communication
- **Plugin marketplace** — Community-contributed tools and integrations
- **Cross-platform** — Windows, macOS, Linux, Android, iOS
- **Advanced planning** — Multi-step task decomposition with dependencies
- **Federated learning** — Model improvements across devices

---

> Status: ✅ verified · 🟡 code-complete (needs hardware) · ⬜ not started