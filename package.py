#!/usr/bin/env python3
"""Package ULTRON-ULTRON build artifacts into /root/outbox for delivery.

Produces:
  outbox/ultron-laptop.zip      - laptop/core + laptop/hud
  outbox/ultron-phone.zip       - phone/agent + phone/web + bootstrap.sh
  outbox/ultron-orb-apk.zip     - phone/orb-apk (standalone Android app)
Run:  python3 package.py
"""
import os, shutil, zipfile, sys

ROOT = "/root/jarvis-ultron"
OUT = "/root/outbox"
os.makedirs(OUT, exist_ok=True)

def zipdir(src, name, exclude=(".git", "node_modules", "__pycache__")):
    zpath = os.path.join(OUT, name)
    if os.path.exists(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in exclude]
            for f in files:
                fp = os.path.join(root, f)
                z.write(fp, os.path.relpath(fp, src))
    print("wrote", zpath, f"{os.path.getsize(zpath)//1024} KB")

if __name__ == "__main__":
    zipdir(os.path.join(ROOT, "laptop"), "ultron-laptop.zip")
    zipdir(os.path.join(ROOT, "phone"), "ultron-phone.zip")
    zipdir(os.path.join(ROOT, "phone", "orb-apk"), "ultron-orb-apk.zip")
    # top-level docs
    for doc in ["README.md", "NOTES.md"]:
        sp = os.path.join(ROOT, doc)
        if os.path.exists(sp):
            shutil.copy(sp, os.path.join(OUT, doc))
    print("OUTBOX READY:", OUT)
    print(os.listdir(OUT))
