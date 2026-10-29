"""Seeded source-only worlds. No labels are used for rejection or cell selection."""
import copy
import hashlib
import itertools
import random
import zlib
from collections import Counter
from . import SCHEMA_VERSION
from .canonical import fingerprint
from .core import ContractError, dumps, integer, keys, parse_query, parse_world
from .coverage import episode_support
from .engine import evaluate
from .oracle import evaluate_sql
from .metrics import answer_entropies
from .render import edge_line, lexical_counts, render_episode, render_query

SPLITS = ("interface_train", "development", "id_test", "ood_names", "ood_template", "ood_topology")
L5_CELLS = {"base": (0,0,0,0), "overlap": (1,0,0,0), "aliases": (0,1,0,0), "distractors": (0,0,1,0), "compressibility": (0,0,0,1)}


def rng_for(seed, *parts):
    material = dumps([seed,*parts]).encode()
    return random.Random(int.from_bytes(hashlib.sha256(material).digest(), "big"))


def validate_config(config):
    keys(config, ("schema_version", "semantic_contract", "seed", "structural", "episodic"), "config")
    if config["schema_version"] != "relational-episodes-config/1.0":
        raise ContractError("unsupported config version")
    if config["semantic_contract"] != "protocol-semantic-conventions/1.2":
        raise ContractError("G3 requires frozen semantic contract 1.2")
    integer(config["seed"], "seed", 0, 2**63-1)
    for mode in ("structural","episodic"):
        keys(config[mode], SPLITS, mode)
        for split, n in config[mode].items():
            integer(n, f"{mode}.{split}", 0, 1000)
    if config["episodic"]["ood_topology"]:
        raise ContractError("episodic topology OOD not implemented; use explicit paired controls")
    return config


def query(qid, kind, start=None, relations=(), distinct=False, cue=None, second_cue=None):
    return {"id":qid,"kind":kind,"start":start,"relations":list(relations),"episode_constraint":"distinct" if distinct else "any","cue":cue,"first_cue":start["cue"] if kind == "join" and start is not None else None,"second_cue":second_cue}


def start(kind, value, cue=None):
    return {"kind":kind,"value":value,"cue":cue}


def _vocabulary(mode, split, rng):
    prefix = ("S" if mode == "structural" else "M") + ("Novel" if split == "ood_names" else "Known")
    names = [f"{prefix}N{i:03}" for i in range(64)]
    rng.shuffle(names)
    relations = [f"{prefix}R{i}" for i in range(4)]
    rng.shuffle(relations)
    return names, relations


def structural_raw(seed, split, index):
    rng = rng_for(seed, "structural", split, index)
    names, rels = _vocabulary("structural", split, rng)
    world = {"mode":"structural","entities":[{"id":n,"type":"node"} for n in names],"relations":[{"id":r,"subject_type":"node","object_type":"node"} for r in rels],"source_edges":[],"aliases_with_scope":[],"episodes":[]}
    # OOD changes cluster size (8 -> 16) at fixed 64 entities, 4 relations,
    # 256 facts, 8 batches and directed degree in {0,2}. It is not a size holdout.
    width = 16 if split == "ood_topology" else 8
    per_relation = []
    for r in rels:
        chunks = []
        for block in range(0,64,width):
            src = list(range(block,block+width)); dst = src.copy()
            rng.shuffle(src); rng.shuffle(dst)
            src = src[:width//2]; dst = dst[:width//2]
            chunk = []
            for i,s in enumerate(src):
                for shift in (0,1):
                    chunk.append((names[s],r,names[dst[(i+shift)%len(dst)]]))
            chunks.append(chunk)
        per_relation.append(chunks)
    batches = list(range(8))*32
    rng.shuffle(batches)
    cluster_of = {names[i]: i//width for i in range(64)}
    for chunks in per_relation:
        for chunk in chunks:
            for s,r,o in chunk:
                i = len(world["source_edges"])
                world["source_edges"].append({"id":f"edge{i:04}","subject":s,"relation":r,"object":o,"episode_id":None,"acquisition_batch":batches[i],"occurrence":i+1})
    bridge = copy.deepcopy(world)
    # Destination permutation among blocks: exactly preserves the indegree of
    # every node for every relation, and each source's outgoing relation degree.
    rel_size = 64
    for r_idx in range(4):
        for block in range(64//width):
            other = (block+1) % (64//width)
            for offset in range(width):
                at = r_idx*rel_size + block*width + offset
                target = r_idx*rel_size + other*width + offset
                bridge["source_edges"][at]["object"] = world["source_edges"][target]["object"]
    # Query bank selected before evaluating answers, including all ordered
    # relation pairs and a balanced coverage of source entities.
    queries = []
    for i in range(16):
        queries.append(query(f"atomic{i:02}","atomic",start("entity",names[(i*7)%64]),[rels[i%4]]))
    for i,(r,s) in enumerate(itertools.product(rels, repeat=2)):
        queries.append(query(f"join{i:02}","join",start("entity",names[(i*11)%64]),[r,s]))
    for i in range(4):
        queries.append(query(f"events{i}","all_matching",start("entity",names[i]),[rels[i]]))
    return [("clustered",world),("bridge",bridge)], queries, {"cluster_of":cluster_of,"cluster_width":width}


def episodic_raw(seed, split, index):
    rng = rng_for(seed,"episodic",split,index)
    names, rels = _vocabulary("episodic",split,rng)
    prefix = "MX" if split == "ood_names" else "MA"
    aliases = [f"{prefix}{i:03}" for i in range(64)]; rng.shuffle(aliases)
    cues = [f"{'Fresh' if split == 'ood_names' else 'Cue'}{i:03}" for i in range(32)]; rng.shuffle(cues)
    symbols = [f"{'NewSym' if split == 'ood_names' else 'Sym'}{i:02}" for i in range(17)]
    template = "reverse" if split == "ood_template" else "plain"
    result = []
    query_banks = {}
    plans = {}
    for i in range(32):
        local_rng = rng_for(seed,"episode_structure",split,index,i)
        roles = list(range(4)); rmap = list(range(4))
        local_rng.shuffle(roles); local_rng.shuffle(rmap)
        plans[i] = (roles,rmap)
    # Five frozen one-factor cells. Full factorial interactions are not claimed.
    for cell,(overlap,collision,density,compressibility) in L5_CELLS.items():
        w = {"mode":"episodic","entities":[{"id":n,"type":"node"} for n in names],"relations":[{"id":r,"subject_type":"node","object_type":"node"} for r in rels],"source_edges":[],"aliases_with_scope":[],"episodes":[]}
        slots = [[(4*(i//2)+j)%64 if overlap else (2*i+j)%64 for j in range(4)] for i in range(32)]
        seen = set(); seconds = []
        for i,row in enumerate(slots):
            for j,n in enumerate(row):
                if n in seen: seconds.append((i,j,n))
                seen.add(n)
        alias_slots = [row.copy() for row in slots]
        if collision:
            # A deterministic cyclic derangement of second occurrences; every
            # alias token still occurs exactly twice, but binds two entities.
            for shift in range(1,len(seconds)):
                candidate = [row.copy() for row in slots]
                for k,(i,j,n) in enumerate(seconds):
                    candidate[i][j] = seconds[(k+shift)%len(seconds)][2]
                if all(len(set(row)) == 4 for row in candidate):
                    alias_slots = candidate
                    break
            else:
                raise RuntimeError("no valid alias collision permutation")
        patterns = [(0,0,1),(2,0,3),(1,1,2),(3,1,0),(0,2,2),(1,2,3),(2,3,0),(3,3,1)]
        if density:
            patterns = [(0,0,1),(0,0,3),(1,1,2),(3,1,2),(1,2,0),(2,2,1),(2,3,3),(3,3,0)]
        payloads = {}
        for i,row in enumerate(slots):
            epid = f"episode{i:03}"
            local_aliases = []
            for j,n in enumerate(row):
                a = {"id":f"binding{i:03}_{j}","alias":aliases[alias_slots[i][j]],"entity":names[n],"episode_id":epid}
                local_aliases.append(a); w["aliases_with_scope"].append(a)
            local_edges = []
            roles,rmap = plans[i]
            for ordinal,(s,r,o) in enumerate(patterns,1):
                e = {"id":f"fact{i:03}_{ordinal}","subject":names[row[roles[s]]],"relation":rels[rmap[r]],"object":names[row[roles[o]]],"episode_id":epid,"acquisition_batch":i,"occurrence":ordinal}
                local_edges.append(e); w["source_edges"].append(e)
            payload = symbols.copy()
            if compressibility:
                rng_for(seed,"payload",split,index,i).shuffle(payload)
            payloads[epid] = payload
            w["episodes"].append({"id":epid,"cue":cues[i],"source_text":render_episode(cues[i],local_aliases,local_edges,payload,template)})
        queries = []
        for i in (0,7,16,31):
            roles,rmap = plans[i]
            queries.append(query(f"source{i:02}","reconstruct",cue=cues[i]))
            queries.append(query(f"atomic{i:02}","atomic",start("alias",aliases[alias_slots[i][roles[0]]],cues[i]),[rels[rmap[0]]]))
            pivot = slots[i][roles[1]]
            partner = next(j for j,row in enumerate(slots) if j != i and pivot in row)
            queries.append(query(f"join{i:02}","join",start("alias",aliases[alias_slots[i][roles[0]]],cues[i]),[rels[rmap[0]],rels[rmap[1]]],True,second_cue=cues[partner]))
            queries.append(query(f"events{i:02}","all_matching",start("alias",aliases[alias_slots[i][roles[0]]]),[rels[rmap[0]]]))
        # Fixed lexical query across alias intervention; all matching bindings.
        queries.append(query("ambiguous","atomic",start("alias",aliases[0]),[rels[0]]))
        result.append((cell,w,{"payloads":payloads,"slots":slots,"plans":{str(i):plans[i] for i in plans},"factors":{"entity_overlap":overlap,"alias_collision":collision,"distractor_density":density,"compressibility":compressibility}}))
        query_banks[cell] = queries
    return result, query_banks


def _record(world, queries, split, family, variant, metadata):
    parsed = parse_world(world)
    targets, paths = {}, {}
    rendered_queries = []
    for q in queries:
        pq = parse_query(q,parsed)
        target, trace = evaluate(parsed,pq)
        independent = evaluate_sql(parsed,pq)
        if dumps([target,trace]) != dumps(independent):
            raise AssertionError(f"independent oracle mismatch in {family}/{variant}/{q['id']}")
        targets[q["id"]] = target; paths[q["id"]] = trace
        rendered_queries.append(dict(q,prompt=render_query(q)))
    template = "reverse" if split == "ood_template" else "plain"
    source = "".join(e["source_text"] for e in world["episodes"]) if world["mode"] == "episodic" else "\n".join(edge_line(e,template) for e in world["source_edges"]) + "\n"
    answer_cardinality = dict(Counter(len(t["values"]) for t in targets.values() if t["kind"] != "source"))
    audit = dict(metadata, template=template, fingerprint=fingerprint(parsed), lexical_counts=lexical_counts(source), whitespace_token_counts=dict(sorted(Counter(source.split()).items())), answer_identity_entropy=answer_entropies(queries,targets), source_utf8_bytes=len(source.encode()), source_sha256=hashlib.sha256(source.encode()).hexdigest(), source_zlib_bytes=len(zlib.compress(source.encode(),9)), answer_cardinality_histogram={str(k):v for k,v in sorted(answer_cardinality.items())}, label_origin="direct exact edge enumeration cross-checked by independent SQLite joins", query_exposure="interface_supervision" if split == "interface_train" else "evaluation_only", forbidden_selector_fields=["queries","target_sets","proof_paths","audit","counterfactual_links"])
    if world["mode"] == "episodic":
        audit["episode_support"] = {q["id"]:episode_support(parsed,targets[q["id"]],paths[q["id"]]) for q in queries}
        audit["retrieval_budget_episodes"] = {q["id"]:(1 if q["kind"] == "reconstruct" or (q["kind"] == "atomic" and q["start"]["cue"] is not None) else 2) for q in queries}
        audit["retrieval_budget_policy"] = "equal across compared methods within each query kind; join=2, all_matching=2 (each alias occurs in exactly two bundles), unscoped atomic=2, scoped atomic/reconstruction=1"
        audit["episode_whitespace_tokens"] = [len(e["source_text"].split()) for e in world["episodes"]]
        audit["tokenizer_audit"] = "whitespace only; pretrained tokenizer audit pending"
        audit["maximum_shared_entities_between_episodes"] = max(len(set(a)&set(b)) for a,b in itertools.combinations(metadata["slots"],2))
        alias_entities = {}
        for a in world["aliases_with_scope"]: alias_entities.setdefault(a["alias"],set()).add(a["entity"])
        audit["alias_distinct_entity_histogram"] = {str(k):v for k,v in sorted(Counter(len(v) for v in alias_entities.values()).items())}
    else:
        audit["bridge_edge_ids"] = [e["id"] for e in world["source_edges"] if metadata["cluster_of"][e["subject"]] != metadata["cluster_of"][e["object"]]]
    return {"schema_version":SCHEMA_VERSION,"id":family+"_"+variant,"episode_set_or_graph_id":family,"split":split,**world,"episode_id":None,"acquisition_batch":sorted({e["acquisition_batch"] for e in world["source_edges"]}),"source_text":source,"queries":rendered_queries,"target_sets":targets,"proof_paths":paths,"counterfactual_links":[],"audit":audit}


def families(config):
    validate_config(config)
    for mode in ("structural","episodic"):
        for split in SPLITS:
            for index in range(config[mode][split]):
                if mode == "structural":
                    worlds, queries, meta = structural_raw(config["seed"],split,index)
                    family = "S" + fingerprint(parse_world(worlds[0][1]))[:24]
                    records = [_record(w,queries,split,family,variant,dict(meta,variant=variant)) for variant,w in worlds]
                else:
                    worlds, queries = episodic_raw(config["seed"],split,index)
                    # Base skeleton is deliberately shared across paired controls.
                    # The family key omits names, renderings, questions and IDs;
                    # random local relation/role plans distinguish topology seeds.
                    skeleton = worlds[0][1]
                    family = "E" + fingerprint(parse_world(skeleton))[:24]
                    records = [_record(w,queries[variant],split,family,variant,dict(meta,variant=variant)) for variant,w,meta in worlds]
                for rec in records:
                    rec["counterfactual_links"] = [r["id"] for r in records if r["id"] != rec["id"]]
                yield records
