"""SQLite catalog and personal knowledge. No package-manager or network actions."""

from contextlib import contextmanager
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from urllib.parse import urlsplit


SCHEMA_VERSION = 2
NAME = re.compile(r"[A-Za-z0-9@][A-Za-z0-9@._+-]{0,127}\Z")
ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def text(value, limit=8192):
    """Do not let catalog strings emit terminal control sequences."""
    value = ANSI.sub("", str(value))
    return "".join(c for c in value if c in "\n\t" or ord(c) >= 32 and not 127 <= ord(c) <= 159)[:limit]


def default_database():
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "solace-assist/catalog.sqlite3"


def web_url(value):
    value = text(value, 2048).strip()
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username and not parsed.password else ""
    except ValueError:
        return ""


def search_expression(query):
    if len(query) > 512:
        raise ValueError("Search is limited to 512 characters")
    terms = re.findall(r"[^\W_]+", query, flags=re.UNICODE)[:32]
    # FTS operators, punctuation and quotes are data, not query language.
    return " AND ".join('"' + term.replace('"', '""') + '"*' for term in terms)


SCHEMA = """
CREATE TABLE IF NOT EXISTS assist_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tools(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, purpose TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
 documentation_url TEXT NOT NULL DEFAULT '', documentation TEXT NOT NULL DEFAULT '',
 documentation_status TEXT NOT NULL DEFAULT 'metadata-only', origin TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS categories(tool_id TEXT REFERENCES tools(id), category TEXT,
 PRIMARY KEY(tool_id,category));
CREATE TABLE IF NOT EXISTS keywords(tool_id TEXT REFERENCES tools(id), keyword TEXT,
 PRIMARY KEY(tool_id,keyword));
CREATE TABLE IF NOT EXISTS tool_packages(tool_id TEXT REFERENCES tools(id), package TEXT,
 PRIMARY KEY(tool_id,package));
CREATE TABLE IF NOT EXISTS tool_executables(tool_id TEXT REFERENCES tools(id), executable TEXT,
 PRIMARY KEY(tool_id,executable));
CREATE TABLE IF NOT EXISTS packages(
 source TEXT, repository TEXT, name TEXT, version TEXT, description TEXT,
 url TEXT, dependencies TEXT NOT NULL, groups_json TEXT NOT NULL,
 imported_at INTEGER NOT NULL, provenance TEXT NOT NULL,
 PRIMARY KEY(source,repository,name));
CREATE INDEX IF NOT EXISTS packages_name ON packages(name);
CREATE INDEX IF NOT EXISTS tool_packages_name ON tool_packages(package);
CREATE TABLE IF NOT EXISTS installed(package TEXT PRIMARY KEY, version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS package_executables(package TEXT, executable TEXT,
 PRIMARY KEY(package,executable));
CREATE TABLE IF NOT EXISTS favorites(tool_id TEXT PRIMARY KEY REFERENCES tools(id));
CREATE TABLE IF NOT EXISTS notes(tool_id TEXT PRIMARY KEY REFERENCES tools(id), body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tags(tool_id TEXT REFERENCES tools(id), tag TEXT,
 PRIMARY KEY(tool_id,tag));
CREATE TABLE IF NOT EXISTS recent(tool_id TEXT PRIMARY KEY REFERENCES tools(id), viewed_at INTEGER);
CREATE TABLE IF NOT EXISTS guide_provenance(
 tool_id TEXT PRIMARY KEY REFERENCES tools(id), revision TEXT NOT NULL,
 reviewed_on TEXT NOT NULL, scope TEXT NOT NULL, sources_json TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS tool_fts USING fts5(
 tool_id UNINDEXED, name, purpose, description, keywords, categories, documentation,
 tokenize='porter unicode61');
"""


class Catalog:
    def __init__(self, path=None, seed=True):
        self.path = Path(path) if path is not None else default_database()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.path.exists(): self.path.touch(mode=0o600)
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, SCHEMA_VERSION):
                raise ValueError("Unsupported catalog schema; preserve this database and upgrade Assist")
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and "assist_meta" not in tables:
                raise ValueError("This is not an Assist database; refusing to modify it")
            self.path.chmod(0o600)
            backup = self._backup_v1(db) if version == 1 else None
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)
            if seed:
                self._refresh_bundled(db)
            if backup:
                db.execute("INSERT OR REPLACE INTO assist_meta VALUES('migration_backup',?)", (backup.name,))
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def _backup_v1(self, db):
        # SQLite's backup API includes WAL contents; copying only the .sqlite file
        # would risk losing recent notes from an open explorer session.
        with tempfile.NamedTemporaryFile(prefix=self.path.name + ".pre-v2-", suffix=".bak", dir=self.path.parent, delete=False) as handle:
            path = Path(handle.name)
        try:
            target = sqlite3.connect(path)
            try: db.backup(target)
            finally: target.close()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path

    def _refresh_bundled(self, db):
        root = files("solace_assist").joinpath("data")
        seed_bytes = root.joinpath("catalog.json").read_bytes()
        index_bytes = root.joinpath("guides/index.json").read_bytes()
        data, index = json.loads(seed_bytes), json.loads(index_bytes)
        revision = hashlib.sha256(seed_bytes + b"\0" + index_bytes)
        guides = []
        for entry in index["guides"]:
            if not NAME.fullmatch(entry["tool_id"]) or not re.fullmatch(r"[a-z0-9-]+\.md", entry["file"]):
                raise ValueError("Invalid bundled guide identity")
            body = root.joinpath("guides", entry["file"]).read_bytes()
            if len(body) > 65536: raise ValueError("Bundled guide exceeds size limit")
            if not entry["sources"] or any(not web_url(url) for url in entry["sources"]):
                raise ValueError("Bundled guides require public web source references")
            revision.update(entry["file"].encode() + b"\0" + body)
            guides.append((entry, body.decode("utf-8")))
        digest = revision.hexdigest()
        previous = db.execute("SELECT value FROM assist_meta WHERE key='content_revision'").fetchone()
        if previous and previous[0] == digest: return
        for tool in data["tools"]:
            self._curated(db, tool)
        for entry, body in guides:
            tool_id = entry["tool_id"]
            if not db.execute("SELECT 1 FROM tools WHERE id=?", (tool_id,)).fetchone():
                raise ValueError("Guide references an unknown curated tool")
            db.execute("UPDATE tools SET documentation=?,documentation_status='source-checked',description=? WHERE id=?",
                       (text(body, 65536), text(entry["description"]), tool_id))
            db.execute("INSERT OR REPLACE INTO guide_provenance VALUES(?,?,?,?,?)",
                       (tool_id, hashlib.sha256(body.encode()).hexdigest(), entry["reviewed_on"], entry["scope"], json.dumps(entry["sources"])))
            self._index(db, tool_id)
        db.execute("INSERT OR REPLACE INTO assist_meta VALUES('bundled_seed',?)", (str(data["version"]),))
        db.execute("INSERT OR REPLACE INTO assist_meta VALUES('content_revision',?)", (digest,))

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _index(self, db, tool_id):
        tool = db.execute("SELECT rowid AS _rowid,* FROM tools WHERE id=?", (tool_id,)).fetchone()
        categories = " ".join(r[0] for r in db.execute("SELECT category FROM categories WHERE tool_id=?", (tool_id,)))
        words = " ".join(r[0] for r in db.execute("SELECT keyword FROM keywords WHERE tool_id=?", (tool_id,)))
        words += " " + " ".join(r[0] for r in db.execute("SELECT executable FROM tool_executables WHERE tool_id=?", (tool_id,)))
        words += " " + " ".join(r[0] for r in db.execute("SELECT pe.executable FROM package_executables pe JOIN tool_packages tp ON tp.package=pe.package WHERE tp.tool_id=?", (tool_id,)))
        words += " " + " ".join(r[0] for r in db.execute("SELECT tag FROM tags WHERE tool_id=?", (tool_id,)))
        note = db.execute("SELECT body FROM notes WHERE tool_id=?", (tool_id,)).fetchone()
        documentation = tool["documentation"] + (" " + note[0] if note else "")
        db.execute("DELETE FROM tool_fts WHERE rowid=?", (tool["_rowid"],))
        db.execute("INSERT INTO tool_fts(rowid,tool_id,name,purpose,description,keywords,categories,documentation) VALUES(?,?,?,?,?,?,?,?)",
                   (tool["_rowid"], tool_id, tool["name"], tool["purpose"], tool["description"], words, categories, documentation))

    def _curated(self, db, tool):
        tool_id = tool["id"]
        if not NAME.fullmatch(tool_id):
            raise ValueError("Invalid tool identifier")
        db.execute("INSERT INTO tools VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, purpose=excluded.purpose, description=excluded.description, url=excluded.url, documentation_url=excluded.documentation_url, documentation=excluded.documentation, documentation_status=excluded.documentation_status, origin=excluded.origin",
                   (tool_id, text(tool["name"]), text(tool["purpose"]), text(tool.get("description", "")),
                    web_url(tool.get("url", "")), web_url(tool.get("documentation_url", "")),
                    text(tool.get("documentation", ""), 65536), tool.get("documentation_status", "purpose-only"), "curated"))
        for table, column, values in [
            ("categories", "category", tool.get("categories", [])),
            ("keywords", "keyword", tool.get("keywords", [])),
            ("tool_packages", "package", tool.get("packages", [])),
            ("tool_executables", "executable", tool.get("executables", [])),
        ]:
            db.execute(f"DELETE FROM {table} WHERE tool_id=?", (tool_id,))
            db.executemany(f"INSERT INTO {table}(tool_id,{column}) VALUES(?,?)", [(tool_id, text(v)) for v in values])
        self._index(db, tool_id)

    def import_packages(self, records, source, repository, provenance="local Pacman cache; not independently reverified"):
        if not NAME.fullmatch(source) or not NAME.fullmatch(repository):
            raise ValueError("Invalid source/repository identifier")
        count = 0
        with self.connection() as db:
            db.execute("DELETE FROM packages WHERE source=? AND repository=?", (source, repository))
            for package in records:
                name = package["name"]
                if not NAME.fullmatch(name): raise ValueError("Invalid package name")
                groups = [text(g, 128) for g in package.get("groups", [])]
                description = text(package.get("description", ""))
                url = web_url(package.get("url", ""))
                db.execute("INSERT INTO packages VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (source, repository, name, text(package.get("version", "unknown")), description, url,
                            json.dumps([text(d) for d in package.get("dependencies", [])]), json.dumps(groups),
                            int(time.time()), provenance))
                existing = db.execute("SELECT origin FROM tools WHERE id=?", (name,)).fetchone()
                if not existing:
                    db.execute("INSERT INTO tools(id,name,purpose,description,url,origin) VALUES(?,?,?,?,?,?)",
                               (name, name, description or "Package metadata; purpose not curated", description, url, "metadata"))
                elif existing[0] == "metadata":
                    db.execute("UPDATE tools SET purpose=?,description=?,url=? WHERE id=?", (description, description, url, name))
                db.execute("INSERT OR IGNORE INTO tool_packages VALUES(?,?)", (name, name))
                if not existing or existing[0] == "metadata":
                    db.execute("DELETE FROM categories WHERE tool_id=?", (name,))
                    all_groups = [group for row in db.execute("SELECT groups_json FROM packages WHERE name=?", (name,)) for group in json.loads(row[0])]
                    categories = sorted({g.removeprefix("blackarch-") for g in all_groups if g != "blackarch"}) or ["uncategorized"]
                    db.executemany("INSERT OR IGNORE INTO categories VALUES(?,?)", [(name, category) for category in categories])
                self._index(db, name)
                count += 1
                if count > 100000: raise ValueError("Repository exceeds catalog import limit")
        return count

    def replace_installed(self, packages, executables=None):
        with self.connection() as db:
            affected = {r[0] for r in db.execute("SELECT DISTINCT tp.tool_id FROM tool_packages tp JOIN package_executables pe ON pe.package=tp.package")}
            db.execute("DELETE FROM installed")
            db.executemany("INSERT INTO installed VALUES(?,?)", [(n, v) for n, v in packages.items() if NAME.fullmatch(n)])
            if executables is not None:
                db.execute("DELETE FROM package_executables")
                db.executemany("INSERT OR IGNORE INTO package_executables VALUES(?,?)", executables)
            db.execute("DELETE FROM package_executables WHERE package NOT IN (SELECT package FROM installed)")
            affected.update(r[0] for r in db.execute("SELECT DISTINCT tp.tool_id FROM tool_packages tp JOIN installed i ON i.package=tp.package"))
            for tool_id in affected: self._index(db, tool_id)
            db.execute("INSERT OR REPLACE INTO assist_meta VALUES('installed_checked_at',?)", (str(int(time.time())),))

    def search(self, query="", category=None, installed=False, favorites=False, tag=None, limit=100):
        if not 1 <= limit <= 1000: raise ValueError("Result limit must be between 1 and 1000")
        expression = search_expression(query)
        conditions, args = [], []
        installed_sql = "EXISTS(SELECT 1 FROM tool_packages tp JOIN installed i ON i.package=tp.package WHERE tp.tool_id=t.id)"
        favorite_sql = "EXISTS(SELECT 1 FROM favorites f WHERE f.tool_id=t.id)"
        available_sql = "EXISTS(SELECT 1 FROM tool_packages tp JOIN packages p ON p.name=tp.package WHERE tp.tool_id=t.id)"
        join = " JOIN tool_fts ON tool_fts.rowid=t.rowid" if expression else ""
        if expression: conditions.append("tool_fts MATCH ?"); args.append(expression)
        if category: conditions.append("EXISTS(SELECT 1 FROM categories c WHERE c.tool_id=t.id AND c.category=?)"); args.append(category)
        if installed: conditions.append(installed_sql)
        if favorites: conditions.append(favorite_sql)
        if tag: conditions.append("EXISTS(SELECT 1 FROM tags g WHERE g.tool_id=t.id AND g.tag=?)"); args.append(tag.casefold())
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        order = "CASE WHEN t.origin='curated' THEN 0 ELSE 1 END,bm25(tool_fts,0,8,5,2,4,3,1),t.name" if expression else "favorite DESC,t.name"
        with self.connection() as db:
            rows = db.execute(f"SELECT t.id,t.name,t.purpose,t.documentation_status,t.origin,{installed_sql} AS installed,{available_sql} AS available,{favorite_sql} AS favorite FROM tools t{join}{where} ORDER BY {order} LIMIT ?", [*args, limit]).fetchall()
            return [dict(row) for row in rows]

    def categories(self):
        with self.connection() as db:
            return [(r[0], r[1]) for r in db.execute("SELECT category,count(*) FROM categories GROUP BY category ORDER BY category")]

    def show(self, tool_id, record_view=False):
        with self.connection() as db:
            row = db.execute("SELECT * FROM tools WHERE id=?", (tool_id,)).fetchone()
            if row is None: raise KeyError(f"Unknown tool: {tool_id}")
            result = dict(row)
            for table, column in [("categories", "category"), ("keywords", "keyword"), ("tool_packages", "package"), ("tool_executables", "executable"), ("tags", "tag")]:
                result[table] = [r[0] for r in db.execute(f"SELECT {column} FROM {table} WHERE tool_id=? ORDER BY {column}", (tool_id,))]
            names = result["tool_packages"]
            placeholders = ",".join("?" for _ in names) or "NULL"
            result["packages"] = [dict(r) for r in db.execute(f"SELECT * FROM packages WHERE name IN ({placeholders}) ORDER BY source,repository", names)]
            result["installed_packages"] = [dict(r) for r in db.execute(f"SELECT * FROM installed WHERE package IN ({placeholders})", names)]
            result["package_executables"] = [dict(r) for r in db.execute(f"SELECT * FROM package_executables WHERE package IN ({placeholders}) ORDER BY executable", names)]
            result["favorite"] = bool(db.execute("SELECT 1 FROM favorites WHERE tool_id=?", (tool_id,)).fetchone())
            guide = db.execute("SELECT * FROM guide_provenance WHERE tool_id=?", (tool_id,)).fetchone()
            result["guide_provenance"] = dict(guide) if guide else None
            if guide: result["guide_provenance"]["sources"] = json.loads(guide["sources_json"])
            note = db.execute("SELECT body FROM notes WHERE tool_id=?", (tool_id,)).fetchone()
            result["note"] = note[0] if note else ""
            if record_view: db.execute("INSERT OR REPLACE INTO recent VALUES(?,?)", (tool_id, int(time.time())))
            return result

    def favorite(self, tool_id, enabled=True):
        self.show(tool_id)
        with self.connection() as db:
            if enabled: db.execute("INSERT OR IGNORE INTO favorites VALUES(?)", (tool_id,))
            else: db.execute("DELETE FROM favorites WHERE tool_id=?", (tool_id,))

    def note(self, tool_id, body):
        self.show(tool_id)
        if len(body) > 262144: raise ValueError("Notes are limited to 256 KiB")
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO notes VALUES(?,?)", (tool_id, body))
            self._index(db, tool_id)

    def tag(self, tool_id, tag, remove=False):
        self.show(tool_id)
        tag = text(tag, 65).strip().casefold()
        if not tag or len(tag) > 64: raise ValueError("Tags must be 1–64 characters")
        with self.connection() as db:
            if remove: db.execute("DELETE FROM tags WHERE tool_id=? AND tag=?", (tool_id, tag))
            else: db.execute("INSERT OR IGNORE INTO tags VALUES(?,?)", (tool_id, tag))
            self._index(db, tool_id)

    def info(self):
        with self.connection() as db:
            return {"database": str(self.path), "schema": SCHEMA_VERSION,
                    "tools": db.execute("SELECT count(*) FROM tools").fetchone()[0],
                    "packages": db.execute("SELECT count(*) FROM packages").fetchone()[0],
                    "installed": db.execute("SELECT count(*) FROM installed").fetchone()[0],
                    "installed_checked_at": (dict(db.execute("SELECT key,value FROM assist_meta")) or {}).get("installed_checked_at"),
                    "guides": db.execute("SELECT count(*) FROM guide_provenance").fetchone()[0],
                    "migration_backup": (dict(db.execute("SELECT key,value FROM assist_meta")) or {}).get("migration_backup"),
                    "sources": [dict(r) for r in db.execute("SELECT source,repository,count(*) AS packages,max(imported_at) AS imported_at,provenance FROM packages GROUP BY source,repository,provenance")]}
