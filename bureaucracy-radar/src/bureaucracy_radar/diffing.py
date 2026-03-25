from __future__ import annotations

from dataclasses import dataclass
import difflib


@dataclass
class DiffResult:
    changed: bool
    summary: str
    diff_text: str


def compare_text(previous: str, current: str, max_lines: int = 40) -> DiffResult:
    previous_lines = previous.splitlines()
    current_lines = current.splitlines()

    if previous_lines == current_lines:
        return DiffResult(changed=False, summary="Nenhuma mudança detectada.", diff_text="")

    diff_lines = list(
        difflib.unified_diff(
            previous_lines,
            current_lines,
            fromfile="previous",
            tofile="current",
            lineterm="",
        )
    )
    clipped = diff_lines[:max_lines]
    summary = f"Mudança detectada: {len(current_lines) - len(previous_lines)} linhas de diferença líquida."
    return DiffResult(changed=True, summary=summary, diff_text="\n".join(clipped))
