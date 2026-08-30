#!/usr/bin/env bash
# GitHub prep: commit everything locally and stage a remote. PUSH is NOT done here
# (awaiting user's repo access). After the user provides the repo, run:
#   git remote add origin <url> && git push -u origin main
set -e
cd /root/jarvis-ultron
git config user.email "ultron@local.build" 2>/dev/null || true
git config user.name "ULTRON Build" 2>/dev/null || true
# remove cloned upstream orb .git to avoid nested repo confusion
rm -rf hud/.git 2>/dev/null || true
git add -A
git commit -q -m "ULTRON: laptop+phone mesh, premium orbs, offline brains, orb APK, tests" || echo "nothing to commit"
echo "=== committed locally ==="
git log --oneline -3 2>/dev/null
echo ""
echo "READY TO PUSH — provide a GitHub repo URL, then:"
echo "  git remote add origin <url>"
echo "  git push -u origin main"
