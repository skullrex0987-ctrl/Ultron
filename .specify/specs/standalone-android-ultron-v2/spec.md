# ULTRON Standalone Android APK v2 Specification

## Purpose

Produce one independently installable ULTRON Android APK containing the ORB interface, gesture input, permissions, native voice lifecycle, model management, local GGUF inference, optional cloud routing, notification reading, and laptop/phone mesh connectivity. Termux must not be required for the APK's core capabilities.

## User Stories

### US1 — First launch
As a user, I install ULTRON, see the ORB, and receive clear runtime permission prompts for camera, microphone, notifications, and any optional accessibility/notification features.

### US2 — Gestures
As a user, I tap **GESTURES**, grant camera permission, and use pinch, open-palm, peace, thumbs-up, swipe, and two-hand zoom gestures. The ORB visibly reacts and actions are dispatched safely.

### US3 — Model management
As a user, I open **⚙ SETTINGS**, see storage usage and available models, download a GGUF model with progress/resume/error state, load it, switch models, unload it, and delete it.

### US4 — Local inference
As a user, I can chat with a downloaded GGUF model without Termux or Ollama. The app exposes an actual native llama.cpp inference path and reports load/inference failures clearly.

### US5 — Cloud fallback
As a user, I can configure OpenRouter, Anthropic, OpenAI, or DeepSeek credentials in settings. Cloud use is explicit and secrets are stored only in protected Android storage.

### US6 — Always-on voice
As a user, I can enable an Android foreground microphone service, choose a wake phrase, say “ultron,” speak a command, and receive the command in the app/agent even when the screen is off, subject to Android battery and permission policy.

### US7 — TTS and replay
As a user, I can enable speech responses. Markdown is stripped before TTS, speech can be interrupted, and the last response can be replayed without another LLM call.

### US8 — Notification reading
As a user, I can explicitly enable notification reading, choose allowed apps, and hear messages read aloud. Banking, payment, password, SMS, and OTP content remains blocked by default.

### US9 — Mesh
As a user, I can pair the APK with the laptop/phone ULTRON agent using an authenticated transport and send/receive goals, state, transcripts, and replies.

### US10 — Release
As a maintainer, I can reproduce the APK build, run verification checks, upload the APK to a GitHub Release, and find the exact download link in the README.

## Functional Requirements

- FR1: The APK must use a native Android launcher activity and compile Kotlin sources.
- FR2: The APK must declare and request CAMERA, RECORD_AUDIO, INTERNET, notification, and foreground microphone permissions as applicable to the Android API level.
- FR3: Permission denial must degrade gracefully and explain the disabled capability.
- FR4: The settings button must be visible without relying on an undiscoverable edge control.
- FR5: Model downloads must use an app-owned model directory, temporary partial files, progress callbacks, cancellation, retry, and integrity/size validation.
- FR6: Model state must distinguish unavailable, downloading, downloaded, loading, loaded, unloading, failed, and deleted.
- FR7: Only one large local model may be loaded at a time unless device capability explicitly supports more.
- FR8: Native inference must expose create, load, unload, infer, stop, and destroy lifecycle methods.
- FR9: JNI/native build failures must fail the release build; a stub must never silently masquerade as local inference in a release APK.
- FR10: The ORB UI must consume native state callbacks and preserve the existing visual and gesture language.
- FR11: Always-on voice must run only after explicit opt-in and display an ongoing foreground notification.
- FR12: Notification reader must default off, support an allowlist, and apply a sensitive-content denylist.
- FR13: Voice and notification services must stop cleanly and release microphone/TTS resources.
- FR14: Cloud keys must never be logged, bundled, or placed in Git.
- FR15: Mesh transport must require pairing/authentication and enforce frame/rate limits.

## Non-Functional Requirements

- NFR1: No ANR during model downloads, model load, inference, or TTS.
- NFR2: UI must remain responsive while native inference runs off the main thread.
- NFR3: APK must support arm64-v8a; x86_64 is optional for emulator testing.
- NFR4: Build verification must inspect the APK for native libraries, Kotlin classes, permissions, settings assets, and model-management bridge.
- NFR5: Documentation must clearly distinguish host verification from physical-device verification.

## Acceptance Criteria

- AC1: Clean Gradle build creates a debug APK from committed sources.
- AC2: APK inspection finds `MainActivity`, `ModelManager`, `ModelBridge`, `VoiceWakeService`, `MessageReaderService`, `TtsEngine`, `libultron-inference.so`, settings UI, and declared permissions.
- AC3: Python regression suite passes with no failures/errors.
- AC4: Android unit/build checks cover model states, URL validation, sensitive notification filtering, markdown stripping, and wake-word command parsing.
- AC5: Release APK is uploaded to GitHub Release and README points to the verified asset URL.
- AC6: Any physical-device limitation is explicitly reported rather than claimed as tested.
