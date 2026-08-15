"""Extract conservative role/fix evidence from positioned IAP OCR output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_ROLE_NAMES = frozenset({"IAF", "IF", "FAF", "MAP", "MAPT"})
_BOX_SUFFIX = re.compile(
    r"^(?P<text>.*?)(?:\s*)\[\["
    r"(?P<x0>-?\d+(?:\.\d+)?),\s*"
    r"(?P<y0>-?\d+(?:\.\d+)?),\s*"
    r"(?P<x1>-?\d+(?:\.\d+)?),\s*"
    r"(?P<y1>-?\d+(?:\.\d+)?)"
    r"\]\]\s*$"
)


@dataclass(frozen=True)
class IapOcrRoleEvidence:
    """One explicit OCR role/fix pairing from a source PDF page."""

    page: int
    ident: str
    role: str
    relation: str

    def to_report(self) -> dict[str, object]:
        return {
            "page": self.page,
            "ident": self.ident,
            "role": self.role,
            "relation": self.relation,
        }


@dataclass(frozen=True)
class _PositionedText:
    text: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float


def _exact_role(text: str) -> str | None:
    role = text.strip().upper()
    return role if role in _ROLE_NAMES else None


def _inline_roles(text: str, identifiers: set[str]) -> tuple[tuple[str, str], ...]:
    """Read only standalone role words and explicitly printed identifiers."""
    upper = text.upper()
    roles = [
        role
        for role in _ROLE_NAMES
        if re.search(rf"(?<![A-Z0-9/]){role}(?![A-Z0-9/])", upper)
    ]
    idents = [
        ident
        for ident in identifiers
        if re.search(rf"(?<![A-Z0-9]){re.escape(ident)}(?![A-Z0-9])", upper)
    ]
    return tuple((ident, role) for role in sorted(roles) for ident in sorted(idents))


def _positioned_texts(markdown: str, page: int) -> tuple[_PositionedText, ...]:
    result: list[_PositionedText] = []
    for raw_line in markdown.splitlines():
        match = _BOX_SUFFIX.fullmatch(raw_line.strip())
        if match is None:
            continue
        text = match["text"].strip()
        if not text:
            continue
        result.append(_PositionedText(
            text=text,
            page=page,
            x0=float(match["x0"]),
            y0=float(match["y0"]),
            x1=float(match["x1"]),
            y1=float(match["y1"]),
        ))
    return tuple(result)


def _horizontal_gap(first: _PositionedText, second: _PositionedText) -> float:
    return max(first.x0 - second.x1, second.x0 - first.x1, 0.0)


def _vertical_gap(first: _PositionedText, second: _PositionedText) -> float:
    return max(first.y0 - second.y1, second.y0 - first.y1, 0.0)


def _relation(role: _PositionedText, fix: _PositionedText) -> tuple[str, float] | None:
    """Return a strict rendered adjacency relation, or no relationship."""
    row_delta = abs(((role.y0 + role.y1) / 2) - ((fix.y0 + fix.y1) / 2))
    horizontal_gap = _horizontal_gap(role, fix)
    if _vertical_gap(role, fix) <= 3 and row_delta <= 18 and horizontal_gap <= 160:
        return "same_row", row_delta + horizontal_gap

    horizontal_overlap = min(role.x1, fix.x1) - max(role.x0, fix.x0)
    vertical_gap = _vertical_gap(role, fix)
    if horizontal_overlap >= -6 and vertical_gap <= 48:
        return "vertical_stack", vertical_gap + max(-horizontal_overlap, 0.0)
    return None


def extract_iap_ocr_role_evidence(
    pages: Iterable[tuple[int, str]],
    leg_idents: Iterable[str],
) -> tuple[IapOcrRoleEvidence, ...]:
    """Return explicit, source-only role/fix pairings from OCR text positions.

    OCR output is not permitted to infer procedure geometry.  This parser
    therefore accepts only a standalone role label and a current database-leg
    identifier that occur in one OCR item or a narrowly bounded rendered
    relationship.  The result remains audit evidence and is not projectable.
    """
    identifiers = {
        ident.strip().upper()
        for ident in leg_idents
        if ident and ident.strip()
    }
    if not identifiers:
        return ()

    strongest: dict[tuple[int, str, str], tuple[int, float, str]] = {}

    def retain(
        page: int,
        ident: str,
        role: str,
        relation: str,
        *,
        distance: float,
    ) -> None:
        priority = {
            "same_ocr_item": 0,
            "same_row": 1,
            "vertical_stack": 2,
        }[relation]
        key = (page, ident, role)
        candidate = (priority, distance, relation)
        if key not in strongest or candidate < strongest[key]:
            strongest[key] = candidate

    for page, markdown in pages:
        positioned = _positioned_texts(markdown, page)
        for item in positioned:
            for ident, role in _inline_roles(item.text, identifiers):
                retain(page, ident, role, "same_ocr_item", distance=0.0)

        roles = [
            (item, role)
            for item in positioned
            if (role := _exact_role(item.text)) is not None
        ]
        fixes = [
            (item, item.text.strip().upper())
            for item in positioned
            if item.text.strip().upper() in identifiers
        ]
        for role_item, role in roles:
            candidates: list[tuple[float, str, str]] = []
            for fix_item, ident in fixes:
                relation = _relation(role_item, fix_item)
                if relation is not None:
                    relation_name, distance = relation
                    candidates.append((distance, ident, relation_name))
            if candidates:
                distance, ident, relation_name = min(candidates)
                retain(page, ident, role, relation_name, distance=distance)

    return tuple(sorted(
        (
            IapOcrRoleEvidence(page, ident, role, relation)
            for (page, ident, role), (_, _, relation) in strongest.items()
        ),
        key=lambda item: (item.page, item.ident, item.role, item.relation),
    ))
