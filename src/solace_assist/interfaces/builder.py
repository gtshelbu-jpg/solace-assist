"""Interactive reviewed-template forms. Preview/staging never executes commands."""

import json

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, Static

from solace_assist.core.tasks import TASKS
from solace_assist.core.templates import TEMPLATES, list_templates, preview
from solace_assist.interfaces import helper_state


class TaskPicker(ModalScreen):
    CSS = """
    TaskPicker { align: center middle; }
    #task-box { width: 85%; height: auto; max-height: 90%; border: thick $accent; background: $surface; padding: 1 2; }
    #task-list { height: auto; max-height: 18; }
    """
    BINDINGS = [("escape", "close", "Close")]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="task-box"):
            yield Label("Choose an investigation task — guidance, not automatic execution")
            yield OptionList(*(task["name"] for task in TASKS), id="task-list")
            yield Button("Cancel", id="task-cancel")

    def on_option_list_option_selected(self, event):
        self.dismiss(TASKS[event.option_index])

    def on_mount(self):
        self.query_one("#task-list", OptionList).focus()

    def on_button_pressed(self, event):
        self.dismiss(None)

    def action_close(self):
        self.dismiss(None)


class CommandBuilder(ModalScreen):
    CSS = """
    CommandBuilder { align: center middle; }
    #builder-box { width: 90%; height: auto; max-height: 95%; border: thick $accent; background: $surface; padding: 1 2; }
    #builder-fields { height: auto; }
    #builder-preview { height: auto; min-height: 3; margin: 1 0; }
    #builder-actions { height: auto; }
    #builder-actions Button { margin-right: 1; }
    #builder-description { height: auto; margin: 1 0; }
    """
    BINDINGS = [("escape", "close", "Close"),
                Binding("ctrl+enter", "stage", "Stage", priority=True)]

    def __init__(self, tool=None, template_id=None, helper_session=None, **kwargs):
        super().__init__(**kwargs)
        options = list_templates(tool)
        self.template_id = template_id or (options[0]["id"] if options else next(iter(TEMPLATES)))
        self.helper_session = helper_session
        ready = helper_state.read(helper_session, "ready.json") if helper_session else None
        self.render_shell = "bash" if ready and ready.get("shell") == "bash" else "generic"
        self.generated = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="builder-box"):
            yield Label("Build a reviewed command — nothing runs here")
            yield Select([(row["id"] + " — " + row["description"], row["id"]) for row in list_templates()],
                         value=self.template_id, allow_blank=False, id="builder-template")
            yield Select([("Structured arguments (unknown shell)", "generic"), ("Bash", "bash"), ("Zsh", "zsh"), ("Fish", "fish"), ("POSIX sh", "sh")],
                         value=self.render_shell, allow_blank=False, id="builder-shell")
            yield Static("", id="builder-description", markup=False)
            with VerticalScroll(id="builder-fields"):
                pass
            yield Static("Enter: preview · Ctrl+Enter: stage · Esc: close", id="builder-preview", markup=False)
            with Horizontal(id="builder-actions"):
                yield Button("Preview", id="builder-generate", variant="primary")
                yield Button("Stage for shell", id="builder-stage", disabled=True)
                yield Button("Close", id="builder-close")

    async def on_mount(self):
        await self.fields()

    async def fields(self):
        self.generated = None
        self.query_one("#builder-stage", Button).disabled = True
        fields = self.query_one("#builder-fields", VerticalScroll)
        await fields.remove_children()
        template = TEMPLATES[self.template_id]
        descriptions = {"path": "Existing local file path; no file is read by this form",
                        "single-ip": "One explicitly authorized IP, e.g. 192.0.2.10 (documentation placeholder)",
                        "port-list": "Explicit ports, e.g. 22,80,443 — no ranges or extra flags"}
        for name, kind in template["arguments"].items():
            await fields.mount(Label(name + " — " + descriptions[kind]), Input(id="argument-" + name))
        self.query_one("#builder-description", Static).update(template["description"] +
            "\n" + template["options"])
        self.query_one("#builder-preview", Static).update("Enter: preview · Ctrl+Enter: stage · Esc: close")
        fields.query(Input).first().focus()

    async def on_select_changed(self, event):
        if event.select.id == "builder-template" and event.value in TEMPLATES and event.value != self.template_id:
            self.template_id = event.value
            await self.fields()
        elif event.select.id == "builder-shell" and event.value != self.render_shell:
            self.render_shell = event.value
            self.invalidate()

    def invalidate(self):
        self.generated = None
        self.query_one("#builder-stage", Button).disabled = True

    def on_input_changed(self, event):
        self.invalidate()

    def on_input_submitted(self, event):
        event.stop()
        self.action_preview()

    def on_button_pressed(self, event):
        event.stop()
        if event.button.id == "builder-close":
            self.dismiss(None)
        elif event.button.id == "builder-generate":
            self.action_preview()
        elif event.button.id == "builder-stage":
            self.action_stage()

    def action_preview(self):
        try:
            arguments = {name: self.query_one("#argument-" + name, Input).value for name in TEMPLATES[self.template_id]["arguments"]}
            result = preview(self.template_id, arguments, self.render_shell)
            self.generated = (self.template_id, arguments)
            ready = helper_state.read(self.helper_session, "ready.json") if self.helper_session else None
            can_stage = self.render_shell == "bash" and ready and ready.get("shell") == "bash"
            self.query_one("#builder-preview", Static).update((result["command"] or json.dumps(result["argv"])) +
                ("\nCtrl+Enter: stage for Bash (does not run)." if can_stage else "\nRead-only preview."))
            self.query_one("#builder-stage", Button).disabled = not can_stage
            return True
        except (ValueError, OSError, KeyError, TypeError) as error:
            self.invalidate()
            self.query_one("#builder-preview", Static).update(str(error))
            return False

    def action_stage(self):
        # Rebuild from current fields so a shortcut cannot stage a stale preview.
        if not self.action_preview() or self.query_one("#builder-stage", Button).disabled:
            return
        try:
            if self.generated and self.helper_session:
                helper_state.queue(self.helper_session, *self.generated)
                self.query_one("#builder-preview", Static).update("Staged. Ctrl+B, Left → empty prompt → Ctrl+X Ctrl+I to insert.\nYour Enter runs it; existing input is never overwritten.")
                self.query_one("#builder-stage", Button).disabled = True
        except (ValueError, OSError, KeyError, TypeError) as error:
            self.invalidate()
            self.query_one("#builder-preview", Static).update(str(error))

    def action_close(self):
        self.dismiss(None)
