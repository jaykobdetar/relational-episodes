import argparse
import json
from pathlib import Path
import sys
from .core import ContractError, dumps, loads, parse_query, parse_world
from .coverage import episode_support
from .engine import evaluate
from .oracle import evaluate_sql
from .release import build
from .resources import check_headroom, limits
from .scoring import score
from .validate import validate_release


def main():
    parser = argparse.ArgumentParser(description="Exact immutable relational/episode generator")
    sub = parser.add_subparsers(dest="command",required=True)
    gen = sub.add_parser("generate"); gen.add_argument("--config",required=True); gen.add_argument("--out",required=True)
    val = sub.add_parser("validate"); val.add_argument("directory"); val.add_argument("--report",required=True)
    solve = sub.add_parser("solve"); solve.add_argument("input",help="JSON object with world and query")
    scoring = sub.add_parser("score"); scoring.add_argument("input",help="JSON object with prediction and target")
    sub.add_parser("headroom")
    args = parser.parse_args(); limits()
    try:
        if args.command == "headroom":
            print(dumps(check_headroom())); return 0
        if args.command in ("generate","validate"):
            gate = check_headroom()
            print(dumps({"resource_gate":gate}),file=sys.stderr)
        if args.command == "generate":
            result = build(loads(Path(args.config).read_text()),args.out)
            print(dumps({"records":result["records"],"families":result["families"],"serialized_export_bytes":result["serialized_export_bytes"]}))
        elif args.command == "validate":
            result = validate_release(args.directory)
            # Refuse overwriting an earlier validation report; preserve failures too.
            with Path(args.report).open("x") as f: f.write(dumps(result)+"\n")
            print(dumps({"status":result["status"],"counts":result["counts"]}))
        elif args.command == "solve":
            obj = loads(Path(args.input).read_text())
            from .core import keys
            keys(obj,("world","query"),"solve input")
            w = parse_world(obj["world"]); q = parse_query(obj["query"],w)
            target, paths = evaluate(w,q)
            if dumps([target,paths]) != dumps(evaluate_sql(w,q)): raise ContractError("independent mismatch")
            print(dumps({"target":target,"proof_paths":paths,"episode_support":episode_support(w,target,paths),"query_scope":"diagnostic_uncued_second_scope" if w.mode == "episodic" and q.kind == "join" and q.second_cue is None else "declared_scope"}))
        elif args.command == "score":
            obj = loads(Path(args.input).read_text())
            from .core import keys
            keys(obj,("prediction","target"),"score input")
            print(dumps(score(obj["prediction"],obj["target"])))
    except (ContractError,FileExistsError,KeyError) as exc:
        print(f"{type(exc).__name__}: {exc}",file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
