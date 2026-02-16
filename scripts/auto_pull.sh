#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/espresso/project/archive"
LOG_FILE="${HOME}/.local/state/repo-autopull.log"

mkdir -p "$(dirname "$LOG_FILE")"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { printf '[%s] %s\n' "$(ts)" "$*" >> "$LOG_FILE"; }

if [[ ! -d "$REPO_DIR/.git" ]]; then
  log "skip: git repo not found at $REPO_DIR"
  exit 0
fi

cd "$REPO_DIR"

# Skip if working tree is not clean so local edits are never overwritten.
if [[ -n "$(git status --porcelain)" ]]; then
  log "skip: working tree is dirty"
  exit 0
fi

# Pick upstream if configured; otherwise default to nchy/main.
upstream="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
if [[ -n "$upstream" ]]; then
  remote="${upstream%%/*}"
  branch="${upstream#*/}"
else
  remote="nchy"
  branch="main"
fi

if ! git remote get-url "$remote" >/dev/null 2>&1; then
  log "skip: remote '$remote' not found"
  exit 0
fi

if ! git fetch --quiet "$remote" "$branch"; then
  log "error: fetch failed for $remote/$branch (auth/network issue likely)"
  exit 0
fi

ahead_behind="$(git rev-list --left-right --count HEAD..."$remote/$branch" 2>/dev/null || echo "0 0")"
ahead="${ahead_behind%% *}"
behind="${ahead_behind##* }"

if [[ "$behind" == "0" ]]; then
  log "ok: already up to date ($remote/$branch)"
  exit 0
fi

if [[ "$ahead" != "0" && "$behind" != "0" ]]; then
  log "skip: branch diverged (ahead=$ahead behind=$behind)"
  exit 0
fi

if [[ "$ahead" != "0" && "$behind" == "0" ]]; then
  log "skip: local branch ahead by $ahead commit(s)"
  exit 0
fi

if git pull --ff-only --quiet "$remote" "$branch"; then
  log "updated: fast-forwarded to $remote/$branch"
else
  log "error: ff-only pull failed"
fi
