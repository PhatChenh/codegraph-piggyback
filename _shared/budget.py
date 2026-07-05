"""_shared.budget — budgeted-emit helper (frozen invariant: output never
exceeds its budget; overflow collapses to counts)."""

from __future__ import annotations


def emit_budgeted(lines: list[str], max_lines: int,
                  collapse_label: str = "more") -> list[str]:
    """Keep the first `max_lines` lines (callers pre-sort worst-first); collapse
    the remainder to one count line. Never returns more than max_lines + 1."""
    if max_lines <= 0 or len(lines) <= max_lines:
        return list(lines)
    kept = lines[:max_lines]
    kept.append(f"  … +{len(lines) - max_lines} {collapse_label} (truncated to budget)")
    return kept
