"""Where a flashable image comes from (#285): a release download, or a local run of the build pipeline."""
import hashlib
import io
import json
import tarfile
import time
import urllib.request
from pathlib import Path

REPO = "mralinp/zlt-x28-openwrt"
ARCHIVE = "x28-native-image.tar.gz"  # holds exactly manifest.json and rootfs-a-experimental.bin, the package_ubi output Flash reads
SUMS = "sha256sums"
FILES = ("manifest.json", "rootfs-a-experimental.bin")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def latest_release(fetch=get, repo=REPO):
    """The newest release that carries the image and its checksums, or None."""
    for rel in json.loads(fetch(f"https://api.github.com/repos/{repo}/releases")):
        urls = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
        if ARCHIVE in urls and SUMS in urls:
            return rel["tag_name"], urls
    return None


def download(dest_root, fetch=get, repo=REPO):
    """Fetch, verify and unpack the newest release image into dest_root/native-ubi-release-<tag>; returns that folder."""
    found = latest_release(fetch, repo)
    if not found:
        raise RuntimeError("no release carries a flashable image yet (#254)")
    tag, urls = found
    blob = fetch(urls[ARCHIVE])
    sums = {line.split()[-1]: line.split()[0] for line in fetch(urls[SUMS]).decode().splitlines() if line.strip()}
    if sums.get(ARCHIVE) != sha256(blob):
        raise ValueError(f"{ARCHIVE} does not match {SUMS} of release {tag}")
    out = dest_root / f"native-ubi-release-{tag}"
    if out.exists():
        raise FileExistsError(f"{out} already exists")
    with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
        # by name only: nothing in the archive picks a path
        data = {n: tar.extractfile(n).read() for n in FILES}
    manifest = json.loads(data["manifest.json"])
    if manifest.get("padded_sha256") != sha256(data["rootfs-a-experimental.bin"]):
        raise ValueError("image does not match its manifest")
    out.mkdir(parents=True)
    for name, content in data.items():
        (out / name).write_bytes(content)
    return out


def local_commands(inputs, work, out, repo, python="python3"):
    """The three build steps, in order. inputs: stock, modern, key (files), extra_ipks, kmods, feed (stage extras, kmods dir, feed ipks)."""
    stage, profile = work / "stage", work / "profile"
    return [
        [python, str(repo / "tools/build/stage_native.py"), "--stock", inputs["stock"], "--modern", inputs["modern"],
         "--ipk", *inputs["extra_ipks"], "--output", str(stage)],
        [python, str(repo / "tools/build/first_boot.py"), "--stage", str(stage), "--public-key", inputs["key"], "--stock", inputs["stock"],
         "--output", str(profile), "--kmods", inputs["kmods"], "--ipk", *inputs["feed"]],
        ["docker", "build", "-t", "x28-firmware-tools:ubi", "-f", str(repo / "tools/firmware/Dockerfile"), str(repo / "tools/firmware")],
        ["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
         "--tmpfs", "/tmp:rw,exec,size=768m", "-v", f"{repo / 'tools'}:/tools:ro", "-v", f"{profile}:/profile:ro",
         "-v", f"{out.parent}:/out", "x28-firmware-tools:ubi", "python3", "/tools/build/package_ubi.py", "--profile", "/profile",
         "--output", f"/out/{out.name}"],
    ]


def stamp():
    return time.strftime("%Y%m%d-%H%M%S")
