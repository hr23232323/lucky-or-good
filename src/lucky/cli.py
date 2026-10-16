"""`lucky`: the command line for the judge.

    lucky synthetic DIR                  make a fake market to try things out
    lucky season new DIR --periods FILE  start a research season
    lucky check FILE                     static checks only
    lucky judge FILE [--block NAME]      check, run, score and log
    lucky freeze FILE                    pin a strategy before opening a vault
    lucky vault FILE --block NAME        one look at a sealed block (humans only)
    lucky ledger                         list trials in the season
    lucky verify                         check the ledger's hash chain

The season comes from --season or the LUCKY_SEASON environment variable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .checks import static_check
from .judge import GateError, Judge
from .season import Season


def _season(args) -> Season:
    path = args.season or os.environ.get("LUCKY_SEASON")
    if not path:
        sys.exit("No season. Pass --season DIR or set LUCKY_SEASON (see `lucky season new`).")
    return Season.load(path)


def _fmt_report(rec: dict) -> str:
    lines = [f"#{rec.get('seq', '?')}  {rec.get('file')}  [{rec.get('block')}]  {rec['status']}"]
    meta = rec.get("meta") or {}
    if meta.get("name"):
        lines.append(f"  {meta['name']}: {meta.get('hypothesis', '')}")
    if rec["status"] == "rejected":
        lines += [f"  - {v}" for v in rec["violations"]]
    elif rec["status"] == "error":
        lines.append("  " + rec["error"].strip().splitlines()[-1])
    elif rec["status"] == "lookahead":
        bad = [c for c in rec["lookahead"] if not c["ok"]]
        lines.append(
            f"  weights changed when future data was removed (e.g. {bad[0]['date']}: "
            f"{bad[0]['mismatched_cells']} cells). Something reads data after t."
        )
    if "answer" in rec:
        a = rec["answer"]
        lines.append(f"  validation: {a['verdict']}, Sharpe ~ {a['sharpe']}")
        lines.append(
            f"  budget left: {rec.get('budget_left')}" + ("  (repeat)" if rec.get("repeat") else "")
        )
    m = rec.get("metrics")
    if m:
        lines.append(
            f"  Sharpe {m['sharpe']:.2f} (gross {m['gross_sharpe']:.2f}, t {m['t_stat']:.1f})  "
            f"return {m['annual_return']:.1%}/yr  max DD {m['max_drawdown']:.1%}"
        )
        lines.append(
            f"  costs {m['annual_cost_drag']:.1%}/yr  turnover {m['annual_turnover']:.0f}x/yr  "
            f"positions {m['avg_positions']:.0f}  exposure {m['avg_gross_exposure']:.2f}"
        )
        if "benchmark_sharpe" in m:
            lines.append(
                f"  benchmark Sharpe {m['benchmark_sharpe']:.2f}  beta {m.get('beta', 0):.2f}  "
                f"alpha Sharpe {m.get('alpha_sharpe', 0):.2f}"
            )
        lines.append(f"  with one extra day of lag: Sharpe {rec.get('extra_lag_sharpe', 0):.2f}")
    d = rec.get("deflation")
    if d and "strategies_tried" in d:
        lines.append(
            f"  {d['strategies_tried']} strategies tried in this season; noise alone would be "
            f"expected to reach Sharpe {d['best_noise_sharpe_expected']:.2f}. "
            f"Deflated Sharpe: {d['deflated_sharpe']:.2f}"
        )
    elif d:
        lines.append(
            f"  vault opens so far: {d['vault_opens']}  deflated Sharpe {d['deflated_sharpe']:.2f}"
        )
    for note in rec.get("notes") or []:
        lines.append(f"  note: {note}")
    return "\n".join(lines)


def _print(rec: dict, as_json: bool) -> None:
    print(json.dumps(rec, indent=2, default=str) if as_json else _fmt_report(rec))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lucky", description="An honest judge for trading strategies.")
    p.add_argument("--season", help="season directory (default: $LUCKY_SEASON)")
    p.add_argument("--json", action="store_true", help="print raw JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("synthetic", help="write a synthetic market in MarketParquet layout")
    s.add_argument("dir")
    s.add_argument("--stocks", type=int, default=300)
    s.add_argument("--edge", type=float, default=0.0, help="planted edge strength (0 = none)")
    s.add_argument("--start", default="2000-01-03")
    s.add_argument("--end", default="2026-10-15")
    s.add_argument("--seed", type=int, default=0)

    sn = sub.add_parser("season", help="manage research seasons")
    snsub = sn.add_subparsers(dest="season_cmd", required=True)
    new = snsub.add_parser("new", help="start a season")
    new.add_argument("dir")
    new.add_argument("--periods", required=True, help="config/periods/<dataset>.toml")
    new.add_argument("--data", default=os.environ.get("LUCKY_DATA_DIR"), help="data root")
    new.add_argument("--model", default="unspecified", help="proposing model, e.g. claude-opus-5-5")
    new.add_argument("--cutoff", default="unknown", help="its training cutoff, e.g. 2026-06")
    new.add_argument("--top-n", type=int, default=1000)
    new.add_argument("--benchmark", default="SPY")
    new.add_argument("--budget", type=int, default=25, help="validation looks allowed")

    c = sub.add_parser("check", help="static checks only")
    c.add_argument("file")

    j = sub.add_parser("judge", help="check, run, score and log a strategy")
    j.add_argument("file")
    j.add_argument("--block", default="discovery")

    f = sub.add_parser("freeze", help="pin a strategy before opening a sealed block")
    f.add_argument("file")
    f.add_argument("--note", default="")

    v = sub.add_parser("vault", help="one look at a vault or forward block (humans only)")
    v.add_argument("file")
    v.add_argument("--block", required=True)

    sub.add_parser("ledger", help="list trials in the season")
    sub.add_parser("verify", help="check the ledger's hash chain")

    args = p.parse_args(argv)

    if args.cmd == "synthetic":
        from .synthetic import SyntheticConfig, generate

        cfg = SyntheticConfig(
            start=args.start, end=args.end, n_stocks=args.stocks, edge=args.edge, seed=args.seed
        )
        truth = generate(args.dir, cfg)
        print(f"Wrote {truth['n_days']} days x {args.stocks} stocks to {args.dir}")
        print("Point a season at it:")
        print(
            f"  lucky season new runs/try --periods config/periods/synthetic.toml --data {args.dir}"
        )
        return 0

    if args.cmd == "season":
        if not args.data:
            sys.exit("Pass --data or set LUCKY_DATA_DIR.")
        season = Season.create(
            args.dir,
            args.periods,
            args.data,
            model=args.model,
            model_cutoff=args.cutoff,
            top_n=args.top_n,
            benchmark=args.benchmark,
            validation_budget=args.budget,
        )
        print(f"Season '{season.name}' at {season.dir}. Use: export LUCKY_SEASON={season.dir}")
        return 0

    if args.cmd == "check":
        problems = static_check(Path(args.file).read_text())
        for prob in problems:
            print(prob)
        print("ok" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0

    season = _season(args)

    if args.cmd == "verify":
        problems = season.ledger.verify()
        for prob in problems:
            print(prob)
        print("ledger intact" if not problems else "LEDGER TAMPERED")
        return 1 if problems else 0

    if args.cmd == "ledger":
        for e in season.ledger.entries():
            if e.get("kind") == "trial":
                m = e.get("metrics") or {}
                ans = e.get("answer") or {}
                shown = m.get("sharpe", ans.get("sharpe", ""))
                name = (e.get("meta") or {}).get("name", Path(e["file"]).stem)
                print(f"{e['seq']:>5}  {e['block']:<10} {e['status']:<9} {shown!s:>6}  {name}")
            elif e.get("kind") == "freeze":
                print(f"{e['seq']:>5}  frozen     {e['hash']}  {e.get('note', '')}")
        return 0

    judge = Judge(season)
    try:
        if args.cmd == "judge":
            rec = judge.evaluate(args.file, args.block)
        elif args.cmd == "freeze":
            rec = judge.freeze(args.file, args.note)
            print(f"frozen {rec['hash']} (#{rec['seq']})")
            return 0
        elif args.cmd == "vault":
            rec = judge.open_sealed(args.file, args.block)
        else:  # pragma: no cover
            p.error(f"unknown command {args.cmd}")
    except GateError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    _print(rec, args.json)
    return 0 if rec["status"] == "scored" else 1


if __name__ == "__main__":
    sys.exit(main())
