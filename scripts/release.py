"""Release helper used by CI. Standard library only (same rules as the maintainer's MQute).

    python3 scripts/release.py check-title "feat(build): attach rootfs to releases"
    python3 scripts/release.py next-version          # main: X.Y.Z
    python3 scripts/release.py next-version --pre    # develop: X.Y.Z-rc.N
    python3 scripts/release.py selftest

Versions follow SemVer and are derived from Conventional Commits since the
latest ``vX.Y.Z`` tag:

* ``type!:`` or a ``BREAKING CHANGE:`` footer -> major (minor while < 1.0)
* ``feat:``                                    -> minor
* anything else                                -> patch
* a ``Release-As: X.Y.Z`` footer                  -> exactly that version (e.g. 1.0.0)

The base is the newest stable-form tag (vX.Y.Z, any branch). develop publishes X.Y.Z-rc.N pre-releases
of the version main will get; main publishes X.Y.Z, stable from 1.0.0 (0.x stays a pre-release).
develop is merged into main with a merge commit, not squashed, so the tag's commit leads back into develop.
"""

from __future__ import annotations

import re
import subprocess
import sys

TYPES = ("feat", "fix", "perf", "refactor", "docs", "test", "build", "ci", "chore", "style", "revert")
TITLE = re.compile(rf"^(?P<type>{'|'.join(TYPES)})(\([\w./ -]+\))?(?P<breaking>!)?: \S.*$")
INITIAL_VERSION = "0.1.0"
PATCH, MINOR, MAJOR = 0, 1, 2


def is_conventional(title):
    return TITLE.match(title.strip()) is not None


def bump_for(message):
    subject, _, body = message.strip().partition("\n")
    match = TITLE.match(subject.strip())
    if (match and match["breaking"]) or re.search(r"^BREAKING[ -]CHANGE:", body, re.MULTILINE):
        return MAJOR
    if match and match["type"] == "feat":
        return MINOR
    return PATCH


def next_version(current, messages):
    if current is None:
        return INITIAL_VERSION
    major, minor, patch = (int(part) for part in current.split("."))
    bump = max((bump_for(m) for m in messages), default=PATCH)
    if bump == MAJOR and major == 0:
        bump = MINOR  # SemVer 0.x: breaking changes bump the minor version
    if bump == MAJOR:
        return f"{major + 1}.0.0"
    if bump == MINOR:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


RELEASE_AS = re.compile(r"^Release-As: *v?(\d+\.\d+\.\d+) *$", re.MULTILINE)
STABLE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
RC = re.compile(r"^v(\d+\.\d+\.\d+)-rc\.(\d+)$")


def key(version):
    return tuple(int(p) for p in version.split("."))


def release_version(current, messages):
    """next_version, unless a Release-As footer names a higher one."""
    asked = [m.group(1) for msg in messages for m in RELEASE_AS.finditer(msg)]
    if asked:
        want = max(asked, key=key)
        if current is None or key(want) > key(current):
            return want
    return next_version(current, messages)


def rc_number(base, tags):
    return 1 + max((int(m.group(2)) for t in tags if (m := RC.match(t)) and m.group(1) == base), default=0)


def _git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def tags():
    return _git("tag", "-l", "v*").split()


def latest_tag(all_tags):
    """The newest vX.Y.Z by version, from any branch: develop must see main's releases."""
    stable = [t for t in all_tags if STABLE.match(t)]
    return max(stable, key=lambda t: key(t[1:])) if stable else None


def commit_messages(since):
    revision = f"{since}..HEAD" if since else "HEAD"
    return [m for m in _git("log", "--format=%B%x00", revision).split("\x00") if m.strip()]


def selftest():
    assert is_conventional("feat(build): attach rootfs") and is_conventional("fix!: drop x")
    assert not is_conventional("Update README") and not is_conventional("feat:missing space")
    assert next_version(None, ["anything"]) == "0.1.0"
    assert next_version("0.1.0", ["fix(recovery): x", "docs: y"]) == "0.1.1"
    assert next_version("0.1.1", ["fix: a", "feat(build): b"]) == "0.2.0"
    assert next_version("0.2.0", ["feat!: break"]) == "0.3.0"  # minor while 0.x
    assert next_version("0.2.0", ["fix: a\n\nBREAKING CHANGE: b"]) == "0.3.0"
    assert next_version("1.4.2", ["refactor!: c"]) == "2.0.0"
    assert next_version("1.4.2", []) == "1.4.3"
    assert release_version("0.79.0", ["feat: x", "chore: go stable\n\nRelease-As: 1.0.0"]) == "1.0.0"
    assert release_version("1.2.0", ["fix: a\n\nRelease-As: 1.0.0"]) == "1.2.1"  # never backwards
    tags = ["v0.79.0", "v0.80.0-rc.1", "v0.80.0-rc.2", "v0.9.0", "v0.81.0-rc.7", "feed-2"]
    assert latest_tag(tags) == "v0.79.0" and rc_number("0.80.0", tags) == 3 and rc_number("0.82.0", tags) == 1
    print("release.py self-check OK")


def main(argv):
    if len(argv) == 2 and argv[0] == "check-title":
        if is_conventional(argv[1]):
            return 0
        print(f"PR title {argv[1]!r} is not a Conventional Commit, e.g. 'feat(build): attach rootfs to releases'.")
        print(f"Allowed types: {', '.join(TYPES)}. Add '!' after the type for breaking changes.")
        return 1
    if argv in (["next-version"], ["next-version", "--pre"]):
        all_tags = tags()
        tag = latest_tag(all_tags)
        version = release_version(tag[1:] if tag else None, commit_messages(tag))
        print(f"{version}-rc.{rc_number(version, all_tags)}" if argv[1:] else version)
        return 0
    if argv == ["selftest"]:
        selftest()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
