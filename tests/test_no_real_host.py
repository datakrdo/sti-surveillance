"""El host real de Neon no puede estar en el repo (se hará público); solo placeholders (ep-xxx...)."""
import re, subprocess, pathlib

ROOT = pathlib.Path(__file__).parent.parent
REAL = re.compile(r"ep-(?!x{3})[a-z0-9-]+\.[a-z0-9.-]*neon\.tech")


def test_detector():
    assert REAL.search("ep-" + "empty-poetry-123.c-7.us-east-2.aws" + ".neon.tech")
    assert not REAL.search("ep-xxx.neon.tech") and not REAL.search("ep-xxxxxxxx.region.aws.neon.tech")


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, check=True).stdout


def test_no_real_neon_host_in_repo():
    tracked = set(git("ls-files", "-z").decode().split("\0"))
    bad = []
    for p in filter(None, git("ls-files", "-co", "--exclude-standard", "-z").decode().split("\0")):
        if not (ROOT / p).is_file() and p not in tracked:
            continue
        try:  # lo versionado se lee del índice, para que un valor local (skip-worktree) no dé falsos positivos
            raw = git("show", f":{p}") if p in tracked else (ROOT / p).read_bytes()
        except subprocess.CalledProcessError:
            raw = (ROOT / p).read_bytes() if (ROOT / p).is_file() else b""
        if REAL.search(raw.decode("utf-8", "ignore")):
            bad.append(p)
    assert not bad, f"host real de Neon en: {bad}"
