import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from solace_assist.core.templates import list_templates, preview, render_argv


class TemplateTests(unittest.TestCase):
    def test_offline_preview_and_unknown_shell_have_no_execution_or_insertion(self):
        with patch("subprocess.run", side_effect=AssertionError("preview must not execute")):
            result = preview("tcpdump-file", {"file": "my capture.pcap"})
        self.assertEqual(result["argv"], ["tcpdump", "-n", "-c", "20", "-r", "my capture.pcap"])
        self.assertIsNone(result["command"])
        self.assertFalse(result["execution"])
        self.assertFalse(result["insertion"])
        self.assertEqual(len(list_templates("readelf")), 2)

    def test_paths_cannot_become_options_or_response_files(self):
        for value in ("-h", "@settings"):
            result = preview("readelf-header", {"file": value}, "bash")
            self.assertEqual(result["argv"][-1], "./" + value)
            self.assertNotIn("\n", result["command"])

    def test_network_preview_requires_authorization_and_single_explicit_ip(self):
        arguments = {"target": "192.0.2.10", "ports": "22,80,443"}
        with self.assertRaisesRegex(ValueError, "authorization"):
            preview("nmap-services", arguments)
        result = preview("nmap-services", arguments, "bash", authorized=True)
        self.assertEqual(result["argv"], ["nmap", "-sV", "-p", "22,80,443", "192.0.2.10"])
        self.assertIn("-6", preview("nmap-services", {**arguments, "target": "2001:db8::1"}, authorized=True)["argv"])
        for bad in ("192.0.2.0/24", "--script", "host; command", "example.com"):
            with self.assertRaises(ValueError):
                preview("nmap-services", {**arguments, "target": bad}, authorized=True)
        for bad in ("0", "65536", "1-65535", "22 --script", "22,abc"):
            with self.assertRaises(ValueError):
                preview("nmap-services", {**arguments, "ports": bad}, authorized=True)

    def test_controls_missing_extra_and_unknown_fields_are_rejected(self):
        for value in ("", "a\nb", "a\rb", "a\x00b", "a\x1bb"):
            with self.assertRaises(ValueError):
                preview("readelf-header", {"file": value}, "bash")
        for arguments in ({}, {"file": "x", "extra": "x"}):
            with self.assertRaises(ValueError):
                preview("readelf-header", arguments)
        with self.assertRaises(ValueError):
            preview("invented-template", {})
        with self.assertRaises(ValueError):
            render_argv(["echo", "x\n"], "bash")

    def test_available_shell_renderers_round_trip_literal_arguments(self):
        # Execute only our JSON fixture, never a security tool or a preview action.
        values = ["space value", "single'quote", 'double"quote', "$(not-a-command)", "; literal", "back\\slash", "日本語", "!history"]
        argv = [sys.executable, "-c", "import json,sys;print(json.dumps(sys.argv[1:]))", *values]
        for shell in ("bash", "zsh", "fish", "sh"):
            executable = shutil.which(shell)
            if executable is None:
                continue
            with self.subTest(shell=shell):
                command = render_argv(argv, shell)
                result = subprocess.run([executable, "-c", command], capture_output=True, text=True, check=True)
                self.assertEqual(json.loads(result.stdout), values)


if __name__ == "__main__":
    unittest.main()
