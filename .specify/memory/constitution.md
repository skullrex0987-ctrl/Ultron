# ULTRON Constitution

## Core Principles

### I. ULTRON Identity
The product is ULTRON. User-facing text, APK labels, documentation, logs, and release notes must use ULTRON consistently; do not call it JARVIS.

### II. Standalone Android First
The Android APK must run without Termux. Native Android services own permissions, lifecycle, model storage, voice, notifications, and inference. Web UI enhancements may not be the only implementation of a required native capability.

### III. Test-First and Honest Verification
Every new behavior requires a regression test or a reproducible build check before completion. Never call a placeholder or stub production-ready. Report device-dependent verification separately from host/build verification.

### IV. Secure by Default
Permissions are explicit, cloud providers are opt-in/configurable, sensitive notifications are denied by default, secrets never enter source control, and destructive or remote actions require safety gates.

### V. One Source of Truth
Model state, voice state, and agent state must have one authoritative native owner. The ORB is a view of state, not a second controller with divergent behavior.

### VI. Release Integrity
A release APK must be built from the committed source, inspected for required classes/assets/permissions, checksum-verified, uploaded to a GitHub Release, and linked from the README.

## Quality Gates
- Python regression suite passes.
- Android Gradle build passes with Kotlin and native components compiled.
- APK contains the settings UI, native voice/model classes, permissions, and native inference library.
- GitHub main and release asset are verified by read-back.

## Governance
This constitution governs implementation and release decisions for ULTRON. A claim of completion requires tool-backed evidence. Amendments must be committed with the relevant specification or plan.

**Version**: 1.0.0 | **Ratified**: 2026-09-12 | **Last Amended**: 2026-09-12
