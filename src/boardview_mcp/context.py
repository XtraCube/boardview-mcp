"""Startup-time board context: the file is parsed once, indexed once, and shared by every tool."""

from __future__ import annotations

import difflib
import fnmatch
import re

from .parser import parse_file
from .graph import ConnectivityGraph
from .classify import classify_component, PASSIVE_KINDS

MAX_DEFAULT_SCAN = 200
SEARCH_WINDOW_MAX = 500


def _clamp(value: object, lo: int, hi: int) -> int:
    try:
        n = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))


class BoardContext:
    def __init__(self, path: str, *, max_bytes: int | None = None) -> None:
        kwargs = {"max_bytes": max_bytes} if max_bytes else {}
        self.path: str = path
        self.board = parse_file(path, **kwargs)  # type: ignore[arg-type]
        self.graph = ConnectivityGraph(self.board)
        # classification is computed once per component so tools stay cheap and consistent
        self.classified: dict[str, dict] = {
            ref: classify_component(comp, self.board.devices)
            for ref, comp in self.board.components.items()
        }
        self.bridgeable: dict[str, dict] = {
            ref: self.graph.bridge_eligibility(ref) for ref in self.board.components
        }
        self._fold: dict[str, str] = {}
        for key in list(self.board.components) + list(self.board.nets) + list(self.board.shapes) + list(self.board.devices):
            self._fold.setdefault(key.lower(), key)

    # ---------------------------------------------------------------- name resolution

    def resolve_component(self, ref: str) -> tuple[str | None, list[str]]:
        """Exact match wins; otherwise a single case-insensitive match is accepted. Ambiguity is reported."""
        if ref in self.board.components:
            return ref, []
        cands = self._candidates(ref, self.board.components)
        if len(cands) == 1:
            return cands[0], [f"case-insensitive match for {ref!r} -> {cands[0]}"]
        return None, cands

    def resolve_net(self, name: str) -> tuple[str | None, list[str]]:
        if name in self.board.nets:
            return name, []
        cands = self._candidates(name, self.board.nets)
        if len(cands) == 1:
            return cands[0], [f"case-insensitive match for {name!r} -> {cands[0]}"]
        return None, cands

    def _candidates(self, probe: str, table: dict) -> list[str]:
        """Never invent a name: report only spellings that exist in this file, ordered best guess first.

        Case-insensitive equality first, then near-misses (the real-world case is a mis-transcribed net,
        e.g. ``12V_PEX8_6_INP`` for ``12V_PEX6_8_INP``), then substring overlap either way.
        """
        low = probe.lower()
        exact_fold = [k for k in table if k.lower() == low]
        if exact_fold:
            return exact_fold
        folded: dict[str, str] = {}
        for key in table:
            folded.setdefault(key.lower(), key)
        near = [folded[k] for k in difflib.get_close_matches(low, list(folded), n=12, cutoff=0.55)]
        out = near[:]
        for key in table:
            if key in out:
                continue
            if low in key.lower() or key.lower() in low:
                out.append(key)
        return out[:40]

    def note(self, notes: list[str], kind: str = "note") -> str:
        return "; ".join(notes) if notes else kind

    # ---------------------------------------------------------------- search

    def _scan(self, pattern: str, *, fields: str = "all", kind: str | None = None) -> list[dict]:
        """Every component matching *pattern*, unpaginated. The board has a bounded component count, so a
        full scan is cheap and gives tools an honest total instead of a truncated guess."""
        rx = re.compile(re.escape(pattern), re.IGNORECASE) if self._is_glob(pattern) else None
        glob = self._compile_glob(pattern) if self._is_glob(pattern) else None
        out: list[dict] = []
        for ref, comp in self.board.components.items():
            info = self.classified[ref]
            if kind and info["kind"] != kind:
                continue
            hay = {
                "ref": ref,
                "package": comp.package or "",
                "device": comp.device or "",
                "part": (self.board.devices.get(comp.device or "").part or "") if comp.device else "",
                "position": f"{comp.x:.3f},{comp.y:.3f}" if comp.x is not None and comp.y is not None else "",
                "pins": ",".join(sorted(comp.pins)),
                "nets": ",".join(self.graph.nets_of(ref)),
                "kind": info["kind"],
            }
            scanned = hay if fields == "all" else {k: v for k, v in hay.items() if k in fields.split(",")}
            hit = None
            for field_name, value in scanned.items():
                if glob and glob.fullmatch(value):
                    hit = (field_name, value)
                    break
                if rx and rx.search(value):
                    hit = (field_name, value)
                    break
                if not rx and not glob and pattern.lower() in value.lower():
                    hit = (field_name, value)
                    break
            if hit:
                out.append(
                    {
                        "ref": ref,
                        "matched_field": hit[0],
                        "matched_text": hit[1],
                        "package": comp.package,
                        "device": comp.device,
                        "inferred_kind": info["kind"],
                        "inferred": True,
                        "pin_count_declared": len(comp.pins),
                        "pin_count_connected": sum(1 for p in comp.pins.values() if p.nets),
                    }
                )
        return out

    def search(self, pattern: str, *, fields: str = "all", kind: str | None = None, limit: int = 25, offset: int = 0) -> dict:
        """Substring or glob search over components; case-insensitive; original spelling preserved.

        Returns a page plus an honest ``total_matched`` for the whole board, so a truncated page can never
        be mistaken for "these are the only matches".
        """
        window = _clamp(limit, 1, SEARCH_WINDOW_MAX)
        start = _clamp(offset, 0, 1_000_000)
        matches = self._scan(pattern, fields=fields, kind=kind)
        return {
            "matches": matches[start : start + window],
            "total_matched": len(matches),
            "offset": start,
            "limit": window,
            "truncated": len(matches) > start + window,
        }

    def search_nets(self, pattern: str, limit: int = 50) -> list[dict]:
        out: list[dict] = []
        low = pattern.lower()
        for name, net in self.board.nets.items():
            if low in name.lower():
                out.append({"net": name, "member_count": len(net.members), "duplicate_members": net.duplicate_members})
                if len(out) >= limit:
                    break
        return out

    def _is_glob(self, pattern: str) -> bool:
        return any(ch in pattern for ch in "*?")

    def _compile_glob(self, pattern: str):
        return re.compile(fnmatch.translate(pattern).replace("\n", ""))

    def kinds_present(self) -> dict:
        out: dict[str, int] = {}
        for info in self.classified.values():
            out[info["kind"]] = out.get(info["kind"], 0) + 1
        return out

    def passive_kinds(self) -> list[str]:
        return sorted(PASSIVE_KINDS)
