"""Optional Textual interface. Catalog operations are shared with the CLI."""

import json
import hashlib
import re

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.theme import Theme
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Checkbox, DataTable, Footer, Header, Input, Markdown, OptionList, Static
from textual.widgets.option_list import Option

from solace_assist.core.catalog import text
from solace_assist.sources.pacman import sync_local
from solace_assist.interfaces.palette import DEFAULT_PALETTE, load_palette, system_palette_path


def escaped(value, limit=8192):
    return re.sub(r"([\\`*_{}\[\]()#+.!>|-])", r"\\\1", text(value, limit))


def detail_markdown(tool):
    lines = [f"# {escaped(tool['name'])}", escaped(tool["purpose"]),
             "**Categories:** " + escaped(", ".join(tool["categories"])),
             "**Documentation:** " + escaped(tool["documentation_status"]),
             "**Installed snapshot:** " + escaped(", ".join(f"{p['package']} {p['version']}" for p in tool["installed_packages"]) or "not recorded"),
             "**Package mappings:** " + escaped(", ".join(tool["tool_packages"])),
             "**Known tool executables:** " + escaped(", ".join(tool["tool_executables"]) or "not verified")]
    if tool["packages"]:
        lines += ["## Package metadata"]
        for package in tool["packages"]:
            lines.append(escaped(f"{package['repository']}/{package['name']} {package['version']}"))
            if package["description"]: lines.append(escaped(package["description"]))
            dependencies = json.loads(package["dependencies"])
            if dependencies: lines.append("Dependencies: " + escaped(", ".join(dependencies[:24])))
            lines.append(escaped(package["provenance"]))
    if tool["description"]: lines += [escaped(tool["description"])]
    guide = tool.get("guide_provenance")
    if guide:
        lines += ["**Source review:** " + escaped(guide["reviewed_on"]), escaped(guide["scope"]),
                  "Examples are source-checked, not runtime-validated. Review before running; Assist never executes them."]
        lines += ["Source: " + escaped(url) for url in guide["sources"]]
    lines += ["## Documentation"]
    lines.append(tool["documentation"] or "No verified command guide is bundled yet. Use official documentation; no flags or examples are inferred.")
    # Render URLs as text rather than automatically launching external programs.
    if tool["documentation_url"]: lines.append("Official docs: " + escaped(tool["documentation_url"]))
    if tool["url"]: lines.append("Upstream: " + escaped(tool["url"]))
    if tool["tags"]: lines += ["**Personal tags:** " + escaped(", ".join(tool["tags"]))]
    if tool["note"]: lines += ["## Personal note", escaped(tool["note"], 65536)]
    return "\n\n".join(lines)


class ToolExplorer(App):
    TITLE = "Solace Assist"
    SUB_TITLE = "Offline tool discovery — no command execution"
    CSS = """
    Screen { background: $background; color: $foreground; }
    #search { margin: 0 1; }
    #filters { height: 3; }
    #status { height: 1; margin: 0 1; color: $accent; }
    #body { height: 1fr; }
    #categories { width: 27; height: 1fr; border: solid $primary-muted; }
    #results { width: 2fr; height: 1fr; min-width: 25; border: solid $primary-muted; }
    #details { width: 3fr; min-width: 25; padding: 0 1; border: solid $primary-muted; }
    .narrow #categories { width: 19; }
    .narrow #details { display: none; }
    .narrow.detail-open #results { display: none; }
    .narrow.detail-open #categories { display: none; }
    .narrow.detail-open #details { display: block; width: 1fr; }
    """
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("slash", "focus_search", "Search"),
        Binding("ctrl+g", "focus_categories", "Categories"),
        Binding("f", "favorite", "Favorite"),
        Binding("ctrl+r", "sync", "Sync local metadata"),
        Binding("escape", "back", "Back", priority=True),
    ]

    def __init__(self, catalog, palette_path=None, **kwargs):
        super().__init__(**kwargs)
        self.palette_path = system_palette_path() if palette_path is None else palette_path
        self._palette_name = None
        self.refresh_system_theme()
        self.catalog = catalog
        self.category = None
        self.category_values = {}
        self.selected_id = None
        self.search_generation = 0
        self.detail_generation = 0
        self.search_timer = None
        self.syncing = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Search a task: enumerate SMB, analyze firmware, decode radio signals…", id="search")
        with Horizontal(id="filters"):
            yield Checkbox("Installed snapshot only", id="installed")
            yield Checkbox("Favorites only", id="favorites")
        yield Static("Bundled purpose references; Ctrl+R explicitly imports local package metadata.", id="status", markup=False)
        with Horizontal(id="body"):
            yield OptionList(id="categories")
            yield DataTable(id="results", cursor_type="row", zebra_stripes=True)
            with VerticalScroll(id="details"):
                yield Markdown("Select a tool. Browsing never executes it.", id="detail")
        yield Footer()

    def on_mount(self):
        self.set_interval(1.0, self.refresh_system_theme)
        self.query_one("#results", DataTable).add_columns("Tool", "Status", "Purpose")
        self.refresh_categories()
        self.query_one("#search", Input).focus()
        self.request_search()

    def refresh_system_theme(self):
        palette = load_palette(self.palette_path)
        if palette is None:
            if self._palette_name is not None:
                return  # Keep the last good palette during partial/invalid writes.
            palette = DEFAULT_PALETTE
        signature = hashlib.sha256(json.dumps(palette, sort_keys=True).encode()).hexdigest()[:16]
        name = "assist-" + signature
        if name == self._palette_name:
            return
        previous = self._palette_name
        self.register_theme(Theme(name=name, text_alpha=1.0, **palette))
        self.theme = name
        self._palette_name = name
        if previous is not None:
            self.unregister_theme(previous)

    def on_resize(self, event):
        self.set_class(event.size.width < 110, "narrow")

    def refresh_categories(self):
        sidebar = self.query_one("#categories", OptionList)
        sidebar.clear_options()
        sidebar.add_option(Option(Text("All categories"), id="all"))
        self.category_values = {"all": None}
        for index, (name, count) in enumerate(self.catalog.categories()):
            key = f"category-{index}"
            self.category_values[key] = name
            sidebar.add_option(Option(Text(f"{name} ({count})"), id=key))

    def on_input_changed(self, event: Input.Changed):
        if event.input.id != "search": return
        if self.search_timer is not None: self.search_timer.stop()
        self.search_timer = self.set_timer(0.12, self.request_search)

    def on_checkbox_changed(self, event: Checkbox.Changed):
        self.request_search()

    def on_input_submitted(self, event: Input.Submitted):
        self.query_one("#results", DataTable).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.category = self.category_values.get(event.option_id)
        self.request_search()

    def request_search(self):
        self.search_generation += 1
        self.search_worker(self.search_generation, self.query_one("#search", Input).value,
                           self.category, self.query_one("#installed", Checkbox).value,
                           self.query_one("#favorites", Checkbox).value)

    @work(thread=True, exclusive=True, group="catalog-search", exit_on_error=False)
    def search_worker(self, generation, query, category, installed, favorites):
        try:
            rows = self.catalog.search(query, category, installed, favorites, limit=250)
            self.call_from_thread(self.display_results, generation, rows)
        except Exception as error:
            self.call_from_thread(self.notify, text(error), severity="error")

    def display_results(self, generation, rows):
        if generation != self.search_generation: return
        table = self.query_one("#results", DataTable)
        table.clear()
        for row in rows:
            status = "installed" if row["installed"] else "catalog" if row["available"] else "reference"
            table.add_row(Text(("* " if row["favorite"] else "") + row["name"]),
                          Text(status), Text(row["purpose"].replace("\n", " ")), key=row["id"])
        self.query_one("#status", Static).update(f"{len(rows)} results (maximum 250) • no automatic execution • Ctrl+R reads local package caches")
        if rows:
            self.request_detail(rows[0]["id"])
        else:
            self.selected_id = None
            self.detail_generation += 1
            self.query_one("#detail", Markdown).update("No matching tools. Try fewer words or another filter.")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        if event.row_key.value: self.request_detail(str(event.row_key.value))

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        if event.row_key.value:
            self.request_detail(str(event.row_key.value))
            if self.has_class("narrow"):
                self.add_class("detail-open")
                self.query_one("#details", VerticalScroll).focus()

    def request_detail(self, tool_id):
        self.selected_id = tool_id
        self.detail_generation += 1
        self.detail_worker(self.detail_generation, tool_id)

    @work(thread=True, exclusive=True, group="catalog-detail", exit_on_error=False)
    def detail_worker(self, generation, tool_id):
        try:
            tool = self.catalog.show(tool_id, record_view=True)
            self.call_from_thread(self.display_detail, generation, tool)
        except Exception as error:
            self.call_from_thread(self.notify, text(error), severity="error")

    def display_detail(self, generation, tool):
        if generation == self.detail_generation:
            self.query_one("#detail", Markdown).update(detail_markdown(tool))

    def action_focus_search(self): self.query_one("#search", Input).focus()
    def action_focus_categories(self): self.query_one("#categories", OptionList).focus()
    def action_back(self):
        self.remove_class("detail-open")
        self.query_one("#results", DataTable).focus()

    def action_favorite(self):
        if self.selected_id: self.favorite_worker(self.selected_id)

    @work(thread=True, exclusive=True, group="catalog-favorite", exit_on_error=False)
    def favorite_worker(self, tool_id):
        try:
            self.catalog.favorite(tool_id, not self.catalog.show(tool_id)["favorite"])
            self.call_from_thread(self.request_search)
        except Exception as error:
            self.call_from_thread(self.notify, text(error), severity="error")

    def action_sync(self):
        if self.syncing: return
        self.syncing = True
        self.query_one("#status", Static).update("Importing local Pacman caches and installed-file metadata; no downloads or package operations…")
        self.sync_worker()

    @work(thread=True, exclusive=True, group="catalog-sync", exit_on_error=False)
    def sync_worker(self):
        try:
            counts = sync_local(self.catalog)
            self.call_from_thread(self.sync_finished, counts)
        except Exception as error:
            self.call_from_thread(self.sync_failed, text(error))

    def sync_finished(self, counts):
        self.syncing = False
        self.refresh_categories()
        self.request_search()
        self.notify("Read-only local import: " + str(counts))

    def sync_failed(self, error):
        self.syncing = False
        self.query_one("#status", Static).update("Import failed; personal data is preserved. " + error)
        self.notify(error, severity="error")
