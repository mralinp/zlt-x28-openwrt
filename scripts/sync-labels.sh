#!/bin/sh
# Create/update the repo labels from .github/labels.yml (needs gh auth). Usage: scripts/sync-labels.sh [owner/repo]
set -eu
REPO=${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}
HERE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 -I - "$REPO" "$HERE/.github/labels.yml" <<'PY'
import re, subprocess, sys
repo, path = sys.argv[1:3]
for line in open(path):
    m = re.match(r'- \{name: (.+?), color: (\w+), description: "(.*)"\}', line.strip())
    if not m: continue
    n, c, d = m.groups()
    subprocess.run(["gh", "label", "create", n, "--repo", repo, "--color", c, "--description", d, "--force"], check=True)
PY
