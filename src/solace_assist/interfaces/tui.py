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
from textual.css.query import NoMatches
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Markdown, OptionList, Static
from textual.widgets.option_list import Option

from solace_assist.core.catalog import text
from solace_assist.sources.pacman import sync_local
from solace_assist.interfaces.palette import DEFAULT_PALETTE, load_palette, system_palette_path
from solace_assist.interfaces.builder import CommandBuilder, TaskPicker
from solace_assist.core.templates import list_templates
from solace_assist.interfaces import helper_state


def escaped(value, limit=8192):
    return re.sub(r"([\\`*_{}\[\]()#+.!>|-])", r"\\\1", text(value, limit))


def detail_markdown(tool):
    lines = [f"# {escaped(tool['name'])}", escaped(tool["purpose"]),
             "**Categories:** " + escaped(", ".join(tool["categories"])),
             "**Documentation:** " + escaped(tool["documentation_status"]),
             "**Installed snapshot:** " + escaped(", ".join(f"{p['package']} {p['version']}" for p in tool["installed_packages"]) or "not recorded"),
             "**Package mappings:** " + escaped(", ".join(tool["tool_packages"])),
             "**Known tool executables:** " + escaped(", ".join(tool["tool_executables"]) or "not verified")]
    if tool["description"]: lines += [escaped(tool["description"])]
    guide = tool.get("guide_provenance")
    if guide:
        lines += ["**Source review:** " + escaped(guide["reviewed_on"]), escaped(guide["scope"]),
                  "Examples are source-checked, not runtime-validated. Review before running; Assist never executes them."]
        lines += ["Source: " + escaped(url) for url in guide["sources"]]
    lines += ["## Documentation"]
    lines.append(tool["documentation"] or "No verified command guide is bundled yet. Use official documentation; no flags or examples are inferred.")
    templates = list_templates(tool["id"])
    if templates:
        lines += ["## Build a reviewed command", "Press **Ctrl+P** (or Build command) to fill in a typed form and preview, never execute:"]
        lines += ["- " + escaped(row["description"]) for row in templates]
    # Render URLs as text rather than automatically launching external programs.
    if tool["documentation_url"]: lines.append("Official docs: " + escaped(tool["documentation_url"]))
    if tool["url"]: lines.append("Upstream: " + escaped(tool["url"]))
    if tool["tags"]: lines += ["**Personal tags:** " + escaped(", ".join(tool["tags"]))]
    if tool["note"]: lines += ["## Personal note", escaped(tool["note"], 65536)]
    if tool["packages"]:
        lines += ["## Package metadata (not a command guide)"]
        for package in tool["packages"][:8]:
            lines.append(escaped(f"{package['repository']}/{package['name']} {package['version']} — {package['provenance']}"))
    return "\n\n".join(lines)


class ToolExplorer(App):
    TITLE = "Solace Assist"
    SUB_TITLE = "Offline tool discovery — no command execution"
    COMMAND_PALETTE_BINDING = "ctrl+shift+p"
    CSS = """
    Screen { background: $background; color: $foreground; }
    #search { margin: 0 1; }
    #filters { height: 3; }
    #actions { height: 3; margin: 0 1; }
    #actions Button { margin-right: 1; }
    #helper-status { height: auto; max-height: 4; margin: 0 1; color: $accent; }
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
        Binding("ctrl+t", "tasks", "Tasks"),
        Binding("ctrl+p", "build", "Build command"),
        Binding("escape", "back", "Back", priority=True),
    ]

    def __init__(self, catalog, palette_path=None, initial_tool=None, initial_query="", helper_session=None, **kwargs):
        super().__init__(**kwargs)
        self.palette_path = system_palette_path() if palette_path is None else palette_path
        self._palette_name = None
        self.refresh_system_theme()
        self.catalog = catalog
        self.opening_tool = initial_tool
        self.initial_query = initial_query
        self.helper_session = helper_session
        self.context_updated = None
        self.start_guided = not initial_tool or bool(catalog.show(initial_tool)["guide_provenance"])
        self.category = None
        self.category_values = {}
        self.selected_id = None
        self.search_generation = 0
        self.detail_generation = 0
        self.search_timer = None
        self.syncing = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="actions"):
            yield Button("Start a task", id="tasks")
            yield Button("Build command", id="build")
        yield Static("", id="helper-status", markup=False)
        yield Input(value=self.initial_query, placeholder="Search a task: enumerate SMB, analyze firmware, decode radio signals…", id="search")
        with Horizontal(id="filters"):
            yield Checkbox("Reviewed guides", value=self.start_guided, id="guided")
            yield Checkbox("Installed", id="installed", tooltip="Only tools in the last explicitly synchronized installed-package snapshot")
            yield Checkbox("Favorites", id="favorites", tooltip="Only your saved favorites")
        yield Static("Bundled purpose references; Ctrl+R explicitly imports local package metadata.", id="status", markup=False)
        with Horizontal(id="body"):
            yield OptionList(id="categories")
            yield DataTable(id="results", cursor_type="row", zebra_stripes=True)
            with VerticalScroll(id="details"):
                yield Markdown("Select a tool. Browsing never executes it.", id="detail")
        yield Footer()

    def on_mount(self):
        self.set_interval(1.0, self.refresh_system_theme)
        if self.helper_session:
            self.set_interval(0.5, self.refresh_context)
            self.refresh_context()
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
        for index, (name, count) in enumerate(self.catalog.categories(self.query_one("#guided", Checkbox).value)):
            key = f"category-{index}"
            self.category_values[key] = name
            sidebar.add_option(Option(Text(f"{name} ({count})"), id=key))

    def on_input_changed(self, event: Input.Changed):
        if event.input.id != "search": return
        if self.search_timer is not None: self.search_timer.stop()
        self.search_timer = self.set_timer(0.12, self.request_search)

    def on_checkbox_changed(self, event: Checkbox.Changed):
        if event.checkbox.id not in {"guided", "installed", "favorites"}:
            return
        if event.checkbox.id == "guided":
            self.category = None
            self.refresh_categories()
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
                           self.query_one("#favorites", Checkbox).value, self.query_one("#guided", Checkbox).value)

    @work(thread=True, exclusive=True, group="catalog-search", exit_on_error=False)
    def search_worker(self, generation, query, category, installed, favorites, guided):
        try:
            rows = self.catalog.search(query, category, installed, favorites, limit=250, guided=guided)
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
        scope = "reviewed guides" if self.query_one("#guided", Checkbox).value else "all metadata (guides may be unavailable)"
        self.query_one("#status", Static).update(f"{len(rows)} results • {scope} • Ctrl+T tasks • Ctrl+P command builder")
        if self.opening_tool:
            tool_id, self.opening_tool = self.opening_tool, None
            for index, row in enumerate(rows):
                if row["id"] == tool_id:
                    table.move_cursor(row=index)
                    break
            self.request_detail(tool_id)
            if self.has_class("narrow"):
                self.add_class("detail-open")
                self.query_one("#details", VerticalScroll).focus()
        elif rows:
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

    def on_button_pressed(self, event):
        if event.button.id == "tasks": self.action_tasks()
        elif event.button.id == "build": self.action_build()

    def action_tasks(self):
        def chosen(task):
            if not task:
                return
            self.opening_tool = task["tool"]
            self.category = None
            self.query_one("#search", Input).value = task["tool"]
            self.request_search()
            self.notify(task["why"], timeout=8)
            if task["template"]:
                self.push_screen(CommandBuilder(template_id=task["template"], helper_session=self.helper_session))
        self.push_screen(TaskPicker(), chosen)

    def action_build(self):
        self.push_screen(CommandBuilder(tool=self.selected_id, helper_session=self.helper_session))

    def refresh_context(self):
        # Timers may already be queued when a screen is tearing down.
        try:
            status = self.query_one("#helper-status", Static)
        except NoMatches:
            return
        try:
            ready = helper_state.read(self.helper_session, "ready.json")
            label = "Bash Readline connected. Ctrl+G in shell: context. Stage a preview here; Ctrl+X then Ctrl+I at an empty shell prompt inserts it WITHOUT Enter."
            if not ready:
                label = "Read-only helper: no editable-buffer adapter connected. Use tasks/guides and manual previews. The selected shell is not replaced."
            status.update(label)
            event = helper_state.read(self.helper_session, "context.json")
            if not event or event.get("updated") == self.context_updated:
                return
            self.context_updated = event["updated"]
            tool = self.catalog.tool_for_executable(event.get("executable") or "")
            if not tool:
                status.update("No known simple executable in that buffer. Search manually; no arguments or credentials were saved. " + label)
                return
            self.opening_tool = tool
            self.category = None
            self.query_one("#guided", Checkbox).value = bool(self.catalog.show(tool)["guide_provenance"])
            self.query_one("#installed", Checkbox).value = False
            self.query_one("#favorites", Checkbox).value = False
            self.query_one("#search", Input).value = tool
            self.request_search()
        except (ValueError, OSError, KeyError, TypeError) as error:
            status.update("Helper state unavailable; manual browsing remains usable.")

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
