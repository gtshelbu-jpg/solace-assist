"""Reviewed, typed command previews. This module never executes or inserts them."""

import ipaddress
import re
import shlex


TEMPLATES = {
    "readelf-header": {
        "tool": "readelf", "description": "Inspect an ELF file header without running it",
        "arguments": {"file": "path"}, "network": False,
        "options": "-h reads the ELF header and architecture; it does not run the file.",
    },
    "readelf-symbols": {
        "tool": "readelf", "description": "Inspect ELF symbols with wide output",
        "arguments": {"file": "path"}, "network": False,
        "options": "--wide avoids truncated columns; --symbols lists available symbols, not decompiled source.",
    },
    "tcpdump-file": {
        "tool": "tcpdump", "description": "Read at most 20 packets from an existing capture, without name resolution",
        "arguments": {"file": "path"}, "network": False,
        "options": "-r reads an existing capture; -n disables name resolution; -c 20 bounds the packet count.",
    },
    "nmap-services": {
        "tool": "nmap", "description": "Version probes on one explicitly authorized IP and port list",
        "arguments": {"target": "single-ip", "ports": "port-list"}, "network": True,
        "options": "-sV actively probes service versions; -p limits probes to your explicit ports. This is not passive inspection.",
    },
}


def list_templates(tool=None):
    return [{"id": key, **value, "guide": value["tool"], "execution": False}
            for key, value in TEMPLATES.items() if tool is None or value["tool"] == tool]


def argument_value(kind, value):
    if not isinstance(value, str) or not value or len(value) > 4096 or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value):
        raise ValueError("Template values must be nonempty single-line text without control characters")
    if kind == "path":
        # Positional paths must not become options. Preserve relative semantics.
        # GNU tools may also expand @response-files before parsing options.
        return "./" + value if value.startswith(("-", "@")) else value
    if kind == "single-ip":
        return str(ipaddress.ip_address(value))
    if kind == "port-list":
        if not re.fullmatch(r"[0-9]+(?:,[0-9]+){0,31}", value):
            raise ValueError("Use at most 32 explicit comma-separated ports, not a range or option")
        ports = [int(port) for port in value.split(",")]
        if any(not 1 <= port <= 65535 for port in ports):
            raise ValueError("Ports must be between 1 and 65535")
        return ",".join(str(port) for port in dict.fromkeys(ports))
    raise ValueError("Unknown template argument type")


def render_argv(argv, shell):
    if not all(isinstance(arg, str) and not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in arg) for arg in argv):
        raise ValueError("Command previews cannot contain control characters or implicit submission")
    if shell in ("bash", "zsh", "sh"):
        return shlex.join(argv)
    if shell == "fish":
        return " ".join("'" + arg.replace("\\", "\\\\").replace("'", "\\'") + "'" for arg in argv)
    if shell == "generic":
        return None  # Structured preview only; do not guess an unknown grammar.
    raise ValueError("Unsupported shell; choose generic for a structured preview")


def preview(template_id, arguments, shell="generic", authorized=False):
    # Legacy callers may still pass authorized; previews need no acknowledgment.
    if template_id not in TEMPLATES:
        raise ValueError("Unknown reviewed template")
    template = TEMPLATES[template_id]
    if set(arguments) != set(template["arguments"]):
        raise ValueError("Supply exactly these arguments: " + ", ".join(template["arguments"]))
    values = {key: argument_value(kind, arguments[key]) for key, kind in template["arguments"].items()}
    if template_id == "readelf-header":
        argv = ["readelf", "-h", values["file"]]
    elif template_id == "readelf-symbols":
        argv = ["readelf", "--wide", "--symbols", values["file"]]
    elif template_id == "tcpdump-file":
        argv = ["tcpdump", "-n", "-c", "20", "-r", values["file"]]
    else:
        argv = ["nmap"] + (["-6"] if ":" in values["target"] else [])
        argv += ["-sV", "-p", values["ports"], values["target"]]
    return {
        "template": template_id, "tool": template["tool"], "guide": template["tool"],
        "argv": argv, "shell": shell, "command": render_argv(argv, shell),
        "execution": False, "insertion": False,
        "caution": "Review the bundled guide and actual tool version before use. Nothing was run or inserted.",
    }
