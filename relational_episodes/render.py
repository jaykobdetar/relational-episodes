"""Deterministic original source templates; labels never enter rendering."""
from collections import Counter
import re
from .core import dumps


def edge_line(edge, template="plain"):
    if template == "plain":
        return f"{edge['occurrence']}: {edge['subject']} {edge['relation']} {edge['object']}"
    if template == "reverse":
        return f"{edge['occurrence']}: {edge['object']} <-{edge['relation']}- {edge['subject']}"
    raise ValueError("unknown template")


def render_episode(cue, bindings, edges, payload, template):
    if template == "plain":
        lines = [f"Episode {cue}"]
        lines += [f"{a['alias']} = {a['entity']}" for a in bindings]
    elif template == "reverse":
        lines = [f"Bundle {cue}"]
        lines += [f"{a['entity']} as {a['alias']}" for a in bindings]
    else:
        raise ValueError("unknown template")
    lines += [edge_line(e, template) for e in edges]
    lines += ["Symbols " + " ".join(payload)]
    return "\n".join(lines) + "\n"


def lexical_counts(source):
    # Precise audit tokenizer for invariance only; NOT a pretrained tokenizer.
    return dict(sorted(Counter(re.findall(r"[A-Za-z][A-Za-z0-9_]*", source)).items()))


def render_query(q):
    if q["kind"] == "reconstruct":
        return f"Return the exact UTF-8 source text of the bundle with visible cue {q['cue']}, including its final newline."
    s = q["start"]
    who = f"{s['kind']} {s['value']}" + (f" in bundle {s['cue']}" if s["cue"] else " in every matching scope")
    if q["kind"] == "atomic":
        return f"Return the set of entities reached from {who} by {q['relations'][0]}."
    if q["kind"] == "all_matching":
        return f"Return all source events from {who} by {q['relations'][0]} as a JSON array of objects with cue, occurrence, subject, relation, object."
    scope = " The two facts must come from different bundles." if q["episode_constraint"] == "distinct" else ""
    if q["second_cue"] is not None:
        scope += f" The second fact must be in bundle {q['second_cue']}."
    return f"Return the set of endpoints from {who} by {q['relations'][0]} then {q['relations'][1]}.{scope}"


def model_question(q):
    # Explicit allowlist; no internal query IDs, proofs, targets, seed or variant.
    return {"question": render_query(q), "answer_format": "exact_source" if q["kind"] == "reconstruct" else ("event_set" if q["kind"] == "all_matching" else "entity_set")}


def selector_export(record):
    """Only original observed source facts; no queries or test supervision.

    Group/variant IDs are storage bookkeeping, not model input. Their bytes are
    reported by the release writer. Experiment code must subset this file to
    its acquired batches and retained budget BEFORE handing it to a selector.
    """
    if record["mode"] == "structural":
        items = [{"edge_id": e["id"], "acquisition_batch": e["acquisition_batch"], "text": edge_line(e, record["audit"]["template"])} for e in record["source_edges"]]
    else:
        batch_by_ep = {e["episode_id"]:e["acquisition_batch"] for e in record["source_edges"]}
        items = [{"cue":ep["cue"], "acquisition_batch":batch_by_ep[ep["id"]], "text":ep["source_text"]} for ep in record["episodes"]]
    return {"episode_set_or_graph_id":record["episode_set_or_graph_id"], "variant_id":record["id"], "mode":record["mode"], "source_records":items}


def retained_selector_view(export, retained_keys, acquired_batch):
    """Hard boundary: returned facts are the intersection of retained + observed.

    No use of a hidden full graph. Retention input is an explicit caller-supplied
    set; this library supplies neither a replay policy nor additional questions.
    """
    if type(acquired_batch) is not int or acquired_batch < 0:
        raise ValueError("acquired_batch must be nonnegative strict int")
    if type(retained_keys) not in (list, tuple, set) or any(type(k) is not str for k in retained_keys):
        raise ValueError("retained_keys must be strings")
    key = "edge_id" if export["mode"] == "structural" else "cue"
    known = {row[key] for row in export["source_records"]}
    if not set(retained_keys) <= known:
        raise ValueError("retained key absent from provided source export")
    return [dict(row) for row in export["source_records"] if row[key] in retained_keys and row["acquisition_batch"] <= acquired_batch]
