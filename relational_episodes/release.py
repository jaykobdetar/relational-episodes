"""Streaming release builder; refuses overwrite and retains partial evidence."""
from importlib.resources import files as package_files
import hashlib
import platform
import sqlite3
from collections import Counter
from pathlib import Path
from .core import ContractError, dumps
from .generate import families, validate_config
from .render import model_question, selector_export
from .validate import validate_family


def build(config, output, max_bytes=28_000_000):
    validate_config(config)
    out = Path(output)
    out.mkdir(parents=True,exist_ok=False)
    names = ("records.jsonl","sources.jsonl","questions.jsonl","interface_supervision.jsonl")
    handles = {n:(out/n).open("x",encoding="utf-8",newline="\n") for n in names}
    counts = Counter(); total = 0; seen = {}; groups = set(); records = 0
    try:
        for family in families(config):
            validate_family(family)
            for r in family:
                fid = r["episode_set_or_graph_id"]; fp = r["audit"]["fingerprint"]
                if fp in seen and seen[fp] != fid:
                    raise ContractError("conservative cross-family fingerprint collision; no hidden reseeding")
                seen[fp] = fid; groups.add(fid); records += 1
                counts[r["mode"]+"/"+r["split"]] += 1
                exports = {"records.jsonl":r,"sources.jsonl":selector_export(r),"questions.jsonl":{"id":r["id"],"split":r["split"],"questions":[{"query_id":q["id"],"model_input":model_question(q)} for q in r["queries"]]}}
                if r["split"] == "interface_train":
                    exports["interface_supervision.jsonl"] = {"id":r["id"],"examples":[{"model_input":model_question(q),"target":r["target_sets"][q["id"]]} for q in r["queries"]]}
                for name, data in exports.items():
                    line = dumps(data)+"\n"; total += len(line.encode())
                    if total > max_bytes:
                        raise ContractError("artifact budget exceeded; partial output retained for inspection")
                    handles[name].write(line)
    except Exception as exc:
        (out/"FAILED.txt").write_text(type(exc).__name__+": "+str(exc)+"\n")
        raise
    finally:
        for handle in handles.values(): handle.close()
    files = {}
    for name in names:
        raw = (out/name).read_bytes()
        files[name] = {"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
    root = Path(__file__).resolve().parent.parent
    implementation = {}
    for path in sorted((root/"relational_episodes").glob("*.py")):
        implementation[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    pinned = {path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((root/"inputs").glob("*.json"))}
    manifest = {"schema_version":"relational-episodes-manifest/1.0","python_runtime":{"implementation":platform.python_implementation(),"version":platform.python_version(),"sqlite":sqlite3.sqlite_version},"record_schema_sha256":hashlib.sha256(package_files("relational_episodes").joinpath("schemas/record-v1.schema.json").read_bytes()).hexdigest(),"config_sha256":hashlib.sha256(dumps(config).encode()).hexdigest(),"config":config,"records":records,"families":len(groups),"counts":dict(sorted(counts.items())),"files":files,"implementation_sha256":implementation,"pinned_spec_sha256":pinned,"pinned_spec_status":"present_unverified" if pinned else "not_in_source_distribution","label_provenance":"formal source system only; exact labels; no models or teachers","generation_policy":"five-cell L5 one-factor pilot, immutable snapshots; no label-based filtering or reseeding","seed_visibility":"manifest audit only; never model input","model_input_allowlist":["question","answer_format"],"source_access":"sources.jsonl only, intersect acquired facts and explicit retained budget; IDs and indices count as bytes","evaluation_access":"records.jsonl includes targets/proofs and is evaluator-only outside disjoint interface_train","budget_bytes":max_bytes,"serialized_export_bytes":total,"full_protocol_readiness_claim":False}
    (out/"manifest.json").write_text(dumps(manifest)+"\n",encoding="utf-8")
    return manifest
