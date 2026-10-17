"""One self-contained HTML page per season: every strategy, in one place.

Built only from the season folder (ledger, saved returns, and sealed results
when asked), so it needs no market data and no network. Sealed numbers (true
validation results, vault results) appear only with ``include_sealed=True``.
"""

from __future__ import annotations

import html
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .metrics import DAYS, expected_max_sharpe
from .season import Season

BASELINE, CANDIDATE = "baseline", "candidate"
MAX_BARS = 40  # above this, the Sharpe chart becomes a dot strip
MAX_CURVES = 12  # candidate equity curves shown (best by Sharpe); baselines always shown
ASSETS = Path(__file__).parent / "report_assets"


def _esc(x) -> str:
    return html.escape(str(x), quote=True)


def _group(entry: dict) -> str:
    return BASELINE if "baselines" in Path(entry.get("file", "")).parts else CANDIDATE


def _name(entry: dict) -> str:
    return (entry.get("meta") or {}).get("name") or Path(entry.get("file", "?")).stem


def _fmt(x, spec=".2f", dash="–"):
    if x is None or x == "" or (isinstance(x, float) and math.isnan(x)):
        return dash
    return format(x, spec)


# ---------------------------------------------------------------- data


def gather(season: Season, include_sealed: bool = False) -> dict:
    entries = season.ledger.entries()
    trials = [e for e in entries if e.get("kind") == "trial"]
    latest: dict[str, dict] = {}
    for e in trials:
        if e.get("block_kind") == "discovery" and e.get("status") == "scored":
            latest[e["hash"]] = e
    per_period = [e["metrics"]["sharpe"] / math.sqrt(DAYS) for e in latest.values()]
    n = len(per_period)
    var = float(pd.Series(per_period).var()) if n > 1 else 0.0
    noise_bar = expected_max_sharpe(n, var) * math.sqrt(DAYS)

    validation: dict[str, dict] = {}
    vaults: dict[tuple[str, str], dict] = {}
    for e in trials:
        if "answer" in e:
            validation[e["hash"]] = e["answer"]
        if e.get("block_kind") in {"vault", "forward"}:
            result = {"status": e.get("status"), "seq": e["seq"]}
            sealed = season.dir / "sealed" / f"{e['seq']:05d}.json"
            if include_sealed and sealed.exists():
                full = json.loads(sealed.read_text())
                result["metrics"] = full.get("metrics")
                result["deflation"] = full.get("deflation")
            vaults[(e["hash"], e["block"])] = result
    if include_sealed:
        shown = ("metrics", "deflation", "extra_lag_sharpe", "sign_matches")
        enriched = []
        for e in trials:
            sealed = season.dir / "sealed" / f"{e['seq']:05d}.json"
            if e.get("block_kind") != "discovery" and sealed.exists():
                full = json.loads(sealed.read_text())
                e = {**e, **{k: full[k] for k in shown if k in full}}
            enriched.append(e)
        trials = enriched
        for e in trials:
            if "answer" in e:
                sealed = season.dir / "sealed" / f"{e['seq']:05d}.json"
                if sealed.exists():
                    validation[e["hash"]] = {
                        **e["answer"],
                        "true_sharpe": json.loads(sealed.read_text())["metrics"]["sharpe"],
                    }

    curves = {}
    for h, e in latest.items():
        path = season.dir / "returns" / f"{e['seq']:05d}.parquet"
        if path.exists():
            curves[h] = pd.read_parquet(path)["return"]
    bench_path = season.dir / "returns" / "benchmark_discovery.parquet"
    bench = pd.read_parquet(bench_path)["return"] if bench_path.exists() else None

    return {
        "season": season,
        "entries": entries,
        "trials": trials,
        "latest": latest,
        "noise_bar": noise_bar,
        "validation": validation,
        "vaults": vaults,
        "curves": curves,
        "benchmark": bench,
        "include_sealed": include_sealed,
        "intact": not season.ledger.verify(),
    }


# ---------------------------------------------------------------- charts

W = 760


class Scale:
    def __init__(self, lo, hi, a, b):
        self.lo, self.hi, self.a, self.b = lo, hi, a, b

    def __call__(self, v):
        if self.hi == self.lo:
            return (self.a + self.b) / 2
        return self.a + (v - self.lo) / (self.hi - self.lo) * (self.b - self.a)


def _ticks(lo, hi, n=5):
    span = hi - lo or 1.0
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=raw)
    start = math.ceil(lo / step) * step
    out, v = [], start
    while v <= hi + 1e-9:
        out.append(round(v, 10))
        v += step
    return out


def _bar_path(x0, x1, y, h, r=4):
    """Bar from the baseline x0 to x1, rounded only at the data end."""
    if abs(x1 - x0) < r:
        return f"M{x0:.1f},{y:.1f}H{x1:.1f}V{y + h:.1f}H{x0:.1f}Z"
    if x1 >= x0:
        return (
            f"M{x0:.1f},{y:.1f}H{x1 - r:.1f}Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f}"
            f"V{y + h - r:.1f}Q{x1:.1f},{y + h:.1f} {x1 - r:.1f},{y + h:.1f}H{x0:.1f}Z"
        )
    return (
        f"M{x0:.1f},{y:.1f}H{x1 + r:.1f}Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f}"
        f"V{y + h - r:.1f}Q{x1:.1f},{y + h:.1f} {x1 + r:.1f},{y + h:.1f}H{x0:.1f}Z"
    )


def _tip(lines: list[str]) -> str:
    return _esc(json.dumps(lines))


def _strategy_tip(e: dict) -> list[str]:
    m = e["metrics"]
    d = e.get("deflation") or {}
    return [
        f"Sharpe {m['sharpe']:.2f}",
        _name(e),
        f"gross {m['gross_sharpe']:.2f} · t {m['t_stat']:.1f} · DSR {_fmt(d.get('deflated_sharpe'))}",
        f"costs {m['annual_cost_drag']:.1%}/yr · turnover {m['annual_turnover']:.0f}x",
        f"{_group(e)} · #{e['seq']}",
    ]


def sharpe_chart(data: dict) -> str:
    rows = sorted(data["latest"].values(), key=lambda e: e["metrics"]["sharpe"], reverse=True)
    if not rows:
        return '<p class="empty">No strategies scored in discovery yet.</p>'
    noise = data["noise_bar"]
    vals = [e["metrics"]["sharpe"] for e in rows]
    lo, hi = min(min(vals), 0.0, -0.5), max(max(vals), noise, 0.5)
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad
    if len(rows) <= MAX_BARS:
        return _bars(rows, lo, hi, noise)
    return _strip(rows, lo, hi, noise)


def _ref_lines(x, lo, hi, noise, top, bottom):
    parts = []
    for t in _ticks(lo, hi):
        parts.append(
            f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top}" y2="{bottom}"/>'
            f'<text class="tick" x="{x(t):.1f}" y="{bottom + 16}" text-anchor="middle">{t:g}</text>'
        )
    parts.append(f'<line class="axis" x1="{x(0):.1f}" x2="{x(0):.1f}" y1="{top}" y2="{bottom}"/>')
    parts.append(
        f'<line class="noise" x1="{x(noise):.1f}" x2="{x(noise):.1f}" y1="{top - 6}" y2="{bottom}"/>'
        f'<text class="noise-label" x="{x(noise) + 4:.1f}" y="{top - 8}">'
        f"noise bar {noise:.2f}</text>"
    )
    return "".join(parts)


def _bars(rows, lo, hi, noise) -> str:
    label_w, bar_h, gap, top = 210, 16, 8, 26
    h = top + len(rows) * (bar_h + gap) + 28
    x = Scale(lo, hi, label_w, W - 56)
    parts = [_ref_lines(x, lo, hi, noise, top - 4, h - 26)]
    for i, e in enumerate(rows):
        y = top + i * (bar_h + gap)
        s = e["metrics"]["sharpe"]
        g = _group(e)
        name = _name(e)
        short = name if len(name) <= 30 else name[:29] + "…"
        anchor, dx = ("start", 6) if s >= 0 else ("end", -6)
        parts.append(
            f'<g class="mark" tabindex="0" data-tip="{_tip(_strategy_tip(e))}">'
            f'<rect class="hit" x="0" y="{y - gap / 2}" width="{W}" height="{bar_h + gap}"/>'
            f'<text class="label" x="{label_w - 10}" y="{y + bar_h - 4}" text-anchor="end">'
            f"{_esc(short)}</text>"
            f'<path class="bar {g}" d="{_bar_path(x(0), x(s), y, bar_h)}"/>'
            f'<text class="value" x="{x(s) + dx:.1f}" y="{y + bar_h - 4}" '
            f'text-anchor="{anchor}">{s:.2f}</text></g>'
        )
    return (
        f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="Discovery Sharpe ratio for each '
        f'strategy, with the noise bar">{"".join(parts)}</svg>'
    )


def _strip(rows, lo, hi, noise) -> str:
    top, band = 30, 70
    groups = [BASELINE, CANDIDATE]
    h = top + band * len(groups) + 30
    x = Scale(lo, hi, 110, W - 20)
    parts = [_ref_lines(x, lo, hi, noise, top - 4, h - 26)]
    for gi, g in enumerate(groups):
        cy = top + gi * band + band / 2
        parts.append(f'<text class="label" x="100" y="{cy + 4}" text-anchor="end">{g}s</text>')
        members = [e for e in rows if _group(e) == g]
        for j, e in enumerate(members):
            jitter = ((j * 37) % 23 - 11) * 2.2
            s = e["metrics"]["sharpe"]
            parts.append(
                f'<g class="mark" tabindex="0" data-tip="{_tip(_strategy_tip(e))}">'
                f'<circle class="hit" cx="{x(s):.1f}" cy="{cy + jitter:.1f}" r="12"/>'
                f'<circle class="dot {g}" cx="{x(s):.1f}" cy="{cy + jitter:.1f}" r="4"/></g>'
            )
    return (
        f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="Discovery Sharpe ratio of every '
        f'strategy as dots, split into baselines and candidates">{"".join(parts)}</svg>'
    )


def equity_chart(data: dict) -> tuple[str, str]:
    latest, curves = data["latest"], data["curves"]
    if not curves:
        return '<p class="empty">No return series saved yet.</p>', ""
    chosen = [h for h in curves if _group(latest[h]) == BASELINE]
    cands = sorted(
        (h for h in curves if _group(latest[h]) == CANDIDATE),
        key=lambda h: latest[h]["metrics"]["sharpe"],
        reverse=True,
    )
    chosen += cands[:MAX_CURVES]
    hidden = max(0, len(cands) - MAX_CURVES)

    series = []
    for h in chosen:
        growth = (1 + curves[h].fillna(0)).cumprod()
        series.append({"name": _name(latest[h]), "group": _group(latest[h]), "g": growth})
    if data["benchmark"] is not None:
        b = (1 + data["benchmark"].fillna(0)).cumprod()
        series.append({"name": f"benchmark ({data['season'].benchmark})", "group": "bench", "g": b})

    index = series[0]["g"].index
    for s in series[1:]:
        index = index.union(s["g"].index)
    step = max(1, len(index) // 400)
    idx = index[::step]
    for s in series:
        s["v"] = s["g"].reindex(idx).ffill().bfill()

    top, left, right, bottom = 16, 48, W - 16, 300
    allv = pd.concat([s["v"] for s in series])
    lo, hi = float(allv.min()), float(allv.max())
    x = Scale(0, len(idx) - 1, left, right)
    y = Scale(lo, hi, bottom, top)
    parts = []
    for t in _ticks(lo, hi, 4):
        parts.append(
            f'<line class="grid" x1="{left}" x2="{right}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
            f'<text class="tick" x="{left - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{t:g}</text>'
        )
    years = pd.Series(range(len(idx)), index=idx).groupby(idx.year).min()
    every = max(1, len(years) // 8)
    for yr, i in list(years.items())[::every]:
        parts.append(
            f'<text class="tick" x="{x(i):.1f}" y="{bottom + 16}" text-anchor="middle">{yr}</text>'
        )
    parts.append(f'<line class="axis" x1="{left}" x2="{right}" y1="{y(1):.1f}" y2="{y(1):.1f}"/>')
    order = sorted(
        range(len(series)),
        key=lambda i: {"bench": 0, BASELINE: 1, CANDIDATE: 2}[series[i]["group"]],
    )
    for i in order:
        s = series[i]
        d = "M" + "L".join(f"{x(k):.1f},{y(v):.1f}" for k, v in enumerate(s["v"].to_numpy()))
        parts.append(f'<path class="line {s["group"]}" data-i="{i}" d="{d}"/>')
    parts.append(f'<line id="crosshair" class="crosshair" x1="0" x2="0" y1="{top}" y2="{bottom}"/>')
    parts.append(
        f'<rect id="eq-hit" class="hit" x="{left}" y="{top}" width="{right - left}" '
        f'height="{bottom - top}"/>'
    )
    payload = {
        "dates": [str(d.date()) for d in idx],
        "series": [
            {"name": s["name"], "group": s["group"], "v": [round(float(v), 4) for v in s["v"]]}
            for s in series
        ],
        "x0": left,
        "x1": right,
    }
    note = (
        f"Showing the {MAX_CURVES} best candidates; {hidden} more are in the table."
        if hidden
        else ""
    )
    svg = (
        f'<svg id="equity" viewBox="0 0 {W} {bottom + 24}" role="img" aria-label="Growth of one '
        f'dollar in discovery for each strategy and the benchmark">{"".join(parts)}</svg>'
        f'<script type="application/json" id="equity-data">{json.dumps(payload)}</script>'
    )
    return svg, note


def vault_charts(data: dict) -> str:
    if not data["vaults"]:
        return ""
    if not data["include_sealed"]:
        opened = len(data["vaults"])
        return (
            f'<p class="sealed-note">{opened} sealed look(s) recorded. Results stay sealed in '
            "this view; run <code>lucky report --include-sealed</code> to show them.</p>"
        )
    out = []
    blocks = sorted({b for _, b in data["vaults"]})
    for block in blocks:
        pts = []
        for (h, b), r in data["vaults"].items():
            if b != block or not r.get("metrics") or h not in data["latest"]:
                continue
            e = data["latest"][h]
            pts.append((e["metrics"]["sharpe"], r["metrics"]["sharpe"], e))
        if not pts:
            continue
        xs = [p[0] for p in pts] + [0.0]
        ys = [p[1] for p in pts] + [0.0]
        lo, hi = min(xs + ys) - 0.3, max(xs + ys) + 0.3
        size, m = 360, 44
        sx = Scale(lo, hi, m, size - 12)
        sy = Scale(lo, hi, size - m, 12)
        parts = [
            f'<line class="axis" x1="{sx(0):.1f}" x2="{sx(0):.1f}" y1="12" y2="{size - m}"/>',
            f'<line class="axis" x1="{m}" x2="{size - 12}" y1="{sy(0):.1f}" y2="{sy(0):.1f}"/>',
            f'<line class="diag" x1="{sx(lo):.1f}" y1="{sy(lo):.1f}" x2="{sx(hi):.1f}" y2="{sy(hi):.1f}"/>',
            f'<text class="tick" x="{(m + size) / 2}" y="{size - 10}" text-anchor="middle">'
            "discovery Sharpe</text>",
            f'<text class="tick" x="10" y="{(size - m) / 2}" transform="rotate(-90 10 {(size - m) / 2})" '
            f'text-anchor="middle">{_esc(block)} Sharpe</text>',
        ]
        for t in _ticks(lo, hi, 4):
            parts.append(
                f'<text class="tick" x="{sx(t):.1f}" y="{size - m + 14}" text-anchor="middle">{t:g}</text>'
                f'<text class="tick" x="{m - 6}" y="{sy(t) + 4:.1f}" text-anchor="end">{t:g}</text>'
            )
        for dx, vy, e in pts:
            tip = [f"{block} Sharpe {vy:.2f}", _name(e), f"discovery Sharpe {dx:.2f}"]
            right = sx(dx) > size * 0.55  # label on the side with room
            label = (
                f'<text class="label" x="{sx(dx) + (-9 if right else 9):.1f}" y="{sy(vy) + 4:.1f}" '
                f'text-anchor="{"end" if right else "start"}">{_esc(_name(e))}</text>'
                if len(pts) <= 8
                else ""
            )
            parts.append(
                f'<g class="mark" tabindex="0" data-tip="{_tip(tip)}">'
                f'<circle class="hit" cx="{sx(dx):.1f}" cy="{sy(vy):.1f}" r="12"/>'
                f'<circle class="dot {_group(e)}" cx="{sx(dx):.1f}" cy="{sy(vy):.1f}" r="5"/>{label}</g>'
            )
        out.append(
            f'<figure><svg viewBox="0 0 {size} {size}" role="img" aria-label="Discovery Sharpe '
            f'against {_esc(block)} Sharpe for each frozen strategy">{"".join(parts)}</svg>'
            f"<figcaption>{_esc(block)}: points below the dashed line did worse than in "
            "discovery.</figcaption></figure>"
        )
    return '<div class="vaults">' + "".join(out) + "</div>"


# ---------------------------------------------------------------- page


def _status_badge(status: str) -> str:
    icon = {"scored": "●", "rejected": "✕", "lookahead": "⚠", "error": "!"}.get(status, "·")
    return f'<span class="status {status}">{icon} {status}</span>'


def trials_table(data: dict) -> str:
    vault_blocks = sorted({b for _, b in data["vaults"]})
    head = [
        "#",
        "strategy",
        "",
        "block",
        "status",
        "Sharpe",
        "gross",
        "t",
        "DSR",
        "costs/yr",
        "turnover",
        "max DD",
        "+1 day lag",
        "sign",
        "validation",
    ] + vault_blocks
    rows = []
    for e in data["trials"]:
        m = e.get("metrics") or {}
        d = e.get("deflation") or {}
        ans = data["validation"].get(e["hash"]) if e.get("block_kind") == "discovery" else None
        val = "–"
        if ans:
            val = f"~{ans['sharpe']:.2f}"
            if "true_sharpe" in ans:
                val += f" (true {ans['true_sharpe']:.2f})"
        if "answer" in e:
            val = f"answered ~{e['answer']['sharpe']:.2f}"
        sign = {True: "as expected", False: "opposite"}.get(e.get("sign_matches"), "–")
        hyp = (e.get("meta") or {}).get("hypothesis", "")
        cells = [
            str(e["seq"]),
            f'<div class="sname">{_esc(_name(e))}</div><div class="hyp">{_esc(hyp)}</div>',
            f'<span class="key {_group(e)}"></span>{_group(e)}',
            _esc(e.get("block", "")),
            _status_badge(e.get("status", "")),
            _fmt(m.get("sharpe")),
            _fmt(m.get("gross_sharpe")),
            _fmt(m.get("t_stat"), ".1f"),
            _fmt(d.get("deflated_sharpe")),
            _fmt(m.get("annual_cost_drag"), ".1%"),
            _fmt(m.get("annual_turnover"), ".0f") + ("x" if m else ""),
            _fmt(m.get("max_drawdown"), ".0%"),
            _fmt(e.get("extra_lag_sharpe")),
            sign,
            _esc(val),
        ]
        for b in vault_blocks:
            r = data["vaults"].get((e["hash"], b)) if e.get("block_kind") == "discovery" else None
            if not r:
                cells.append("–")
            elif r.get("metrics"):
                cells.append(_fmt(r["metrics"]["sharpe"]))
            else:
                cells.append("sealed")
        rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + "".join(f"<th>{_esc(h)}</th>" for h in head)
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def failures(data: dict) -> str:
    items = []
    for e in data["trials"]:
        st = e.get("status")
        if st == "rejected":
            why = "; ".join(e.get("violations", []))
        elif st == "lookahead":
            bad = [c for c in e.get("lookahead", []) if not c.get("ok")]
            why = (
                f"weights changed when data after {bad[0]['date']} was removed "
                f"({bad[0]['mismatched_cells']} cells)"
                if bad
                else "look-ahead"
            )
        elif st == "error":
            why = (e.get("error") or "").strip().splitlines()[-1:][0] if e.get("error") else ""
        else:
            continue
        items.append(
            f"<li>{_status_badge(st)} <strong>#{e['seq']} {_esc(_name(e))}</strong>"
            f'<div class="why">{_esc(why)}</div></li>'
        )
    if not items:
        return '<p class="empty">Nothing rejected yet.</p>'
    return '<ul class="failures">' + "".join(items) + "</ul>"


def _tiles(data: dict) -> str:
    trials = data["trials"]
    count = lambda st: sum(1 for e in trials if e.get("status") == st)  # noqa: E731
    latest = data["latest"]
    best = max(latest.values(), key=lambda e: e["metrics"]["sharpe"], default=None)
    spent = sum(1 for e in trials if e.get("spent"))
    tiles = [
        (
            str(len(latest)),
            "strategies scored in discovery",
            f"{len(trials)} trials in all, including reruns and failures",
        ),
        (
            f"{data['noise_bar']:.2f}",
            "noise bar",
            "the Sharpe the best of this many skill-less strategies would be expected to reach",
        ),
        (
            f"{best['metrics']['sharpe']:.2f}" if best else "–",
            "best discovery Sharpe",
            _name(best) if best else "nothing scored yet",
        ),
        (
            f"{count('rejected') + count('lookahead') + count('error')}",
            "rejected or failed",
            f"{count('rejected')} by static checks · {count('lookahead')} look-ahead · "
            f"{count('error')} {'error' if count('error') == 1 else 'errors'}",
        ),
        (
            f"{spent}/{data['season'].validation_budget}",
            "validation looks spent",
            "spent only when validation disagrees with discovery",
        ),
        (
            str(len(data["vaults"])),
            "sealed looks",
            "vault and forward blocks, one per frozen strategy",
        ),
    ]
    return (
        '<div class="tiles">'
        + "".join(
            f'<div class="tile"><div class="tile-value">{_esc(v)}</div>'
            f'<div class="tile-label">{_esc(lbl)}</div><div class="tile-note">{_esc(n)}</div></div>'
            for v, lbl, n in tiles
        )
        + "</div>"
    )


def _periods(season: Season) -> str:
    rows = "".join(
        f"<tr><td>{_esc(b.name)}</td><td>{_esc(b.kind)}</td>"
        f"<td>{b.start.date()} to {b.end.date()}</td></tr>"
        for b in sorted(season.periods.blocks, key=lambda b: b.start)
    )
    return (
        '<div class="table-wrap"><table class="periods"><thead><tr><th>block</th><th>kind</th>'
        f"<th>dates</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


def build(season: Season, include_sealed: bool = False) -> str:
    data = gather(season, include_sealed)
    eq_svg, eq_note = equity_chart(data)
    integrity = (
        '<span class="status scored">● ledger intact</span>'
        if data["intact"]
        else '<span class="status error">! ledger tampered: run lucky verify</span>'
    )
    sealed_flag = (
        '<span class="status lookahead">⚠ includes sealed results</span>'
        if include_sealed
        else '<span class="status neutral">sealed results hidden</span>'
    )
    s = season
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    template = (ASSETS / "report.html").read_text()
    return template.format(
        title=_esc(f"lucky-or-good season {s.name}"),
        name=_esc(s.name),
        meta=_esc(
            f"Proposing model {s.model} (training cutoff {s.model_cutoff}) · universe: top "
            f"{s.top_n} US stocks by liquidity · benchmark {s.benchmark}"
        ),
        integrity=integrity,
        sealed_flag=sealed_flag,
        tiles=_tiles(data),
        sharpe=sharpe_chart(data),
        equity=eq_svg,
        equity_note=_esc(eq_note),
        vaults=vault_charts(data),
        table=trials_table(data),
        failures=failures(data),
        periods=_periods(s),
        generated=generated,
        css=(ASSETS / "report.css").read_text(),
        js=(ASSETS / "report.js").read_text(),
    )


def write(season: Season, out: Path | str | None = None, include_sealed: bool = False) -> Path:
    out = (
        Path(out)
        if out
        else season.dir / ("report-sealed.html" if include_sealed else "report.html")
    )
    out.write_text(build(season, include_sealed))
    return out
