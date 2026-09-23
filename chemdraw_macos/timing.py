"""Per-call wall-clock measurements; no global state or estimated progress."""
from time import perf_counter


class StageTimer:
    def __init__(self):
        self.started = self.previous = perf_counter()
        self.stages = {}

    def mark(self, name):
        now = perf_counter()
        self.stages[name] = self.stages.get(name, 0.0) + now - self.previous
        self.previous = now

    def report(self):
        return {'total_seconds': perf_counter() - self.started,
                'stages_seconds': dict(self.stages),
                'scope': 'server workflow only; excludes assistant reasoning and client review'}
