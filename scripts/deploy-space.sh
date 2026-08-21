#!/usr/bin/env bash
#
# Publishes the agent runtime to a Hugging Face Space.
#
# The Space is a separate git remote, not a subdirectory of this repo, so this
# assembles a clean tree containing exactly what the image needs -- Dockerfile,
# Space README, and apps/agent -- and force-pushes it. Nothing else from the
# monorepo reaches the Space: no web app, no docs, no training venv.
#
# The token is read from the environment and never echoed, never written to the
# assembled tree, and never committed. It is passed to git through a credential
# helper on stdin rather than embedded in the remote URL, so it cannot leak into
# .git/config or the process list.
#
#   HF_TOKEN=... ./scripts/deploy-space.sh <hf-username> [space-name]

set -euo pipefail

USER_NAME="${1:-}"
SPACE_NAME="${2:-sandscope-agent}"

if [[ -z "$USER_NAME" ]]; then
  echo "usage: HF_TOKEN=... $0 <hf-username> [space-name]" >&2
  exit 2
fi
if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "error: HF_TOKEN is not set." >&2
  echo "Create one at https://huggingface.co/settings/tokens with 'write' scope." >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> assembling Space tree"
mkdir -p "$STAGE/apps"
cp "$ROOT/deploy/space/Dockerfile" "$STAGE/Dockerfile"
cp "$ROOT/deploy/space/README.md"  "$STAGE/README.md"

# Copy only git-tracked agent files. Using the index rather than the working
# directory is what keeps .venv-train (2GB+ of torch, and the transformers
# advisories) out of a public Space -- a plain `cp -r` would ship all of it.
git -C "$ROOT" archive HEAD apps/agent | tar -x -C "$STAGE"

cat > "$STAGE/.gitattributes" <<'ATTR'
*.onnx filter=lfs diff=lfs merge=lfs -text
ATTR

# Refuse to publish if a secret made it into the staged tree.
if grep -rIlE '(sk-[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|postgres(ql)?://[^ ]*:[^ ]*@)' "$STAGE" 2>/dev/null | grep -v '\.gitattributes$'; then
  echo "error: possible secret in the staged tree (listed above). Refusing to publish." >&2
  exit 1
fi
echo "    secret scan clean"

SIZE="$(du -sh "$STAGE" | cut -f1)"
echo "    staged $SIZE"

echo "==> publishing to https://huggingface.co/spaces/$USER_NAME/$SPACE_NAME"
cd "$STAGE"
git init -q
git lfs install --local >/dev/null 2>&1 || true
git lfs track "*.onnx" >/dev/null 2>&1 || true
git add -A
git -c user.email=deploy@sandscope -c user.name=sandscope-deploy \
    commit -q -m "Deploy agent runtime from $(git -C "$ROOT" rev-parse --short HEAD)"

git remote add space "https://huggingface.co/spaces/$USER_NAME/$SPACE_NAME"
printf 'protocol=https\nhost=huggingface.co\nusername=%s\npassword=%s\n\n' \
  "$USER_NAME" "$HF_TOKEN" | git credential approve 2>/dev/null || true

git -c credential.helper='!f(){ echo "username='"$USER_NAME"'"; echo "password=$HF_TOKEN"; };f' \
    push -q --force space HEAD:main

echo "==> done"
echo "    Space:  https://huggingface.co/spaces/$USER_NAME/$SPACE_NAME"
echo "    API:    https://$USER_NAME-$SPACE_NAME.hf.space"
echo
echo "Set these as Space secrets (Settings -> Variables and secrets) before it will serve:"
echo "  DATABASE_URL  AGENT_SERVICE_TOKEN  GROQ_API_KEY  GEMINI_API_KEY"
echo "  UPSTASH_REDIS_REST_URL  UPSTASH_REDIS_REST_TOKEN"
echo "  UPSTASH_VECTOR_REST_URL  UPSTASH_VECTOR_REST_TOKEN  RUN_BUDGET_USD"
