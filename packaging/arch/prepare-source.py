"""Prepare an exact, checksummed local source recipe. No makepkg/install/key access."""

import gzip
import hashlib
import io
from pathlib import Path
import re
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[2]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main():
    if git("status", "--porcelain").strip():
        raise ValueError("Commit/review source changes before preparing a package recipe")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if not re.fullmatch(r"[0-9][A-Za-z0-9.]*", version): raise ValueError("Unsupported package version")
    epoch = int(git("show", "-s", "--format=%ct", "HEAD"))
    output = ROOT / "dist/arch" / version
    if output.exists(): raise ValueError("Package output already exists; preserve/review it manually")
    archive = git("archive", "--format=tar", f"--prefix=solace-assist-{version}/", "HEAD")
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", filename="", mtime=epoch) as stream:
        stream.write(archive)
    data = compressed.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    output.mkdir(parents=True)
    (output / f"solace-assist-{version}.tar.gz").write_bytes(data)
    recipe = (ROOT / "packaging/arch/PKGBUILD.in").read_text().replace("@VERSION@", version).replace("@SHA256@", digest)
    (output / "PKGBUILD").write_text(recipe)
    (output / "SOURCE_COMMIT").write_bytes(git("rev-parse", "HEAD"))
    print(f"Prepared {output}; SHA256 {digest}")
    print("Development recipe only. Use an isolated Arch builder and explicit signing; public licensing is unresolved.")


if __name__ == "__main__":
    try: main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"ERROR: {error}")
