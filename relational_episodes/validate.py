"""Recompute targets/traces and enforce release-level lineage and controls."""
import hashlib
import itertools
import math
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from . import SCHEMA_VERSION
from .canonical import degree_signature, fingerprint
from .core import ContractError, dumps, integer, keys, loads, parse_query, parse_world, seq, token
from .coverage import episode_support
from .engine import evaluate
from .generate import L5_CELLS, SPLITS, validate_config
from .oracle import evaluate_sql
from .metrics import answer_entropies
from .render import edge_line, lexical_counts, model_question, render_episode, render_query, selector_export

WORLD_KEYS = ("mode","entities","relations","source_edges","aliases_with_scope","episodes")
RECORD_KEYS = ("schema_version","id","episode_set_or_graph_id","split",*WORLD_KEYS,"episode_id","acquisition_batch","source_text","queries","target_sets","proof_paths","counterfactual_links","audit")


def exact(left,right,message):
    if dumps(left) != dumps(right):
        raise ContractError(message)


def world_of(record):
    return parse_world({k:record[k] for k in WORLD_KEYS})


def validate_record(record):
    try:
        return _validate_record(record)
    except (KeyError,TypeError,AttributeError,UnicodeError) as exc:
        raise ContractError(f"malformed record: {exc}") from exc


def _validate_record(record):
    keys(record,RECORD_KEYS,"record")
    if record["schema_version"] != SCHEMA_VERSION: raise ContractError("unsupported record version")
    token(record["id"],"record.id"); token(record["episode_set_or_graph_id"],"family.id")
    if record["split"] not in SPLITS or record["episode_id"] is not None:
        raise ContractError("invalid split or aggregate episode_id")
    links = seq(record["counterfactual_links"],"counterfactual_links",32)
    for link in links: token(link,"counterfactual_link")
    if len(set(links)) != len(links) or record["id"] in links:
        raise ContractError("duplicate/self counterfactual link")
    w = world_of(record)
    prefix = ("S" if w.mode == "structural" else "M") + ("Novel" if record["split"] == "ood_names" else "Known")
    exact(sorted(e.id for e in w.entities),[f"{prefix}N{i:03}" for i in range(64)],"name dictionary/split mismatch")
    exact(sorted(r.id for r in w.relations),[f"{prefix}R{i}" for i in range(4)],"relation dictionary/split mismatch")
    exact(record["acquisition_batch"],sorted({e.acquisition_batch for e in w.edges}),"invalid aggregate acquisition batches")
    keys(record["target_sets"],record["proof_paths"],"target/proof query keys")
    expected_ids = []
    stats = Counter()
    for q in seq(record["queries"],"queries",512):
        keys(q,("id","kind","start","relations","episode_constraint","cue","first_cue","second_cue","prompt"),"record.query")
        formal = {k:v for k,v in q.items() if k != "prompt"}
        pq = parse_query(formal,w)
        expected_ids.append(pq.id)
        if pq.id not in record["target_sets"]: raise ContractError("missing target")
        exact(q["prompt"],render_query(formal),"prompt does not match formal question")
        target, paths = evaluate(w,pq)
        itarget, ipaths = evaluate_sql(w,pq)
        exact(target,itarget,"independent target mismatch")
        exact(paths,ipaths,"independent witness mismatch")
        exact(record["target_sets"][pq.id],target,"stored target mismatch")
        exact(record["proof_paths"][pq.id],paths,"stored proof mismatch")
        if w.mode == "episodic":
            support = episode_support(w,target,paths)
            exact(record["audit"]["episode_support"].get(pq.id),support,"support-cover audit mismatch")
            budget = 1 if pq.kind == "reconstruct" or (pq.kind == "atomic" and pq.start.cue is not None) else 2
            exact(record["audit"]["retrieval_budget_episodes"].get(pq.id),budget,"retrieval budget mismatch")
            if support["minimum_positive_answer_episode_cover"] > budget:
                raise ContractError("complete positive answer exceeds declared retrieval budget")
            if pq.kind == "join":
                if pq.first_cue is None or pq.second_cue is None or pq.first_cue == pq.second_cue or pq.episode_constraint != "distinct":
                    raise ContractError("primary L5 join must name two distinct public cues")
                if not set(support["supporting_public_cues"]) <= {pq.first_cue,pq.second_cue}:
                    raise ContractError("primary join support escapes two declared scopes")
        stats["queries"] += 1
        stats["witnesses"] += len(paths)
        stats["cross_batch_witnesses"] += sum(p["cross_batch"] for p in paths)
        stats["cross_episode_witnesses"] += sum(p["cross_episode"] for p in paths)
        if target["kind"] != "source":
            stats["empty_answer_queries"] += not target["values"]
            stats["multiple_answer_queries"] += len(target["values"]) > 1
        if pq.kind == "reconstruct": stats["source_reconstructions"] += 1
    if len(expected_ids) != len(set(expected_ids)) or set(expected_ids) != set(record["target_sets"]):
        raise ContractError("duplicate/extra query IDs")
    audit = record["audit"]
    if type(audit) is not dict: raise ContractError("audit must be object")
    if audit.get("template") not in ("plain","reverse"): raise ContractError("unknown template")
    if (record["split"] == "ood_template") != (audit["template"] == "reverse"):
        raise ContractError("template holdout violation")
    exact(audit.get("fingerprint"),fingerprint(w),"fingerprint mismatch")
    if w.mode == "structural":
        source = "\n".join(edge_line(e,audit["template"]) for e in record["source_edges"]) + "\n"
        if len(w.entities) != 64 or len(w.relations) != 4 or len(w.edges) != 256:
            raise ContractError("generated L3 bounded dimensions violated")
        if record["acquisition_batch"] != list(range(8)):
            raise ContractError("expected eight acquisition batches")
        width = 16 if record["split"] == "ood_topology" else 8
        exact(audit.get("cluster_width"),width,"topology regime/split mismatch")
        for cluster in audit["cluster_of"].values(): integer(cluster,"cluster label",0,64//width-1)
        exact(dict(Counter(audit["cluster_of"].values())),dict.fromkeys(range(64//width),width),"cluster partition size mismatch")
        exact(sorted(audit["cluster_of"]),sorted(e.id for e in w.entities),"cluster partition universe mismatch")
        exact(dict(Counter(e.acquisition_batch for e in w.edges)),dict.fromkeys(range(8),32),"batch size mismatch")
        if any(count != 2 for _,count in degree_signature(w)):
            raise ContractError("L3 nonzero relation degrees must equal two")
        expected_bridges = [e.id for e in w.edges if audit["cluster_of"][e.subject] != audit["cluster_of"][e.object]]
        exact(audit.get("bridge_edge_ids"),expected_bridges,"bridge audit mismatch")
    else:
        if len(w.episodes) != 32 or len(w.edges) != 256 or len(w.aliases) != 128:
            raise ContractError("generated L5 bounded dimensions violated")
        alias_prefix = "MX" if record["split"] == "ood_names" else "MA"
        cue_prefix = "Fresh" if record["split"] == "ood_names" else "Cue"
        symbol_prefix = "NewSym" if record["split"] == "ood_names" else "Sym"
        exact(sorted({a.alias for a in w.aliases}),[f"{alias_prefix}{i:03}" for i in range(64)],"alias dictionary/split mismatch")
        exact(sorted(e.cue for e in w.episodes),[f"{cue_prefix}{i:03}" for i in range(32)],"cue dictionary/split mismatch")
        exact(dict(Counter(a.alias for a in w.aliases)),dict.fromkeys((f"{alias_prefix}{i:03}" for i in range(64)),2),"alias frequency/retrieval budget mismatch")
        for ep in w.episodes:
            exact(sorted(audit["payloads"][ep.id]),[f"{symbol_prefix}{i:02}" for i in range(17)],"symbol dictionary/split mismatch")
            expected = render_episode(ep.cue,[a for a in record["aliases_with_scope"] if a["episode_id"] == ep.id],[e for e in record["source_edges"] if e["episode_id"] == ep.id],audit["payloads"][ep.id],audit["template"])
            exact(ep.source_text,expected,"episode source disagrees with formal facts/bindings/payload")
        source = "".join(ep.source_text for ep in w.episodes)
        exact(audit.get("episode_whitespace_tokens"),[len(ep.source_text.split()) for ep in w.episodes],"token count mismatch")
        if any(len(ep.source_text.split()) != 64 for ep in w.episodes):
            raise ContractError("bounded source must have exactly 64 whitespace tokens")
        alias_entities = {}
        for a in w.aliases: alias_entities.setdefault(a.alias,set()).add(a.entity)
        alias_hist = {str(k):v for k,v in sorted(Counter(len(v) for v in alias_entities.values()).items())}
        exact(audit.get("alias_distinct_entity_histogram"),alias_hist,"alias ambiguity audit mismatch")
        cell = audit.get("variant")
        if cell not in L5_CELLS: raise ContractError("unsupported pilot cell")
        exact(audit.get("factors"),dict(zip(("entity_overlap","alias_collision","distractor_density","compressibility"),L5_CELLS[cell])),"factor declaration mismatch")
    exact(record["source_text"],source,"aggregate source mismatch")
    exact(audit.get("whitespace_token_counts"),dict(sorted(Counter(source.split()).items())),"whitespace token audit mismatch")
    exact(audit.get("answer_identity_entropy"),answer_entropies(record["queries"],record["target_sets"]),"answer entropy audit mismatch")
    exact(audit.get("lexical_counts"),lexical_counts(source),"lexical audit mismatch")
    exact(audit.get("source_utf8_bytes"),len(source.encode()),"source byte audit mismatch")
    exact(audit.get("source_zlib_bytes"),len(zlib.compress(source.encode(),9)),"compression audit mismatch")
    exact(audit.get("source_sha256"),hashlib.sha256(source.encode()).hexdigest(),"source checksum mismatch")
    expected_exposure = "interface_supervision" if record["split"] == "interface_train" else "evaluation_only"
    exact(audit.get("query_exposure"),expected_exposure,"join supervision exposure error")
    cards = Counter(len(t["values"]) for t in record["target_sets"].values() if t["kind"] != "source")
    exact(audit.get("answer_cardinality_histogram"),{str(k):v for k,v in sorted(cards.items())},"cardinality audit mismatch")
    return dict(stats)


def cardinality_entropy(record):
    counts = Counter(len(t["values"]) for t in record["target_sets"].values() if t["kind"] != "source")
    total = sum(counts.values())
    return -sum((n/total)*math.log2(n/total) for n in counts.values()) if total else 0.0


def validate_family(records):
    if not records: raise ContractError("empty family")
    family = records[0]["episode_set_or_graph_id"]
    split = records[0]["split"]; mode = records[0]["mode"]
    ids = {r["id"] for r in records}
    variants = {r["audit"]["variant"]:r for r in records}
    expected = {"clustered","bridge"} if mode == "structural" else set(L5_CELLS)
    if set(variants) != expected or len(variants) != len(records): raise ContractError("incomplete/duplicate frozen cell set")
    for r in records:
        if (r["episode_set_or_graph_id"],r["split"],r["mode"]) != (family,split,mode):
            raise ContractError("family spans split/mode/lineage")
        exact(sorted(r["counterfactual_links"]),sorted(ids-{r["id"]}),"incomplete counterfactual links")
    baseline = variants["clustered" if mode == "structural" else "base"]
    expected_family = ("S" if mode == "structural" else "E") + fingerprint(world_of(baseline))[:24]
    if family != expected_family: raise ContractError("family does not match base lineage fingerprint")
    for r in records:
        exact(r["audit"]["whitespace_token_counts"],baseline["audit"]["whitespace_token_counts"],"paired full whitespace-token invariance failed")
        exact(r["audit"]["lexical_counts"],baseline["audit"]["lexical_counts"],"paired lexical invariance failed")
        exact(r["audit"]["source_utf8_bytes"],baseline["audit"]["source_utf8_bytes"],"paired byte length failed")
    if mode == "structural":
        exact(degree_signature(world_of(variants["clustered"])),degree_signature(world_of(variants["bridge"])),"degree-preserving rewiring failed")
        if variants["clustered"]["audit"]["bridge_edge_ids"] or len(variants["bridge"]["audit"]["bridge_edge_ids"]) != 256:
            raise ContractError("motif intervention does not change bridge count as declared")
        return {"degree_invariance":True,"lexical_invariance":True,"source_byte_invariance":True,"bridge_counts":[0,256]}
    # Explicitly measure the remaining confound instead of claiming entropy matching.
    entropy = {cell:cardinality_entropy(r) for cell,r in variants.items()}
    overlap = {}
    for cell,r in variants.items():
        entity_sets = [{e["subject"] for e in r["source_edges"] if e["episode_id"] == ep["id"]} | {e["object"] for e in r["source_edges"] if e["episode_id"] == ep["id"]} for ep in r["episodes"]]
        overlap[cell] = max(len(a&b) for a,b in itertools.combinations(entity_sets,2))
        exact(r["audit"].get("maximum_shared_entities_between_episodes"),overlap[cell],"overlap metric incorrect")
    if overlap["base"] != 2 or overlap["overlap"] != 4: raise ContractError("overlap intervention failed")
    return {"lexical_invariance":True,"source_byte_invariance":True,"maximum_episode_overlap":overlap,"answer_cardinality_entropy_bits":entropy,"answer_cardinality_entropy_matched":len(set(entropy.values())) == 1,"answer_identity_entropy_by_kind":{cell:r["audit"]["answer_identity_entropy"] for cell,r in variants.items()},"full_factorial":False,"compressibility_zlib_bytes":{cell:r["audit"]["source_zlib_bytes"] for cell,r in variants.items()}}


def validate_release(directory):
    directory = Path(directory)
    manifest = loads((directory/"manifest.json").read_text())
    if manifest.get("schema_version") != "relational-episodes-manifest/1.0": raise ContractError("manifest version")
    for name, meta in manifest["files"].items():
        if Path(name).name != name: raise ContractError("unsafe manifest filename")
        content = (directory/name).read_bytes()
        exact(hashlib.sha256(content).hexdigest(),meta["sha256"],f"hash mismatch: {name}")
        exact(len(content),meta["bytes"],f"byte mismatch: {name}")
    validate_config(manifest["config"])
    exact(manifest["config_sha256"],hashlib.sha256(dumps(manifest["config"]).encode()).hexdigest(),"config hash mismatch")
    stats = Counter(); families = {}; fingerprints = {}; ids = set(); family_reports = []
    split_counts = Counter(); split_families = Counter()
    with (directory/"records.jsonl").open() as records_file, (directory/"sources.jsonl").open() as sources_file, (directory/"questions.jsonl").open() as questions_file, (directory/"interface_supervision.jsonl").open() as supervision_file:
        current = []
        for line in records_file:
            r = loads(line)
            result = validate_record(r); stats.update(result); stats["records"] += 1
            fid = r["episode_set_or_graph_id"]; rid = r["id"]
            if rid in ids: raise ContractError("duplicate record ID")
            ids.add(rid)
            if fid in families and families[fid] != r["split"]: raise ContractError("family leakage")
            if fid not in families: split_families[r["mode"]+"/"+r["split"]] += 1
            families[fid] = r["split"]
            split_counts[r["mode"]+"/"+r["split"]] += 1
            fp = r["audit"]["fingerprint"]
            if fp in fingerprints and fingerprints[fp] != fid: raise ContractError("cross-family canonical collision; conservatively rejected")
            fingerprints[fp] = fid
            if current and current[0]["episode_set_or_graph_id"] != fid:
                family_reports.append({"id":current[0]["episode_set_or_graph_id"],"mode":current[0]["mode"],"split":current[0]["split"],**validate_family(current)})
                current = []
            current.append(r)
            export = loads(sources_file.readline())
            exact(export,selector_export(r),"source selector export contaminated or altered")
            qexport = loads(questions_file.readline())
            expected_questions = {"id":rid,"split":r["split"],"questions":[{"query_id":q["id"],"model_input":model_question(q)} for q in r["queries"]]}
            exact(qexport,expected_questions,"question allowlist failed")
            if r["split"] == "interface_train":
                expected_supervision = {"id":rid,"examples":[{"model_input":model_question(q),"target":r["target_sets"][q["id"]]} for q in r["queries"]]}
                exact(loads(supervision_file.readline()),expected_supervision,"interface supervision mismatch")
        if current: family_reports.append({"id":current[0]["episode_set_or_graph_id"],"mode":current[0]["mode"],"split":current[0]["split"],**validate_family(current)})
        if sources_file.readline() or questions_file.readline() or supervision_file.readline(): raise ContractError("extra exported rows")
    if len(family_reports) != len(families): raise ContractError("family rows must be contiguous")
    expected_counts = {mode+"/"+split:n*(2 if mode == "structural" else 5) for mode in ("structural","episodic") for split,n in manifest["config"][mode].items() if n}
    expected_families = {mode+"/"+split:n for mode in ("structural","episodic") for split,n in manifest["config"][mode].items() if n}
    exact(dict(split_counts),expected_counts,"record split counts disagree with config")
    exact(dict(split_families),expected_families,"family split counts disagree with config")
    exact(manifest["counts"],expected_counts,"manifest split counts disagree with config")
    exact(stats["records"],manifest["records"],"manifest count mismatch")
    exact(len(families),manifest["families"],"manifest family count mismatch")
    return {"status":"passed","schema_version":"relational-episodes-validation/1.0","counts":dict(stats),"families":family_reports,"split_family_overlap":0,"cross_family_canonical_collisions":0,"selector_export_allowlist":"passed","independent_oracle":"direct enumeration == SQLite targets AND complete witnesses","limitations":["smoke release is below protocol development and confirmation quotas","L5 has five one-factor cells; no factorial interaction claim","answer-cardinality entropy measured, not balanced; full L5 claim blocked","64 whitespace tokens is not a pretrained tokenizer audit","structural isomorphism guard is conservative color refinement, with possible false collisions","no model competence, memory retention, learned routing or compute-budget claims"]}
