import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solace_assist.core.catalog import Catalog
from solace_assist.interfaces.cli import show_text


class GuideTests(unittest.TestCase):
    def setUp(self):
        Path("/tmp/opencode").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir="/tmp/opencode")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "catalog.sqlite3"

    def test_guides_have_examples_and_visible_provenance(self):
        catalog = Catalog(self.path)
        self.assertEqual(catalog.info()["guides"], 8)
        for tool_id in ("nmap", "tcpdump", "wireshark", "readelf", "smbclient", "binwalk", "gobuster", "rtl-sdr"):
            tool = catalog.show(tool_id)
            self.assertEqual(tool["documentation_status"], "source-checked")
            self.assertIn("```sh", tool["documentation"])
            self.assertTrue(tool["guide_provenance"]["sources"])
            self.assertIn("not runtime-validated", show_text(tool))
            json.dumps(tool)
        self.assertIn("nmap", [r["id"] for r in catalog.search("version-light")])

    def test_v1_migration_preserves_personal_and_imported_state(self):
        catalog = Catalog(self.path)
        catalog.favorite("nmap")
        catalog.note("nmap", "my unique observation")
        catalog.tag("nmap", "my-lab")
        catalog.show("nmap", record_view=True)
        catalog.import_packages([{"name": "sample-package", "description": "Imported record"}], "provided", "lab")
        catalog.replace_installed({"nmap": "test-version"})
        with catalog.connection() as db:
            db.execute("DROP TABLE guide_provenance")
            db.execute("DELETE FROM assist_meta WHERE key='content_revision'")
            db.execute("UPDATE tools SET documentation='',documentation_status='purpose-only' WHERE id='nmap'")
            db.execute("PRAGMA user_version=1")
        migrated = Catalog(self.path)
        tool = migrated.show("nmap")
        self.assertEqual(tool["note"], "my unique observation")
        self.assertEqual(tool["tags"], ["my-lab"])
        self.assertTrue(tool["favorite"])
        self.assertEqual(tool["installed_packages"][0]["version"], "test-version")
        self.assertEqual(migrated.info()["packages"], 1)
        self.assertEqual(migrated.show("sample-package")["origin"], "metadata")
        self.assertIn("nmap", [r["id"] for r in migrated.search("unique observation")])
        backup = self.path.parent / migrated.info()["migration_backup"]
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT body FROM notes").fetchone()[0], "my unique observation")
        with migrated.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM recent").fetchone()[0], 1)
        Catalog(self.path)
        self.assertEqual(len(list(self.path.parent.glob("*.bak"))), 1)

    def test_refresh_is_idempotent_and_preserves_notes(self):
        catalog = Catalog(self.path)
        catalog.note("nmap", "preserved note")
        with catalog.connection() as db:
            db.execute("DELETE FROM assist_meta WHERE key='content_revision'")
        refreshed = Catalog(self.path)
        self.assertEqual(refreshed.show("nmap")["note"], "preserved note")
        self.assertEqual(refreshed.info()["guides"], 8)
        with refreshed.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM tool_fts").fetchone()[0], 14)


if __name__ == "__main__":
    unittest.main()
