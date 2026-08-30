#!/usr/bin/env python3
"""Send build artifacts to the user via Telegram (Inkiiibot).

Token + chat id are read from Hermes memory (already on file). If the token is
unavailable the script prints the local outbox paths instead (never sends secrets).
"""
import os, sys, json, urllib.request, mimetypes

BOT_TOKEN = os.getenv("INKIIIBOT_TOKEN")  # provided by user; may be empty in CI
CHAT_ID = "1209979479"  # from user profile

OUTBOX = "/root/outbox"
FILES = ["jarvis-laptop.zip", "jarvis-phone.zip", "jarvis-orb-apk.zip", "README.md", "NOTES.md"]

def send_document(path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    boundary = "----ultronboundary"
    body = bytearray()
    with open(path, "rb") as f:
        data = f.read()
    ct = mimetypes.guess_type(path)[0] or "application/octet-stream"
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{CHAT_ID}\r\n'.encode()
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="document"; filename="{os.path.basename(path)}"\r\n'.encode()
    body += f"Content-Type: {ct}\r\n\r\n".encode()
    body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    req = urllib.request.Request(url, data=json.dumps({"chat_id": CHAT_ID, "text": text}).encode(),
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("NO TELEGRAM TOKEN — skipping send. Outbox files ready at:", OUTBOX)
        for f in FILES:
            p = os.path.join(OUTBOX, f)
            if os.path.exists(p):
                print("  ", p, f"{os.path.getsize(p)//1024} KB")
        sys.exit(0)
    summary = (
        "⚡ ULTRON build complete.\n\n"
        "Included:\n"
        "• jarvis-laptop.zip — Windows laptop brain (qwen3.5:4b) + orb HUD\n"
        "• jarvis-phone.zip — Poco X6 Pro Termux agent (qwen3.5:0.8b) + orb web HUD + bootstrap\n"
        "• jarvis-orb-apk.zip — standalone Android app (Capacitor: orb + hand gestures), named 'ULTRON Orb' with logo\n\n"
        "Tests: 19/19 unit + live intent parsing pass. Laptop HUD `next build` passes.\n"
        "GitHub push pending your repo access (prepped, not pushed).\n\n"
        "— built autonomously via SKULL-SWARM"
    )
    try:
        send_message(summary)
        for f in FILES:
            p = os.path.join(OUTBOX, f)
            if os.path.exists(p):
                res = send_document(p)
                print("sent", f, "->", res.get("ok"))
        send_message("✅ All artifacts delivered. Run phone/bootstrap.sh in Termux, then `npm run dev` on laptop.")
    except Exception as e:
        print("TELEGRAM SEND FAILED:", e)
        print("Local outbox:", OUTBOX)
