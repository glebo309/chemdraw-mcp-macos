"""Themed Windows setup window (Tkinter); the counterpart of packaging/Welcome.swift.

Same palette, CHEMDRAW / MCP wordmark with three short colored rules, and the continuous
native-ChemDraw molecule animation (Braille-dot sprites from data/welcome.json, revealed by a
gold sweep). The setup protocol is SetupSession from desktop_setup, called in-process on a
worker thread. Windows needs no ChemDraw add-in, so the flow is: check software, test the live
connection, finish (install for this user and connect the selected assistants).

Diagnostics are saved automatically and privately after every step; they contain statuses and
allowlisted fields only, never drawings, connection keys, raw error text or personal paths.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import queue
import re
import shutil
import sys
import threading
import time
import uuid

PALETTE = {
    'accent': (0.96, 0.67, 0.80), 'lavender': (0.74, 0.68, 0.89), 'gold': (0.94, 0.82, 0.55),
    'cream': (0.94, 0.92, 0.89), 'sidebar': (0.13, 0.115, 0.15), 'panel': (0.18, 0.155, 0.19),
}
_BRAILLE = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3)]
CYCLE, SWEEP, FPS = 1.4, 0.476, 25
STYLE_STATUSES = ('style_selected', 'style_cleared')


def color(name, opacity=1.0, over='panel'):
    """Tk has no alpha: blend a palette color (or white) over a background color."""
    fg = (1.0, 1.0, 1.0) if name == 'white' else PALETTE[name]
    bg = PALETTE[over]
    return '#' + ''.join(f'{round(255 * (f * opacity + b * (1 - opacity))):02x}' for f, b in zip(fg, bg))


def sprite_dots(sprite):
    """Dot coordinates of a Braille sprite, as SetupPresentation.swift decodes them."""
    points = []
    for y, row in enumerate(sprite['rows']):
        for x, character in enumerate(row):
            value = ord(character)
            if not 0x2801 <= value <= 0x28FF:
                continue
            mask = value - 0x2800
            points += [(x * 2 + dx, y * 4 + dy) for bit, (dx, dy) in enumerate(_BRAILLE) if mask & (1 << bit)]
    return points


def sprite_layout(points, width, height, margin=12):
    """Normalized dots, scale and top-left offset that center the sprite inside the canvas."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    span_x, span_y = max(xs) - min(xs) + .9, max(ys) - min(ys) + .9
    scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_y)
    left, top = (width - span_x * scale) / 2, (height - span_y * scale) / 2
    return [(x - min(xs), y - min(ys)) for x, y in points], scale, left, top


class Flow:
    """Presentation state only; readiness always comes from the live backend check."""

    def __init__(self):
        self.step, self.connected, self.finished, self.show_diagnostics = 0, False, False, False

    def receive(self, value):
        status = value.get('status')
        if status in STYLE_STATUSES:  # a style choice leaves the tested connection as it is
            return None
        self.connected = status == 'ready' and value.get('ready') is True
        self.show_diagnostics = False
        if status == 'selected':
            self.__init__()
        elif status == 'local_ready':
            self.step = max(self.step, 1)
        elif status == 'ready' and self.connected:
            self.step = 2
        elif status == 'finished':
            self.finished = True
            return 'finished'
        else:
            self.show_diagnostics = True
        return None


class Diagnostics:
    def __init__(self, session=None):
        self.session = session or uuid.uuid4().hex
        self.events = []

    def record(self, action, status, details):
        self.events.append({'timestamp': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                            'action': action, 'status': status, 'details': details})
        del self.events[:-50]

    def text(self):
        report = {'schema_version': 1, 'helper_build': runtime_build(), 'windows': platform.version(),
                  'architecture': platform.machine(), 'events': self.events}
        return ('ChemDraw MCP setup diagnostics\nNo drawings or connection keys are included. '
                'Raw error text and personal paths are omitted.\n\n'
                + json.dumps(report, indent=2, sort_keys=True) + '\n')

    def autosave(self, directory):
        if not re.fullmatch(r'[A-Za-z0-9-]{1,64}', self.session):
            raise ValueError('Invalid diagnostic session name')
        from .private_files import make_private
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f'setup-{self.session}.txt'
        temporary = target.with_name(target.name + '.tmp')
        temporary.write_text(self.text(), encoding='utf-8', newline='')
        make_private(temporary)
        os.replace(temporary, target)
        return target

    def save(self, path):
        Path(path).write_text(self.text(), encoding='utf-8', newline='')
        return Path(path)


def runtime_build():
    if getattr(sys, 'frozen', False):
        try:
            return json.loads((Path(sys.executable).parent / 'version.json').read_text(encoding='utf-8'))['version']
        except (OSError, ValueError, KeyError):
            return 'unknown'
    return 'development'


def detect_chemdraw():
    """(path, version) of the ChemDraw registered for automation, or None."""
    try:
        from .windows_native import app_location, app_metadata
        path = app_location()
        return (path, app_metadata(path).get('version', '')) if path.is_file() else None
    except Exception:
        return None


def reduced_motion(environ=None):
    """Freeze the sprite only on an explicit request (CHEMDRAW_MCP_REDUCE_MOTION=1).

    Windows "Animation effects" (SPI_GETCLIENTAREAANIMATION) is switched off on many machines and
    covers system window transitions, so it is deliberately not read here: the installer's sprite is a
    gentle reveal, not a flashing or parallax effect, and a frozen sprite looked like a broken installer.
    """
    environ = os.environ if environ is None else environ
    return environ.get('CHEMDRAW_MCP_REDUCE_MOTION') == '1'


STEPS = [
    ('Select ChemDraw', 'Setup uses the ChemDraw registered on this computer. Choose the assistants to connect.'),
    ('Connect ChemDraw', 'Start ChemDraw yourself; setup never starts or closes it.'),
    ('Connected to ChemDraw', 'The live document read passed. Finish setup to install ChemDraw MCP for this '
                              'Windows account and connect your selected assistants.'),
]


class SetupWindow:
    def __init__(self, session, *, logs, detect_app=detect_chemdraw):
        import tkinter as tk
        import tkinter.font as tkfont
        self.tk, self.session, self.logs = tk, session, Path(logs)
        self.flow, self.diagnostics = Flow(), Diagnostics()
        self.results, self.busy, self.diagnostic_file, self.save_failed = queue.Queue(), False, None, False
        self.title, self.message = STEPS[0]
        self.started, self.molecule_index, self.dot_items = time.monotonic() - .7, -1, []
        self.reduce_motion = reduced_motion()
        self.root = tk.Tk()
        self.root.title('ChemDraw MCP Setup')
        self.root.configure(bg=color('sidebar', over='sidebar'))
        self.root.resizable(False, False)
        self.s = self.root.winfo_fpixels('1i') / 96
        self.root.geometry(f'{self.px(860)}x{self.px(470)}')
        icon = Path(sys.executable).parent / 'chemdraw-mcp.ico'
        if getattr(sys, 'frozen', False) and icon.is_file():
            self.root.iconbitmap(default=str(icon))
        family = 'Segoe UI' if 'Segoe UI' in tkfont.families() else 'TkDefaultFont'
        self.fonts = {'mark': tkfont.Font(family='Consolas', size=10, weight='bold'),
                      'mono': tkfont.Font(family='Consolas', size=7, weight='bold'),
                      'headline': tkfont.Font(family=family, size=15),
                      'title': tkfont.Font(family=family, size=17, weight='bold'),
                      'body': tkfont.Font(family=family, size=10), 'small': tkfont.Font(family=family, size=8),
                      'button': tkfont.Font(family=family, size=10, weight='bold')}
        try:
            self.molecules = session.dispatch({'action': 'welcome'}).get('molecules', [])
        except Exception:
            self.molecules = []
        self.app = None
        selected = getattr(session, 'settings', {}).get('chemdraw_app')
        self.app = (Path(selected), '') if selected else detect_app()
        appdata = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming'))
        self.claude = tk.BooleanVar(value=(appdata / 'Claude').is_dir())
        self.claude_code = tk.BooleanVar(value=bool(shutil.which('claude')))
        self.codex = tk.BooleanVar(value=(Path.home() / '.codex').is_dir())
        # Other Google tools (Antigravity) create ~/.gemini too; only Gemini CLI or its settings file counts.
        self.gemini = tk.BooleanVar(value=bool(shutil.which('gemini')) or (Path.home() / '.gemini/settings.json').is_file())
        self.build()
        self.refresh()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(80, self.refresh)  # step bars need the mapped panel width
        self.tick()

    def px(self, value):
        return int(round(value * self.s))

    # ------------------------------------------------------------------ layout
    def build(self):
        tk = self.tk
        side = tk.Frame(self.root, bg=color('sidebar', over='sidebar'), width=self.px(290))
        side.pack(side='left', fill='y')
        side.pack_propagate(False)
        bg = color('sidebar', over='sidebar')
        mark = tk.Canvas(side, bg=bg, highlightthickness=0, height=self.px(46), width=self.px(250))
        mark.pack(anchor='w', padx=self.px(24), pady=(self.px(24), 0))
        x = 0
        for character in 'CHEMDRAW / MCP':
            mark.create_text(x, 0, text=character, anchor='nw', fill=color('accent', over='sidebar'), font=self.fonts['mark'])
            x += self.fonts['mark'].measure(character) + self.px(3)
        y = self.fonts['mark'].metrics('linespace') + self.px(8)
        for start, length, name in ((0, 36, 'accent'), (42, 22, 'lavender'), (70, 12, 'gold')):
            mark.create_line(self.px(start), y, self.px(start + length), y, fill=color(name, over='sidebar'), width=max(1, self.px(1)))
        self.canvas = tk.Canvas(side, bg=bg, highlightthickness=0, width=self.px(242), height=self.px(150))
        self.canvas.pack(padx=self.px(24), pady=(self.px(14), self.px(12)))
        w, h, c = self.px(242), self.px(150), color('lavender', .55, 'sidebar')
        for (x0, y0, dx, dy) in ((0, 0, 1, 1), (w - 1, h - 1, -1, -1)):
            self.canvas.create_line(x0, y0 + dy * self.px(10), x0, y0, x0 + dx * self.px(10), y0, fill=c)
        tk.Label(side, text='Natural language to\nchemical structure.', justify='left', bg=bg,
                 fg=color('cream', over='sidebar'), font=self.fonts['headline']).pack(anchor='w', padx=self.px(24))
        tk.Label(side, text='One canvas. You and your assistant.', bg=bg, fg=color('white', .55, 'sidebar'),
                 font=self.fonts['small']).pack(anchor='w', padx=self.px(24), pady=(self.px(6), 0))
        tk.Label(side, text='Created by Glenn Bojanov', bg=bg, fg=color('white', .45, 'sidebar'),
                 font=self.fonts['small']).pack(side='bottom', anchor='w', padx=self.px(24), pady=self.px(22))

        pbg = color('panel')
        self.panel = tk.Frame(self.root, bg=pbg)
        self.panel.pack(side='left', fill='both', expand=True)
        self.bars = tk.Canvas(self.panel, bg=pbg, highlightthickness=0, height=self.px(6))
        self.bars.pack(fill='x', padx=self.px(26), pady=(self.px(26), 0))
        self.step_holder = tk.Frame(self.panel, bg=pbg)
        self.step_holder.pack(fill='x', padx=self.px(26), pady=(self.px(12), 0))
        self.title_label = tk.Label(self.panel, bg=pbg, fg=color('cream'), font=self.fonts['title'], anchor='w',
                                    justify='left', wraplength=self.px(500))
        self.title_label.pack(fill='x', padx=self.px(26), pady=(self.px(4), 0))
        self.message_label = tk.Label(self.panel, bg=pbg, fg=color('white', .72), font=self.fonts['body'], anchor='w',
                                      justify='left', wraplength=self.px(500))
        self.message_label.pack(fill='x', padx=self.px(26), pady=(self.px(4), self.px(8)))
        self.content = tk.Frame(self.panel, bg=color('white', .05))
        self.content.pack(fill='x', padx=self.px(26))
        footer = tk.Frame(self.panel, bg=pbg)
        footer.pack(side='bottom', fill='x', padx=self.px(26), pady=(0, self.px(18)))
        tk.Label(footer, text='Requires licensed ChemDraw. Experimental Windows build.', bg=pbg,
                 fg=color('white', .4), font=self.fonts['small']).pack(side='left')
        actions = tk.Frame(self.panel, bg=pbg)
        actions.pack(side='bottom', fill='x', padx=self.px(26), pady=(0, self.px(10)))
        self.diagnostic_row = tk.Frame(actions, bg=pbg)
        self.diagnostic_row.pack(side='left')
        self.primary = tk.Canvas(actions, bg=pbg, highlightthickness=0, cursor='hand2')
        self.primary.pack(side='right')
        self.primary.bind('<Button-1>', lambda event: self.primary_action())
        self.primary_text = ''

    def draw_primary(self, text):
        """PrimaryButton: rounded accent fill, dark label; muted while busy."""
        canvas, radius = self.primary, self.px(6)
        width = self.fonts['button'].measure(text) + 2 * self.px(18)
        height = self.fonts['button'].metrics('linespace') + 2 * self.px(9)
        canvas.config(width=width, height=height)
        canvas.delete('all')
        fill = color('white', .08) if self.busy else color('accent')
        for x0, y0 in ((0, 0), (width - 2 * radius, 0), (0, height - 2 * radius), (width - 2 * radius, height - 2 * radius)):
            canvas.create_oval(x0, y0, x0 + 2 * radius, y0 + 2 * radius, fill=fill, outline=fill)
        canvas.create_rectangle(radius, 0, width - radius, height, fill=fill, outline=fill)
        canvas.create_rectangle(0, radius, width, height - radius, fill=fill, outline=fill)
        canvas.create_text(width / 2, height / 2, text=text, font=self.fonts['button'],
                           fill=color('cream', .35) if self.busy else '#261a29')
        self.primary_text = text

    def tracked(self, parent, text, font, fill, spacing):
        """Letter-spaced label like SwiftUI .tracking(), drawn on a canvas."""
        canvas = self.tk.Canvas(parent, bg=parent['bg'], highlightthickness=0,
                                height=self.fonts[font].metrics('linespace'), width=self.px(480))
        x = 0
        for character in text:
            canvas.create_text(x, 0, text=character, anchor='nw', fill=fill, font=self.fonts[font])
            x += self.fonts[font].measure(character) + spacing
        return canvas

    def checkbox(self, parent, text, variable):
        """ThemeCheckbox: accent square with a checkmark, lavender outline."""
        row = self.tk.Frame(parent, bg=parent['bg'], cursor='hand2')
        size = self.px(15)
        box = self.tk.Canvas(row, width=size + 2, height=size + 2, bg=parent['bg'], highlightthickness=0)
        box.pack(side='left', padx=(0, self.px(8)))
        label = self.tk.Label(row, text=text, bg=parent['bg'], fg=color('cream'), font=self.fonts['body'])
        label.pack(side='left')

        def draw():
            box.delete('all')
            on = variable.get()
            box.create_rectangle(1, 1, size, size, outline=color('lavender', .65),
                                 fill=color('accent') if on else color('white', .08))
            if on:
                box.create_line(size * .25, size * .52, size * .43, size * .72, size * .78, size * .3,
                                fill=color('sidebar'), width=max(2, self.px(2)), capstyle='round', joinstyle='round')

        def toggle(event=None):
            variable.set(not variable.get())
            draw()
        for widget in (row, box, label):
            widget.bind('<Button-1>', toggle)
        draw()
        return row

    def link(self, parent, text, command, bg=None):
        label = self.tk.Label(parent, text=text, bg=bg or parent['bg'], fg=color('accent'), cursor='hand2',
                              font=self.fonts['small'])
        label.bind('<Button-1>', lambda event: command())
        return label

    def line(self, parent, text, fg=None, font='body'):
        return self.tk.Label(parent, text=text, bg=parent['bg'], fg=fg or color('cream'), anchor='w', justify='left',
                             wraplength=self.px(470), font=self.fonts[font])

    def refresh(self):
        step = 2 if self.flow.finished else self.flow.step
        self.bars.delete('all')
        width = max(self.bars.winfo_width(), self.px(500))
        part = (width - 2 * self.px(10)) / 3
        for index in range(3):
            x0 = index * (part + self.px(10))
            filled = index <= step if not self.flow.finished else True
            self.bars.create_line(x0 + 2, self.px(3), x0 + part - 2, self.px(3), width=self.px(3), capstyle='round',
                                  fill=color('accent') if filled else color('white', .13))
        for child in self.step_holder.winfo_children():
            child.destroy()
        self.tracked(self.step_holder, 'DONE' if self.flow.finished else f'STEP {step + 1} OF 3', 'mono',
                     color('accent'), self.px(3)).pack(anchor='w')
        self.title_label.config(text=self.title)
        self.message_label.config(text=self.message)
        for child in self.content.winfo_children():
            child.destroy()
        box = self.content
        pad = {'padx': self.px(12), 'pady': (self.px(3), 0)}
        if self.flow.finished:
            settings = getattr(self.session, 'settings', {})
            self.line(box, 'Installed for this Windows account; no administrator rights were used.').pack(fill='x', **pad)
            if settings.get('installed_runtime'):
                self.line(box, settings['installed_runtime'], color('gold'), 'small').pack(fill='x', **pad)
            self.line(box, 'Restart the connected apps; in a terminal assistant, start a new session.').pack(fill='x', **pad)
            claude_code = settings.get('claude_code') or {}
            if claude_code.get('status') in ('added', 'unchanged'):
                self.line(box, 'Claude Code is connected.', color('lavender')).pack(fill='x', **pad)
            elif claude_code.get('command'):
                self.line(box, claude_code.get('message', 'Connect Claude Code with:'), color('white', .7), 'small').pack(fill='x', **pad)
                self.command_line(box, claude_code['command'])
            runtime = settings.get('runtime_command')
            if runtime:
                self.line(box, 'Any other MCP client: add a local (stdio) server with this command:',
                          color('white', .7), 'small').pack(fill='x', **pad)
                self.command_line(box, f'"{runtime}" --desktop-serve')
            self.line(box, 'In a new terminal, run: chemdraw-mac doctor', color('lavender')).pack(fill='x', **pad)
            self.draw_primary('Close')
        elif self.flow.step == 0:
            name = f'{self.app[0]}' + (f'  ({self.app[1]})' if self.app and self.app[1] else '') if self.app else 'ChemDraw was not found.'
            self.line(box, name, color('gold'), 'small').pack(fill='x', **pad)
            self.link(box, 'Choose ChemDraw.exe…', self.choose_app).pack(anchor='w', padx=self.px(12))
            self.tracked(box, 'CONNECT TO', 'mono', color('lavender'), self.px(2)).pack(
                anchor='w', padx=self.px(12), pady=(self.px(10), self.px(4)))
            for _, text, variable in self.choices():
                self.checkbox(box, text, variable).pack(anchor='w', padx=self.px(12), pady=self.px(2))
            self.line(box, 'Choose any, or none for the chemdraw-mac terminal command only. One shared installation.',
                      color('white', .55), 'small').pack(fill='x', padx=self.px(12), pady=(0, self.px(8)))
            self.draw_primary('Check software')
        elif self.flow.step == 1:
            for text in ('1. Open ChemDraw.', '2. Choose File > New. A blank drawing is fine.',
                         '3. Click Test connection. It reads the drawing without changing it.'):
                self.line(box, text).pack(fill='x', **pad)
            self.line(box, 'Close any open ChemDraw dialog first. Your drawings are never saved or closed by setup.',
                      color('white', .55), 'small').pack(fill='x', padx=self.px(12), pady=(self.px(4), self.px(8)))
            self.draw_primary('Test connection')
        else:
            chosen = [text for _, text, variable in self.choices() if variable.get()]
            self.line(box, 'Connect: ' + (', '.join(chosen) if chosen else 'terminal only')).pack(fill='x', **pad)
            self.line(box, 'Existing assistant settings are kept and backed up. Your ChemDraw stays as it is.',
                      color('white', .55), 'small').pack(fill='x', padx=self.px(12), pady=(self.px(4), self.px(8)))
            self.style_section(box)
            self.draw_primary('Finish setup')
        self.draw_primary(self.primary_text)
        for child in self.diagnostic_row.winfo_children():
            child.destroy()
        if self.busy:
            self.line(self.diagnostic_row, 'Working…', color('lavender'), 'small').pack(side='left')
        elif self.diagnostics.events:
            note = ('Automatic log save failed. Use Save diagnostics.' if self.save_failed else 'Diagnostics saved privately.')
            self.line(self.diagnostic_row, note, color('white', .55), 'small').pack(side='left')
            self.link(self.diagnostic_row, 'Save diagnostics…', self.save_diagnostics).pack(side='left', padx=(self.px(8), 0))
            if self.diagnostic_file:
                self.link(self.diagnostic_row, 'Open folder', lambda: os.startfile(self.logs)).pack(side='left', padx=(self.px(8), 0))

    # ------------------------------------------------------------------ actions
    def primary_action(self):
        if self.busy:
            return
        if self.flow.finished:
            return self.close()
        if self.flow.step == 0:
            return self.run_action({'action': 'check'})
        if self.flow.step == 1:
            return self.run_action({'action': 'test'})
        clients = [key for key, _, variable in self.choices() if variable.get()]
        return self.run_action({'action': 'finish', 'clients': clients})

    def choices(self):
        return (('claude', 'Claude Desktop', self.claude), ('claude-code', 'Claude Code (terminal)', self.claude_code),
                ('codex', 'Codex (app and CLI)', self.codex), ('gemini', 'Gemini CLI', self.gemini))

    def command_line(self, box, command):
        """A command the user may need to run or paste elsewhere, with a copy link."""
        row = self.tk.Frame(box, bg=box['bg'])
        row.pack(fill='x', padx=self.px(12), pady=(self.px(2), 0))
        self.line(row, command, color('gold'), 'small').pack(side='left', fill='x', expand=True)

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(command)
        self.link(row, 'Copy', copy).pack(side='left', padx=(self.px(8), 0))

    def style_section(self, box):
        """Default drawing style: the built-in house style, or the numbers of a ChemDraw style file."""
        chosen = getattr(self.session, 'settings', {}).get('default_style')
        self.tracked(box, 'DRAWING STYLE', 'mono', color('lavender'), self.px(2)).pack(
            anchor='w', padx=self.px(12), pady=(0, self.px(4)))
        if chosen:
            try:
                p = chosen['preset']
                summary = f"{p['font']}, {float(p['LabelSize']):g} pt labels, {float(p['LineWidth']):.2f} pt bonds"
            except (KeyError, TypeError, ValueError):
                summary = 'The saved style could not be read; choose it again.'
            self.line(box, str(chosen.get('name', '')), color('gold'), 'small').pack(fill='x', padx=self.px(12))
            self.line(box, summary, color('white', .55), 'small').pack(fill='x', padx=self.px(12))
        else:
            self.line(box, 'Built-in house style', color('gold'), 'small').pack(fill='x', padx=self.px(12))
        row = self.tk.Frame(box, bg=box['bg'])
        row.pack(anchor='w', padx=self.px(12), pady=(self.px(2), self.px(8)))
        self.link(row, 'Choose a ChemDraw style (.cds, .cdxml)…', self.choose_style).pack(side='left')
        if chosen:
            self.link(row, 'Use built-in', self.use_builtin_style).pack(side='left', padx=(self.px(12), 0))

    def choose_style(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title='Choose a ChemDraw style for new drawings',
                                          filetypes=[('ChemDraw style', '*.cds *.cdxml *.cdx')])
        if path:
            self.run_action({'action': 'choose_style', 'path': path})

    def use_builtin_style(self):
        self.run_action({'action': 'clear_style'})

    def choose_app(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title='Choose ChemDraw.exe', filetypes=[('ChemDraw', 'ChemDraw.exe'), ('Programs', '*.exe')])
        if path:
            self.run_action({'action': 'choose_app', 'path': path})

    def save_diagnostics(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(title='Save diagnostics', defaultextension='.txt',
                                            initialfile='chemdraw-mcp-setup.txt', filetypes=[('Text', '*.txt')])
        if path:
            self.diagnostics.save(path)

    def run_action(self, request):
        if self.busy:
            return
        self.busy = True
        self.refresh()

        def work():
            try:
                value = self.session.dispatch(request)
            except Exception as exc:
                from .desktop_setup import diagnostic_details
                value = {'status': 'error', 'title': 'Setup needs attention', 'message': str(exc),
                         'details': diagnostic_details({'status': 'error'}, exception=exc)}
            self.results.put((request, value))
        threading.Thread(target=work, daemon=True).start()
        self.root.after(40, self.poll)

    def poll(self):
        try:
            request, value = self.results.get_nowait()
        except queue.Empty:
            self.root.after(40, self.poll)
            return
        self.busy = False
        self.handle(request, value)

    def handle(self, request, value):
        status = value.get('status', 'error')
        self.diagnostics.record(request['action'], status, value.get('details', {}))
        try:
            self.diagnostic_file, self.save_failed = self.diagnostics.autosave(self.logs), False
        except (OSError, ValueError):
            self.save_failed = True
        if request['action'] == 'choose_app' and status == 'selected':
            self.app = (Path(value['app']), '')
        if status in STYLE_STATUSES:  # the choice lives in the session settings; keep title and step
            self.refresh()
            return
        self.flow.receive(value)
        if self.flow.finished:
            self.title, self.message = 'Setup complete', 'ChemDraw MCP is ready.'
        elif status in ('selected', 'local_ready') or (status == 'ready' and self.flow.connected):
            self.title, self.message = STEPS[self.flow.step]
            if status == 'local_ready' and value.get('message'):
                self.message = value['message']
        else:
            self.title = value.get('title', 'Setup needs attention')
            self.message = value.get('message', '')
        self.refresh()

    def close(self):
        try:
            self.session.close()
        finally:
            self.root.destroy()

    # ------------------------------------------------------------------ animation
    def animate_once(self, elapsed):
        if not self.molecules:
            return
        index = 0 if self.reduce_motion else int(elapsed / CYCLE) % len(self.molecules)
        if index != self.molecule_index:
            self.molecule_index = index
            self.canvas.delete('dot')
            sprite = max(self.molecules[index]['sprites'], key=lambda s: s['width'])
            points, scale, left, top = sprite_layout(sprite_dots(sprite), int(self.canvas['width']), int(self.canvas['height']))
            self.dot_items = sorted(
                (x, self.canvas.create_oval(left + x * scale, top + y * scale, left + x * scale + scale * .9,
                                            top + y * scale + scale * .9, fill=color('cream', over='sidebar'),
                                            outline='', state='hidden', tags='dot')) for x, y in points)
            self.width_units = max(x for x, _ in points) if points else 0
        sweep = (self.width_units + 10 if self.reduce_motion else
                 min(1.0, (elapsed % CYCLE) / SWEEP) * (self.width_units + 8))
        cream, gold = color('cream', over='sidebar'), color('gold', over='sidebar')
        for x, item in self.dot_items:
            if x >= sweep:
                self.canvas.itemconfigure(item, state='hidden')
            else:
                self.canvas.itemconfigure(item, state='normal', fill=gold if sweep - x < 8 else cream)

    def tick(self):
        try:
            self.animate_once(time.monotonic() - self.started)
        except self.tk.TclError:
            return
        if not self.reduce_motion:
            self.root.after(int(1000 / FPS), self.tick)


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # crisp text at 125-200 % display scaling
    except Exception:
        pass
    from .desktop_setup import SetupSession
    from .windows_install import Paths
    window = SetupWindow(SetupSession(), logs=Paths().logs)
    window.root.mainloop()
    return 0
