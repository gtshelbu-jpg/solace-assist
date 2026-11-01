import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solace_assist.core.catalog import Catalog, search_expression, text, web_url
from solace_assist.sources.pacman import installed_snapshot, read_repository


def archive(path, entries):
    with tarfile.open(path, "w:gz") as output:
        for name, body in entries:
            data = body.encode()
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            output.addfile(entry, io.BytesIO(data))


class CatalogTests(unittest.TestCase):
    def setUp(self):
        Path("/tmp/opencode").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="assist-tests-", dir="/tmp/opencode")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "catalog.sqlite3"
        self.catalog = Catalog(self.db)

    def test_task_oriented_offline_seed(self):
        for query, expected in [("enumerate smb", "smbmap"), ("analyze firmware", "binwalk"),
                                ("inspect ELF binary", "readelf"), ("discover subdomains", "subfinder"),
                                ("decode radio signals", "rtl-sdr"), ("analyze pcap", "wireshark"),
                                ("capture wireless packets", "aircrack-ng")]:
            with self.subTest(query=query):
                self.assertIn(expected, [r["id"] for r in self.catalog.search(query)])
        self.assertEqual(self.catalog.info()["packages"], 0)

    def test_category_and_installed_filters(self):
        self.catalog.replace_installed({"binutils": "1", "nmap": "2"})
        installed = {r["id"] for r in self.catalog.search(installed=True)}
        self.assertIn("readelf", installed)
        self.assertIn("nmap", installed)
        self.assertNotIn("binwalk", installed)
        self.assertTrue(all(r["id"] in {"smbclient", "smbmap"} for r in self.catalog.search(category="smb")))

    def test_private_database_permissions(self):
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o600)

    def test_notes_favorites_and_tags_survive_catalog_and_installed_refresh(self):
        self.catalog.favorite("nmap")
        self.catalog.note("nmap", "Useful in my bluewidgetlab")
        self.catalog.tag("nmap", "Lab Work")
        self.catalog.import_packages([{"name":"nmap","version":"9","description":"unreviewed metadata"}], "provided", "blackarch")
        self.catalog.replace_installed({"nmap":"8"})
        self.catalog = Catalog(self.db)
        item = self.catalog.show("nmap")
        self.assertTrue(item["favorite"])
        self.assertEqual(item["note"], "Useful in my bluewidgetlab")
        self.assertEqual(item["tags"], ["lab work"])
        self.assertEqual(item["origin"], "curated")
        self.assertIn("nmap", [r["id"] for r in self.catalog.search("bluewidgetlab")])
        self.assertEqual(self.catalog.search(favorites=True, tag="lab work")[0]["id"], "nmap")
        self.assertNotEqual(item["purpose"], "unreviewed metadata")

    def test_multiple_repositories_versions_and_executables(self):
        for repo, version in [("extra", "1"), ("blackarch", "2")]:
            self.catalog.import_packages([{"name":"nmap","version":version}], "provided", repo)
        self.catalog.replace_installed({"nmap":"0"}, [("nmap","nmap"),("nmap","nping")])
        tool = self.catalog.show("nmap")
        self.assertEqual(len(tool["packages"]), 2)
        self.assertEqual(len(tool["package_executables"]), 2)
        self.assertEqual(tool["installed_packages"][0]["version"], "0")
        self.assertNotIn("unverified example", tool["documentation"])
        self.assertIn("nmap", [r["id"] for r in self.catalog.search("nping")])
        self.assertIn("wireshark", [r["id"] for r in self.catalog.search("tshark")])

    def test_repository_refresh_keeps_cross_source_categories(self):
        self.catalog.import_packages([{"name":"metadata-tool","groups":["blackarch-firmware"]}], "provided", "blackarch")
        self.catalog.import_packages([{"name":"metadata-tool","groups":[]}], "pacman-cache", "extra")
        self.assertEqual(self.catalog.show("metadata-tool")["categories"], ["firmware"])

    def test_curated_task_matches_precede_incomplete_metadata(self):
        self.catalog.import_packages([{"name":"analyze-firmware-package","description":"Analyze firmware"}], "provided", "blackarch")
        self.assertEqual(self.catalog.search("analyze firmware")[0]["id"], "binwalk")

    def test_blackarch_archive_groups_and_dependencies(self):
        path = self.root / "blackarch.db"
        archive(path, [("example-1/desc", "%NAME%\nexample\n\n%VERSION%\n1-1\n\n%DESC%\nFirmware research tool\n\n%GROUPS%\nblackarch\nblackarch-firmware\nblackarch-reversing\n\n%DEPENDS%\npython\nlibfoo>=1\n\n%URL%\nhttps://example.invalid\n")])
        count = self.catalog.import_packages(read_repository(path), "provided", "blackarch")
        self.assertEqual(count, 1)
        item = self.catalog.show("example")
        self.assertEqual(item["categories"], ["firmware", "reversing"])
        self.assertEqual(json.loads(item["packages"][0]["dependencies"]), ["python", "libfoo>=1"])
        self.assertEqual(item["documentation_status"], "metadata-only")
        self.assertEqual(item["tool_executables"], [])

    def test_archive_paths_are_never_extracted(self):
        path = self.root / "malicious.db"
        archive(path, [("../../escaped-file", "oops"), ("../../desc", "%NAME%\nread-only-record\n")])
        self.catalog.import_packages(read_repository(path), "provided", "test")
        self.assertFalse((self.root.parent / "escaped-file").exists())
        self.assertEqual(self.catalog.show("read-only-record")["id"], "read-only-record")

    def test_bad_import_rolls_back_metadata(self):
        self.catalog.import_packages([{"name":"stable","version":"1"}], "provided", "test")
        with self.assertRaises(ValueError):
            self.catalog.import_packages([{"name":"temporary"},{"name":"--overwrite"}], "provided", "test")
        self.assertEqual(self.catalog.show("stable")["packages"][0]["version"], "1")
        with self.assertRaises(KeyError): self.catalog.show("temporary")

    def test_large_archive_members_are_rejected(self):
        path = self.root / "huge.db"
        archive(path, [("x/desc", "x" * 2097153)])
        with self.assertRaises(ValueError): list(read_repository(path))

    def test_search_treats_sql_and_fts_operators_as_data(self):
        for query in ['" OR 1=1 --', "NEAR(foo)", "nmap' UNION SELECT", "a:b*", "[]"]:
            self.catalog.search(query)
        self.assertEqual(self.catalog.info()["tools"], 14)
        with self.assertRaises(ValueError): self.catalog.search("x" * 513)
        with self.assertRaises(ValueError): self.catalog.search(limit=100000)

    def test_no_package_execution_for_browsing(self):
        with patch("subprocess.run", side_effect=AssertionError("must not execute")):
            self.catalog.search("enumerate smb")
            self.catalog.show("nmap")
            self.catalog.categories()

    def test_pacman_snapshot_only_uses_fixed_read_queries(self):
        with patch("subprocess.run", side_effect=[subprocess.CompletedProcess([],0,"nmap 1\n", ""),
                   subprocess.CompletedProcess([],0,"nmap /usr/bin/nmap\nnmap /usr/bin/nping\nnmap /etc/nmap.conf\n", "")]) as run:
            packages, executables = installed_snapshot()
        self.assertEqual(packages, {"nmap":"1"})
        self.assertEqual(executables, [("nmap","nmap"),("nmap","nping")])
        self.assertEqual([c.args[0] for c in run.call_args_list], [["pacman","-Q"],["pacman","-Ql"]])

    def test_non_arch_host_remains_usable(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(installed_snapshot(), (None,None))
        self.assertTrue(self.catalog.search("firmware"))

    def test_unrelated_database_is_not_modified(self):
        other = self.root / "other.sqlite3"
        db = sqlite3.connect(other); db.execute("CREATE TABLE private(value)"); db.commit(); db.close()
        other.chmod(0o640)
        before = other.read_bytes()
        with self.assertRaises(ValueError): Catalog(other)
        self.assertEqual(other.read_bytes(), before)
        self.assertEqual(other.stat().st_mode & 0o777, 0o640)

    def test_import_thousands_and_rank_search(self):
        start = time.monotonic()
        records = [{"name":f"research-{i:05}","description":f"Firmware research utility number {i}", "groups":["blackarch-firmware"]} for i in range(5000)]
        self.catalog.import_packages(records, "fixture", "blackarch")
        elapsed = time.monotonic() - start
        start = time.monotonic()
        self.assertEqual(len(self.catalog.search("firmware research", limit=100)), 100)
        search_time = time.monotonic() - start
        # Generous local regression gates, not a universal hardware guarantee.
        self.assertLess(elapsed, 30)
        self.assertLess(search_time, 3)

    def test_terminal_control_sequences_are_not_displayed(self):
        self.assertEqual(text("\x1b[31mred\x1b[0m\x00"), "red")

    def test_metadata_urls_do_not_become_non_web_program_actions(self):
        for url in ["file:///etc/passwd", "javascript:alert(1)", "ssh://example.invalid", "https://user:password@example.invalid"]:
            self.assertEqual(web_url(url), "")
        self.assertEqual(web_url("https://example.invalid/docs"), "https://example.invalid/docs")


if __name__ == "__main__": unittest.main()
