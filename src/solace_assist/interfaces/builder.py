"""Interactive reviewed-template forms. Preview/staging never executes commands."""

import json

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, Select, Static

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
    BINDINGS = [("escape", "close", "Close")]

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
            yield Checkbox("I am authorized to probe the explicit network target", id="builder-authorized")
            yield Static("Fill in the arguments, then generate a preview. No flags or targets are guessed.", id="builder-preview", markup=False)
            with Horizontal(id="builder-actions"):
                yield Button("Generate preview", id="builder-generate", variant="primary")
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
        self.query_one("#builder-authorized", Checkbox).display = template["network"]
        self.query_one("#builder-authorized", Checkbox).value = False
        self.query_one("#builder-description", Static).update(template["description"] +
            "\n" + template["options"] +
            "\nChoose a shell explicitly, or keep structured arguments. Only this helper session's Bash adapter can insert a Bash preview, at your explicit keypress.")
        self.query_one("#builder-preview", Static).update("Nothing generated or executed.")

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

    def on_checkbox_changed(self, event):
        self.invalidate()

    def on_button_pressed(self, event):
        try:
            if event.button.id == "builder-close":
                self.dismiss(None)
            elif event.button.id == "builder-generate":
                arguments = {name: self.query_one("#argument-" + name, Input).value for name in TEMPLATES[self.template_id]["arguments"]}
                authorized = self.query_one("#builder-authorized", Checkbox).value
                result = preview(self.template_id, arguments, self.render_shell, authorized)
                self.generated = (self.template_id, arguments, authorized)
                ready = helper_state.read(self.helper_session, "ready.json") if self.helper_session else None
                can_stage = self.render_shell == "bash" and ready and ready.get("shell") == "bash"
                instruction = ("A staged preview still requires Ctrl+X then Ctrl+I at an empty Bash prompt, followed by your own Enter."
                               if can_stage else "Read-only preview for the chosen grammar; no command insertion is available here.")
                self.query_one("#builder-preview", Static).update((result["command"] or json.dumps(result["argv"])) + "\n\n" + result["caution"] +
                    "\n" + instruction)
                self.query_one("#builder-stage", Button).disabled = not can_stage
            elif event.button.id == "builder-stage" and self.generated and self.helper_session:
                helper_state.queue(self.helper_session, *self.generated)
                self.query_one("#builder-preview", Static).update("Staged, NOT inserted or run.\nSwitch to the shell pane (Ctrl+B, Left), leave the prompt empty, then press Ctrl+X followed by Ctrl+I. Review and press Enter yourself.\nExisting nonempty commands are never overwritten.")
                self.query_one("#builder-stage", Button).disabled = True
        except (ValueError, OSError, KeyError, TypeError) as error:
            self.invalidate()
            self.query_one("#builder-preview", Static).update(str(error))

    def action_close(self):
        self.dismiss(None)
