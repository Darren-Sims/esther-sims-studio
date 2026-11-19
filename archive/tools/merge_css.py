#!/usr/bin/env python3
"""Merge Webflow's per-page stylesheets (page-<id>.css) into one readable site.css.

Webflow writes each page's CSS as an ordered subset of the full site stylesheet:
  [rules] [@media 991] [@media 767] [@media 479]   <- class styles
  [rules] [@media 991] [@media 767] [@media 479]   <- element/ID styles
This merges the pages as order-preserving unions (rule order matters for the
cascade), dedupes identical rules, reports any selector styled differently on
different pages, and pretty-prints the result.

Usage: merge_css.py <css dir>   (writes site.css; also pretty-prints shared.css)
"""
import re
import sys
from collections import defaultdict
from pathlib import Path


def split_top(css):
    """Split CSS into top-level blocks, respecting strings and parentheses."""
    out, i, depth, start, q, par = [], 0, 0, 0, None, 0
    while i < len(css):
        c = css[i]
        if q:
            if c == "\\":
                i += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c == "(":
            par += 1
        elif c == ")":
            par -= 1
        elif par == 0 and c == "{":
            depth += 1
        elif par == 0 and c == "}":
            depth -= 1
            if depth == 0:
                block = css[start : i + 1].strip()
                if block:
                    out.append(block)
                start = i + 1
        i += 1
    return out


def dedupe_decls(rule):
    """Drop exact repeats of a declaration inside one rule (Webflow sometimes
    writes `z-index:5;z-index:5`); keeps the last occurrence, so it's equivalent."""
    i = rule.find("{")
    sel, body = rule[:i], rule[i + 1 : -1]
    if sel.strip().startswith("@"):
        return rule
    decls = [d for d in split_decls(body) if d.strip()]
    seen, out = set(), []
    for d in reversed(decls):
        if d not in seen:
            seen.add(d)
            out.append(d)
    return sel + "{" + ";".join(reversed(out)) + "}"


def parse(css):
    """Return items: ('R', seg, text) or ('M', seg, prelude, [rule texts])."""
    items, seg, last = [], 0, None
    for b in split_top(css):
        prelude = b[: b.index("{")].strip()
        if prelude.startswith("@media") or prelude.startswith("@supports"):
            inner = [dedupe_decls(r) for r in split_top(b[b.index("{") + 1 : -1])]
            items.append(("M", seg, prelude, inner))
            last = "M"
        else:
            if last == "M":
                seg += 1
            items.append(("R", seg, dedupe_decls(b)))
            last = "R"
    return items


FORCED = []


def ordered_union(seqs):
    """Order-preserving union of several sequences of hashable keys.

    Builds precedence edges from each sequence and sorts topologically, breaking
    ties by how early a key appears. Webflow's per-page optimiser occasionally
    orders a few rules differently on different pages, which creates cycles; a
    cycle is broken by taking the earliest-seen key, and recorded in FORCED so
    the effect can be checked (see verification in the README).
    """
    import heapq
    first_seen, edges, indeg = {}, defaultdict(set), defaultdict(int)
    for si, seq in enumerate(seqs):
        for pi, k in enumerate(seq):
            first_seen.setdefault(k, (si, pi))
            indeg.setdefault(k, 0)
        for a, b in zip(seq, seq[1:]):
            if a != b and b not in edges[a]:
                edges[a].add(b)
                indeg[b] += 1
    heap = [(first_seen[k], k) for k, d in indeg.items() if d == 0]
    heapq.heapify(heap)
    out, done = [], set()
    while len(out) < len(indeg):
        if not heap:  # cycle: force the earliest-seen remaining key
            k = min((k for k in indeg if k not in done), key=lambda k: first_seen[k])
            FORCED.append(k)
            indeg[k] = 0
            heapq.heappush(heap, (first_seen[k], k))
        _, k = heapq.heappop(heap)
        if k in done:
            continue
        done.add(k)
        out.append(k)
        for nb in edges[k]:
            if nb in done:
                continue
            indeg[nb] -= 1
            if indeg[nb] == 0:
                heapq.heappush(heap, (first_seen[nb], nb))
    return out


def selector_body(rule):
    i = rule.index("{")
    return rule[:i].strip(), rule[i + 1 : -1].strip()


def find_conflicts(rule_lists, context):
    """Same selector, different declarations, in the same context."""
    by_sel = defaultdict(set)
    for rules in rule_lists:
        for r in rules:
            sel, body = selector_body(r)
            by_sel[sel].add(body)
    return [(context, sel, bodies) for sel, bodies in by_sel.items() if len(bodies) > 1]


def merge(pages):
    """Merge per section: Webflow writes each section as base rules followed by
    its @media blocks. Base rules are merged with base rules and each breakpoint
    with the same breakpoint, so a breakpoint can never land before the base
    rules it overrides."""
    parsed = [parse(t) for t in pages]
    segments = sorted({it[1] for p in parsed for it in p})
    conflicts, result = [], []
    for s in segments:
        base_lists, media_lists, media_order = [], defaultdict(list), []
        for p in parsed:
            base_lists.append([it[2] for it in p if it[0] == "R" and it[1] == s])
            for it in p:
                if it[0] == "M" and it[1] == s:
                    if it[2] not in media_order:
                        media_order.append(it[2])
                    media_lists[it[2]].append(it[3])
        base_lists = [b for b in base_lists if b]
        conflicts += find_conflicts(base_lists, f"section {s}")
        for r in ordered_union(base_lists):
            result.append(("R", r))
        # Webflow's desktop-first breakpoints, largest first; anything else after
        def bp(q):
            m = re.search(r"max-width:\s*(\d+)px", q)
            return (0, -int(m.group(1))) if m and "min-width" not in q else (1, media_order.index(q))
        for q in sorted(media_order, key=bp):
            conflicts += find_conflicts(media_lists[q], f"{q} (section {s})")
            result.append(("M", q, ordered_union(media_lists[q])))
    return result, conflicts, parsed


# ---------------------------------------------------------------- pretty print
def pretty_rule(rule, indent=""):
    sel, body = selector_body(rule)
    if sel.startswith("@"):  # nested at-rule such as @font-face / @keyframes
        inner = split_top(body)
        if inner and all("{" in x for x in inner) and not sel.startswith("@font-face"):
            return f"{indent}{sel} {{\n" + "\n".join(pretty_rule(x, indent + "  ") for x in inner) + f"\n{indent}}}"
    sels = split_commas(sel)
    decls = [d.strip() for d in split_decls(body) if d.strip()]
    head = (",\n" + indent).join(s.strip() for s in sels)
    if not decls:
        return f"{indent}{head} {{}}"
    lines = "\n".join(f"{indent}  {fmt_decl(d)};" for d in decls)
    return f"{indent}{head} {{\n{lines}\n{indent}}}"


def fmt_decl(d):
    if ":" in d:
        p, v = d.split(":", 1)
        return f"{p.strip()}: {v.strip()}"
    return d


def split_on(s, ch):
    out, buf, q, par = [], "", None, 0
    for c in s:
        if q:
            buf += c
            if c == q:
                q = None
            continue
        if c in "\"'":
            q = c
        elif c == "(":
            par += 1
        elif c == ")":
            par -= 1
        if c == ch and par == 0:
            out.append(buf)
            buf = ""
        else:
            buf += c
    out.append(buf)
    return out


def split_commas(s):
    return split_on(s, ",")


def split_decls(s):
    return split_on(s, ";")


def pretty(items, header=""):
    out = [header] if header else []
    for it in items:
        if it[0] == "R":
            out.append(pretty_rule(it[1]))
        else:
            out.append(f"{it[1]} {{\n" + "\n\n".join(pretty_rule(r, "  ") for r in it[2]) + "\n}")
    return "\n\n".join(out) + "\n"


def items_of(css):
    res = []
    for it in parse(css):
        res.append(("R", it[2]) if it[0] == "R" else ("M", it[2], it[3]))
    return res


def main():
    d = Path(sys.argv[1])
    pages = sorted(d.glob("page-*.css"))
    merged, conflicts, parsed = merge([p.read_text(encoding="utf-8") for p in pages])
    for ctx, sel, bodies in conflicts:
        print(f"CONFLICT [{ctx}] {sel}")
        for b in bodies:
            print(f"    {{{b[:160]}}}")
    header = (
        "/*\n * Esther Sims Studio site styles.\n"
        " * Merged from Webflow's 11 per-page stylesheets (identical rules deduplicated,\n"
        " * order kept). Colours, fonts and type sizes are variables in theme.css.\n"
        " * Breakpoints: 991px (tablet), 767px (mobile landscape), 479px (mobile).\n */"
    )
    (d / "site.css").write_text(pretty(merged, header), encoding="utf-8")
    shared = (d / "shared.css").read_text(encoding="utf-8")
    (d / "shared.css").write_text(
        pretty(items_of(shared), "/* Webflow base styles: normalize + Webflow components (nav, sliders, forms, tabs…). */"),
        encoding="utf-8",
    )
    n_rules = sum(1 if it[0] == "R" else len(it[2]) for it in merged)
    print(f"merged {len(pages)} files -> site.css: {n_rules} rules, {len(conflicts)} conflicts, {len(FORCED)} order disagreements resolved")


if __name__ == "__main__":
    main()
