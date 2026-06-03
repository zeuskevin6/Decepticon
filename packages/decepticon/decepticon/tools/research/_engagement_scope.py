"""Research-package re-export of engagement scope helpers.

The contextvar and validator moved to
``decepticon_core.utils.engagement_scope`` so they survive the removal
of this package. ``with_engagement_property`` stays here because it is
research-specific (it tags Neo4j property dicts) and goes away with the
rest of the package.
"""

from __future__ import annotations

from decepticon_core.utils.engagement_scope import (
    _active_engagement,
    get_active_engagement,
    is_valid_engagement_label,
    reset_active_engagement,
    set_active_engagement,
)

__all__ = [
    "_active_engagement",
    "get_active_engagement",
    "is_valid_engagement_label",
    "reset_active_engagement",
    "set_active_engagement",
    "with_engagement_property",
]


_LEGACY_ENGAGEMENT_LABEL = "_legacy"


def with_engagement_property(props: dict | None, *, override: str | None = None) -> dict:
    """Return ``props`` with an ``engagement`` key set to the right label.

    Precedence (first non-empty wins): ``override`` (caller pins it) → an
    ``engagement`` already on ``props`` → the active engagement → the legacy
    label. Preserving an existing ``engagement`` is the multi-tenant safety
    invariant: it stops a ``graph_transaction`` save-back from relabelling a
    loaded node onto the current (or ``_legacy``) engagement on a shared
    Neo4j. See docs/security/neo4j-hardening.md.
    """
    out = dict(props or {})
    engagement = (
        override or out.get("engagement") or get_active_engagement() or _LEGACY_ENGAGEMENT_LABEL
    )
    out["engagement"] = engagement
    return out
