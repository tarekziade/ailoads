import asyncio
import sys

from prompt_toolkit.application import Application
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit import HTML

from molotov import __version__
from molotov.ui.controllers import (
    TerminalController,
    SimpleController,
    RunStatus,
    create_key_bindings,
)


TITLE = HTML(
    f"<b>Molotov v{__version__}</b> ~ Happy Breaking 🥛🔨 ~ <i>Ctrl+C to abort</i>"
)


class MolotovApp:
    def __init__(
        self,
        refresh_interval=0.3,
        max_lines=25,
        simple_console=False,
        single_process=True,
    ):
        self.title = TITLE
        self.single_process = single_process
        self.simple_console = simple_console
        if simple_console:
            controller_klass = SimpleController
        else:
            controller_klass = TerminalController
        self.terminal = controller_klass(max_lines, single_process)
        self.errors = controller_klass(max_lines, single_process)
        self.status = RunStatus()
        self.key_bindings = create_key_bindings()
        self.refresh_interval = refresh_interval
        self.max_lines = max_lines
        self._running = False

    async def refresh_console(self):
        while self._running:
            for line in self.terminal.dump():
                sys.stdout.write(line)
                sys.stdout.flush()
            for line in self.errors.dump():
                sys.stdout.write(line)
                sys.stdout.flush()
            await asyncio.sleep(self.refresh_interval)

    async def start(self):
        self._running = True

        if self.simple_console:
            self.task = asyncio.ensure_future(self.refresh_console())
            return

        title_toolbar = Window(
            FormattedTextControl(lambda: self.title),
            height=1,
            style="class:title",
        )

        bottom_toolbar = Window(
            content=self.status,
            style="class:bottom-toolbar",
            height=1,
        )

        terminal = Window(content=self.terminal, height=self.max_lines + 2)
        errors = Window(content=self.errors, height=self.max_lines + 2)

        self.app = Application(
            min_redraw_interval=0.05,
            layout=Layout(
                HSplit(
                    [
                        title_toolbar,
                        VSplit([terminal, Window(width=4, char=" || "), errors]),
                        bottom_toolbar,
                    ]
                )
            ),
            style=None,
            key_bindings=self.key_bindings,
            refresh_interval=self.refresh_interval,
            color_depth=None,
            output=None,
            input=None,
            erase_when_done=True,
        )

        def _handle_exception(*args, **kw):
            pass

        self.app._handle_exception = _handle_exception
        self.task = asyncio.ensure_future(self.app.run_async())

    async def stop(self):
        self._running = False
        await asyncio.sleep(0)

        if not self.simple_console:
            try:
                self.app.exit()
            except Exception:
                pass
        self.terminal.close()
        self.errors.close()
        await self.task
