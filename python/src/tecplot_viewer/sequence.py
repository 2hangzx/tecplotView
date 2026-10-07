"""Navigation through a user-controlled file collection; no time inference."""
from dataclasses import dataclass, field

from .scan_dat import DatFile, natural_key


@dataclass
class FileSequence:
    files: list[DatFile] = field(default_factory=list)
    current: str | None = None

    def ordered(self, *, reverse=False, selected=None):
        items = sorted(self.files, key=lambda item: natural_key(item.relative_path), reverse=reverse)
        if selected is not None:
            items = [item for item in items if item.relative_path in selected]
        return items

    def target(self, direction=1, *, reverse=False, selected=None, loop=False):
        items = self.ordered(reverse=reverse, selected=selected)
        if not items:
            return None
        current = next((n for n, item in enumerate(items) if item.relative_path == self.current), None)
        if current is None:
            return items[0 if direction > 0 else -1]
        index = current + direction
        if loop:
            index %= len(items)
        return items[index] if 0 <= index < len(items) else None
