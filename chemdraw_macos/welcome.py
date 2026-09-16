"""Fixed native-ChemDraw silhouettes for interactive first-run onboarding.

No drawing, network, image library or font dependency at animation time.
"""
from functools import lru_cache
from importlib.resources import files
import json
import math


@lru_cache(maxsize=1)
def load_molecules():
    return json.loads(files('chemdraw_macos').joinpath('data/welcome.json').read_text(encoding='utf-8'))['molecules']


def phase_progress(stage, elapsed):
    # These are phase weights, NOT estimates of elapsed installation time.
    # Motion approaches a phase ceiling; only verified completion reaches 1.
    start, ceiling = {'installation': (0, .12), 'connection': (.12, .24),
                      'drawing': (.24, .88), 'exports': (.88, .98),
                      'complete': (1, 1)}.get(stage, (0, .05))
    return start + (ceiling - start) * (1 - math.exp(-max(0, elapsed) / 5))


def progress_bar(fraction, width):
    units = int(max(0, min(1, fraction)) * width * 8)
    full, remainder = divmod(units, 8)
    partial = '▏▎▍▌▋▊▉'[remainder - 1] if remainder else ''
    return '█' * full + partial + '░' * (width - full - bool(remainder))


def frame(width, height, seconds, stage, label, progress):
    canvas = [[' '] * width for _ in range(height)]
    colors = [[37] * width for _ in range(height)]
    def centered(y, value, color=37):
        if not 0 <= y < height:
            return
        value = value[:width]
        left = max(0, (width - len(value)) // 2)
        for x, char in enumerate(value, left):
            canvas[y][x], colors[y][x] = char, color
    centered(1, 'C H E M D R A W   /   M C P', '38;5;218')
    if stage == 'complete':
        centered(height // 2 - 1, 'Welcome to ChemDraw MCP')
        centered(height // 2 + 1, 'Natural language → ChemDraw', '38;5;183')
    else:
        molecules = load_molecules()
        index = int(max(0, seconds) / 1.4) % len(molecules)
        sprites = [s for s in molecules[index]['sprites']
                   if s['width'] <= width - 4 and s['height'] <= height - 9]
        art = max(sprites, key=lambda s: s['width'] * s['height'])['rows'] if sprites else []
        top = 3 + max(0, (height - 9 - len(art)) // 2)
        art_width = len(art[0]) if art else 0
        left = max(0, (width - art_width) // 2)
        reveal = min(1, (seconds % 1.4) / .476) * (art_width + 4)
        for y, line in enumerate(art, top):
            for x, char in enumerate(line):
                if x < reveal:
                    canvas[y][left + x] = char
                    colors[y][left + x] = '38;5;222' if reveal - x < 4 else 37
        centered(height - 5, 'Natural language → ChemDraw', '38;5;183')
    centered(height - 3, progress_bar(progress, min(40, max(1, width - 8))), '38;5;218')
    centered(height - 1, ''.join(c if c.isprintable() else ' ' for c in label), 90)
    output = []
    for y, line in enumerate(canvas):
        previous = None
        row = []
        for x, char in enumerate(line):
            color = colors[y][x]
            if color != previous:
                row.append(f'\x1b[{color}m')
                previous = color
            row.append(char)
        output.append(''.join(row))
    return '\n'.join(output)
