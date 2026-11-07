"""sbtools: offline catalog access. Browsing never installs or executes tools."""

import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile

from solace_assist import __version__
from solace_assist.core.catalog import Catalog, text
from solace_assist.sources.pacman import installed_snapshot, read_repository, sync_local


def filters(parser):
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--favorites", action="store_true")
    parser.add_argument("--tag")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--json", action="store_true")


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--version", action="version", version=f"sbtools {__version__}")
    root.add_argument("--db", type=Path, help="Override the private per-user catalog database")
    commands = root.add_subparsers(dest="command")
    p = commands.add_parser("search", help="Search by tool name or intended task")
    p.add_argument("query", nargs="*", help="A quoted phrase or search words")
    p.add_argument("--category"); filters(p)
    p = commands.add_parser("show", help="Show metadata, documentation status and personal notes")
    p.add_argument("tool"); p.add_argument("--json", action="store_true")
    p = commands.add_parser("category", help="List categories, or browse one")
    p.add_argument("name", nargs="?"); filters(p)
    p = commands.add_parser("installed", help="Browse the last explicitly synchronized installed-package snapshot")
    filters(p)
    p = commands.add_parser("sync", help="Explicit read-only import; no downloads, repo enablement or pacman transactions")
    p.add_argument("--local-dir", type=Path, default=Path("/var/lib/pacman/sync"))
    p.add_argument("--repo-db", type=Path, help="Import an explicit Pacman/BlackArch .db archive")
    p.add_argument("--repository", help="Repository label for --repo-db")
    p.add_argument("--no-installed", action="store_true")
    p.add_argument("--no-executables", action="store_true")
    p.add_argument("--json", action="store_true")
    p = commands.add_parser("favorite", help="Add/remove a favorite without changing package state")
    p.add_argument("tool"); p.add_argument("--remove", action="store_true")
    p = commands.add_parser("note", help="Read a note, or explicitly save text/stdin")
    p.add_argument("tool")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--text"); g.add_argument("--stdin", action="store_true"); g.add_argument("--clear", action="store_true")
    p = commands.add_parser("tag", help="Add/remove a personal searchable tag")
    p.add_argument("tool"); p.add_argument("tag"); p.add_argument("--remove", action="store_true")
    p = commands.add_parser("info", help="Catalog counts and source provenance")
    p.add_argument("--json", action="store_true")
    p = commands.add_parser("browse", help="Open one tool's documentation in the explorer; never execute it")
    p.add_argument("tool")
    p = commands.add_parser("launch", help="Optional Walker task-search launcher; selection opens documentation")
    p.add_argument("query", nargs="*")
    p = commands.add_parser("templates", help="List reviewed typed command previews; no execution")
    p.add_argument("--tool"); p.add_argument("--json", action="store_true")
    p = commands.add_parser("preview", help="Preview a reviewed template; never execute, insert or submit it")
    p.add_argument("template")
    p.add_argument("--arg", action="append", default=[], metavar="NAME=VALUE")
    p.add_argument("--shell", choices=["bash", "zsh", "sh", "fish", "generic"], default="generic")
    p.add_argument("--authorized", action="store_true", help="Confirm authorization for the explicit network target")
    p.add_argument("--json", action="store_true")
    return root


def print_rows(rows, as_json=False):
    if as_json:
        print(json.dumps(rows, indent=2)); return
    if not rows:
        print("No matching tools. Try fewer words, another category, or explicitly sync local metadata.")
    for row in rows:
        status = "installed" if row["installed"] else "catalog" if row["available"] else "reference"
        favorite = "*" if row["favorite"] else " "
        print(f"{favorite} {row['id']:<25} {status:<10} {text(row['purpose']).replace(chr(10), ' ')}")


def show_text(tool):
    lines = [f"{tool['name']} ({tool['id']})", tool["purpose"],
             "Categories: " + ", ".join(tool["categories"]),
             "Documentation: " + tool["documentation_status"],
             "Package mappings: " + ", ".join(tool["tool_packages"]),
             "Known tool executables: " + (", ".join(tool["tool_executables"]) or "not verified"),
             "Installed: " + (", ".join(f"{p['package']} {p['version']}" for p in tool["installed_packages"]) or "not in the cached installed snapshot"),
             "Documentation URL: " + (tool["documentation_url"] or "not curated"),
             "Upstream URL: " + (tool["url"] or "not supplied")]
    for package in tool["packages"]:
        lines.append(f"Catalog: {package['source']}/{package['repository']}/{package['name']} {package['version']} — {package['provenance']}")
        if package["description"]: lines.append(package["description"])
        dependencies = json.loads(package["dependencies"])
        if dependencies: lines.append("Dependencies: " + ", ".join(dependencies))
    if tool["description"]: lines += ["", tool["description"]]
    guide = tool.get("guide_provenance")
    if guide:
        lines += ["Source review: " + guide["reviewed_on"], guide["scope"],
                  "Examples are source-checked, not runtime-validated. Review before running; Assist never executes them."]
        lines += ["Source: " + url for url in guide["sources"]]
    if tool["documentation"]: lines += ["", tool["documentation"]]
    else: lines += ["", "No verified command guide is bundled yet. Consult the official documentation; no flags or commands have been inferred."]
    if tool["tags"]: lines.append("Personal tags: " + ", ".join(tool["tags"]))
    if tool["note"]: lines += ["", "Personal note:", tool["note"]]
    return text("\n".join(lines), 300000)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        catalog = Catalog(args.db)
        if args.command is None or args.command == "browse":
            tool = catalog.show(args.tool) if args.command == "browse" else None
            try:
                from solace_assist.interfaces.tui import ToolExplorer
            except ImportError:
                print("The TUI needs the optional Textual dependency. Install solace-assist[tui] in a virtual environment, or use sbtools search/show/sync.", file=sys.stderr)
                return 2
            ToolExplorer(catalog, initial_tool=tool["id"] if tool else None,
                         initial_query=tool["name"] if tool else "").run()
        elif args.command == "launch":
            from solace_assist.interfaces.launcher import launch
            return launch(catalog, " ".join(args.query))
        elif args.command == "templates":
            from solace_assist.core.templates import list_templates
            rows = list_templates(args.tool)
            print(json.dumps(rows, indent=2) if args.json else "\n".join(f"{row['id']}: {row['description']} ({', '.join(row['arguments'])})" for row in rows))
        elif args.command == "preview":
            from solace_assist.core.templates import preview
            arguments = {}
            for argument in args.arg:
                if "=" not in argument:
                    raise ValueError("Template arguments use NAME=VALUE")
                key, value = argument.split("=", 1)
                if key in arguments:
                    raise ValueError("Duplicate template argument: " + key)
                arguments[key] = value
            result = preview(args.template, arguments, args.shell, args.authorized)
            print(json.dumps(result, indent=2) if args.json else (result["command"] or json.dumps(result["argv"])) + "\n" + result["caution"])
        elif args.command in {"search", "category", "installed"}:
            if args.command == "category" and args.name is None:
                categories = catalog.categories()
                print(json.dumps(categories, indent=2) if args.json else "\n".join(f"{name}: {count}" for name, count in categories))
            else:
                category = args.name if args.command == "category" else getattr(args, "category", None)
                query = " ".join(args.query) if args.command == "search" else ""
                rows = catalog.search(query, category, args.installed or args.command == "installed", args.favorites, args.tag, args.limit)
                print_rows(rows, args.json)
        elif args.command == "show":
            tool = catalog.show(args.tool, record_view=True)
            print(json.dumps(tool, indent=2) if args.json else show_text(tool))
        elif args.command == "sync":
            if args.repo_db:
                if not args.repository: raise ValueError("--repo-db requires --repository")
                counts = {args.repository: catalog.import_packages(read_repository(args.repo_db), "provided", args.repository,
                           "user-provided metadata; not independently signature-verified")}
                if not args.no_installed:
                    packages, executables = installed_snapshot(not args.no_executables)
                    if packages is not None:
                        catalog.replace_installed(packages, executables); counts["installed"] = len(packages)
            else:
                if args.repository: raise ValueError("--repository is used only with --repo-db")
                counts = sync_local(catalog, args.local_dir, not args.no_installed, not args.no_executables)
            print(json.dumps(counts, indent=2) if args.json else "Imported read-only snapshots: " + (str(counts) if counts else "none found; bundled discovery data remains available"))
        elif args.command == "favorite":
            catalog.favorite(args.tool, not args.remove)
            print("Favorite updated.")
        elif args.command == "note":
            if args.text is not None or args.stdin or args.clear:
                body = sys.stdin.read(262145) if args.stdin else args.text or ""
                catalog.note(args.tool, body); print("Note saved locally.")
            else: print(text(catalog.show(args.tool)["note"], 300000))
        elif args.command == "tag":
            catalog.tag(args.tool, args.tag, args.remove); print("Personal tag updated.")
        elif args.command == "info":
            info = catalog.info()
            print(json.dumps(info, indent=2) if args.json else "\n".join(f"{key}: {value}" for key, value in info.items()))
        return 0
    except (ValueError, KeyError, OSError, sqlite3.Error, tarfile.TarError, subprocess.SubprocessError) as error:
        print("ERROR: " + text(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
