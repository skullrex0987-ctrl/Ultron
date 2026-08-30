ULTRON-ULTRON BUILD LOG (SKULL-SWARM)
Sun Aug 30 18:21:34 UTC 2026 START scaffold
SPEC LOCKED (user, pre-sleep):
- Two apps: LAPTOP (Win/RTX5060) + PHONE (Termux/Poco X6 Pro, no root). Standalone, linkable.
- Q1 A full mesh | Q2 C laptop=qwen3.5:4b MAIN, phone=qwen3.5:0.8b MINI, linked=comm every connect, phone falls back to 0.8b if laptop down
- Q3 A phone=headless+small web UI orb+gesture | Q4 A+C ADB wireless + accessibility | Q5 A auto-discover+pair
- Q6 A floating widget tap=open/hold=talk/wake-word Vosk | Q7 A Vosk both Hin+Eng | Q8 B Piper phone / browser TTS laptop
- Q9 A+B+C perception: scrcpy+OCR, adb screenshot+OCR, UiAutomator | Q10 A+B local-first + cloud fallback toggle | Q11 C reply in input lang
- Q12 D deliver Telegram chat 1209979479 + prep GitHub (push later w/ access) | Q13 A auto-pull models | Q14 A+B+C pairing
- Q15 C wake-word toggle+mic always | Q16 A Python everywhere, Next.js HUD laptop | Q17/21 C full-auto + NO cap but ASK step count before each task
- Q18 A Telegram to user only | Q19 A full orb+gesture phone browser | Q20 A fork Ultron orb->ULTRON | Q22 A JSONL audit+transcript | Q23 A fallback
- Q24 A build both, test, package, Telegram. BOTH must do everything a Hermes agent can (shell/files/web/code/adb) on laptop AND phone.
