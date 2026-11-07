"""Small reviewed starting workflows, not generated assessments or tool execution."""

TASKS = [
    {"name": "Identify a binary's architecture", "tool": "readelf", "template": "readelf-header",
     "why": "Read an ELF header before considering disassembly. Do not execute an unknown binary."},
    {"name": "Inspect symbols in a binary", "tool": "readelf", "template": "readelf-symbols",
     "why": "Inspect available symbol names; stripped binaries may have little symbol information."},
    {"name": "Inspect an existing packet capture", "tool": "tcpdump", "template": "tcpdump-file",
     "why": "Start offline: read at most 20 saved packets, without live capture or name resolution."},
    {"name": "Identify services on an authorized lab IP", "tool": "nmap", "template": "nmap-services",
     "why": "Version probes contact services. Confirm your authorization, one IP and an explicit port list."},
    {"name": "Investigate SMB share access", "tool": "smbclient", "template": None,
     "why": "Read the SMB guide and choose an authorized server; credentials and anonymous access differ."},
    {"name": "Inspect a firmware image", "tool": "binwalk", "template": None,
     "why": "Review signature results before extraction; use isolation for untrusted parser inputs."},
]
