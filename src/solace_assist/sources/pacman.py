"""Read local ALPM metadata, including BlackArch .db snapshots; never extract archives."""

from pathlib import Path, PurePosixPath
import subprocess
import tarfile


def _fields(content):
    result, current = {}, None
    for line in content.splitlines():
        if line.startswith("%") and line.endswith("%"):
            current = line.strip("%")
            result[current] = []
        elif line and current:
            result[current].append(line)
    return result


def read_repository(path):
    path = Path(path)
    if path.stat().st_size > 268435456: raise ValueError("Repository archive is too large")
    total = 0
    members = 0
    with tarfile.open(path, "r:*") as archive:
        for member in archive:
            members += 1
            if members > 400000: raise ValueError("Too many archive members")
            if member.size > 2097152: raise ValueError("Package metadata entry is too large")
            total += member.size
            if total > 134217728: raise ValueError("Repository metadata exceeds import limit")
            if PurePosixPath(member.name).name != "desc" or not member.isfile(): continue
            handle = archive.extractfile(member)
            if handle is None: continue
            data = _fields(handle.read(2097153).decode("utf-8", errors="replace"))
            def one(key, default=""):
                return data.get(key, [default])[0] if data.get(key) else default
            if not one("NAME"): raise ValueError("Package metadata is missing NAME")
            yield {"name": one("NAME"), "version": one("VERSION", "unknown"),
                   "description": one("DESC"), "url": one("URL"),
                   "groups": data.get("GROUPS", []), "dependencies": data.get("DEPENDS", [])}


def installed_snapshot(executables=True):
    """Fixed read-only queries, never -S/-Sy/-U/-R or downloaded executable help."""
    try:
        result = subprocess.run(["pacman", "-Q"], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return None, None
    if result.returncode: raise ValueError("Cannot read installed Pacman metadata")
    packages = {}
    for line in result.stdout.splitlines():
        fields = line.split(maxsplit=1)
        if len(fields) == 2: packages[fields[0]] = fields[1]
    files = None
    if executables:
        result = subprocess.run(["pacman", "-Ql"], capture_output=True, text=True, timeout=60)
        if result.returncode: raise ValueError("Cannot read installed file metadata")
        files = []
        for line in result.stdout.splitlines():
            fields = line.split(maxsplit=1)
            if len(fields) != 2: continue
            package, location = fields
            if location.startswith(("/usr/bin/", "/usr/sbin/")) and not location.endswith("/"):
                files.append((package, Path(location).name))
    return packages, files


def sync_local(catalog, directory=Path("/var/lib/pacman/sync"), refresh_installed=True, executables=True):
    counts = {}
    for path in sorted(Path(directory).glob("*.db")):
        counts[path.stem] = catalog.import_packages(read_repository(path), "pacman-cache", path.stem)
    if refresh_installed:
        packages, files = installed_snapshot(executables)
        if packages is not None:
            catalog.replace_installed(packages, files)
            counts["installed"] = len(packages)
    return counts
