"""One temporary themed terminal surface for the entire setup conversation."""
import shutil
import sys
import termios
import textwrap
import threading
import time

from .welcome import load_molecules

PINK = '38;5;218'
LAVENDER = '38;5;183'
GOLD = '38;5;222'
INK = '38;5;255'
# Use the same indexed palette as foregrounds, including in Apple Terminal.
# Reset inherited dim/reverse attributes before painting each frame.
BACKGROUND = '\x1b[0m\x1b[48;5;235m'


def wrapped(body, width):
    return [line for paragraph in body for line in
            (textwrap.wrap(''.join(c if c.isprintable() else ' ' for c in paragraph),
                           width=max(1, width)) or [''])]


def ink_rows(sprite):
    points = [(x, y) for y, row in enumerate(sprite['rows']) for x, c in enumerate(row)
              if c not in (' ', '\u2800')]
    if not points: return []
    xs, ys = zip(*points)
    return [row.ljust(max(xs) + 1)[min(xs):max(xs) + 1]
            for row in sprite['rows'][min(ys):max(ys) + 1]]


def setup_frame(width, height, seconds, title, body, prompt):
    width, height = max(1, width), max(1, height)
    canvas = [[' '] * width for _ in range(height)]
    colors = [[INK] * width for _ in range(height)]
    split = max(26, min(50, width // 3))
    right = split + 4
    def put(x, y, text, color=INK):
        for offset, char in enumerate(text):
            if 0 <= y < height and 0 <= x + offset < width:
                canvas[y][x + offset], colors[y][x + offset] = char, color
    put(2, 1, 'CHEMDRAW / MCP', PINK)
    put(2, 3, '━━━━━━  ────  ──', LAVENDER)
    for y in range(1, height - 1): put(split, y, '│', LAVENDER)
    molecules = load_molecules()
    molecule = molecules[int(seconds / 4) % len(molecules)]
    sprites = [ink_rows(s) for s in molecule['sprites']]
    sprites = [rows for rows in sprites if rows and len(rows[0]) <= split - 4 and len(rows) <= height - 12]
    if sprites:
        rows = max(sprites, key=lambda rows: len(rows) * len(rows[0]))
        left = (split - len(rows[0])) // 2
        top = 5 + max(0, (height - 13 - len(rows)) // 2)
        reveal = min(1, (seconds % 4) / .9) * (len(rows[0]) + 4)
        for y, row in enumerate(rows):
            for x, char in enumerate(row):
                if x < reveal: put(left + x, top + y, char, GOLD if reveal - x < 4 else INK)
    put(2, height - 6, 'Natural language', INK)
    put(2, height - 5, 'to chemical structure.', INK)
    put(2, height - 2, 'Created by Glenn Bojanov', LAVENDER)
    put(right, 1, 'TERMINAL SETUP', LAVENDER)
    for y, line in enumerate(wrapped([title], width - right - 2), 3): put(right, y, line, PINK)
    lines = wrapped(body, width - right - 2)
    available = max(0, height - 11)
    for y, line in enumerate(lines[:available], 6): put(right, y, line)
    if len(lines) > available:
        put(right, height - 4, 'Enlarge this window to read all steps.', GOLD)
    for y, line in enumerate(wrapped([prompt], width - right - 2)[:2], height - 3): put(right, y, line, PINK)
    result = []
    for row, palette in zip(canvas, colors):
        parts, previous = [], None
        for char, color in zip(row, palette):
            if previous != color: parts.append(f'\x1b[{color}m'); previous = color
            parts.append(char)
        result.append(''.join(parts))
    return BACKGROUND + '\n'.join(result)


class SetupScreen:
    def __init__(self, stream, enabled):
        self.stream, self.enabled = stream, enabled
        self.title, self.body, self.prompt = 'Starting setup', [], 'Ctrl-C to stop'
        self.lock, self.stop = threading.RLock(), threading.Event()
        self.thread = None

    def __enter__(self):
        self.started = time.monotonic()
        if self.enabled:
            self.stream.write('\x1b[?1049h\x1b[?25l' + BACKGROUND + '\x1b[2J')
            self.draw()
            self.thread = threading.Thread(target=self.animate, daemon=True)
            self.thread.start()
        return self

    def show(self, title, body=(), prompt='Ctrl-C to stop'):
        with self.lock:
            self.title, self.body, self.prompt = title, list(body), prompt
            if self.enabled: self.draw()
            else: print(title + '\n' + '\n'.join(body), file=self.stream, flush=True)

    def draw(self):
        with self.lock:
            size = shutil.get_terminal_size((100, 32))
            frame = setup_frame(size.columns - 1, size.lines - 1, time.monotonic() - self.started,
                                self.title, self.body, self.prompt)
            self.stream.write('\x1b[H' + frame.replace('\n', '\r\n'))
            self.stream.flush()

    def animate(self):
        while not self.stop.wait(.08): self.draw()

    def wait(self, input_fn, prompt):
        if self.enabled:
            size = shutil.get_terminal_size((100, 32))
            width, height = size.columns - 1, size.lines - 1
            split = max(26, min(50, width // 3))
            lines = wrapped(self.body, width - split - 6)
            capacity = max(1, height - 11)
            pages = [lines[i:i + capacity] for i in range(0, len(lines), capacity)] or [[]]
        else:
            pages = [self.body]
        original = None
        try:
            if self.enabled and input_fn is input and sys.stdin.isatty():
                original = termios.tcgetattr(sys.stdin.fileno())
                quiet = list(original)
                quiet[3] &= ~termios.ECHO
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, quiet)
            for index, body in enumerate(pages):
                hint = prompt if index == len(pages) - 1 else 'Return for more  /  Ctrl-C to stop'
                self.show(self.title, body, hint)
                result = input_fn('' if self.enabled else hint + ': ')
            return result
        finally:
            if original is not None:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, original)

    def __exit__(self, *exc):
        self.stop.set()
        if self.thread is not None: self.thread.join()
        if self.enabled:
            self.stream.write('\x1b[0m\x1b[?25h\x1b[?1049l')
            self.stream.flush()
