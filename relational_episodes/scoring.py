"""Deterministic answer parsing with exact set accuracy and precision/recall."""
from .core import ContractError, dumps, integer, keys, token


def _event(v):
    keys(v,("cue","occurrence","subject","relation","object"),"event answer")
    if v["cue"] is not None: token(v["cue"],"event.cue")
    integer(v["occurrence"],"event.occurrence",1,8192)
    for k in ("subject","relation","object"): token(v[k],k)
    return dumps(v)


def normalize(value, kind):
    if kind == "source":
        if type(value) is not str:
            raise ContractError("source prediction must be a string")
        try: return value.encode("utf-8",errors="strict")
        except UnicodeError as exc: raise ContractError("invalid UTF-8 prediction") from exc
    if type(value) is not list or len(value) > 8192:
        raise ContractError("set prediction must be a bounded JSON array")
    if kind == "entity_set":
        items = [token(v,"entity answer") for v in value]
    elif kind == "event_set":
        items = [_event(v) for v in value]
    else:
        raise ContractError("unknown answer kind")
    if len(items) != len(set(items)):
        raise ContractError("duplicate answer elements; predictions must be sets")
    return set(items)


def score(prediction, target):
    keys(target,("kind","values"),"target")
    kind = target["kind"]
    if kind == "source":
        if type(target["values"]) is not list or len(target["values"]) != 1:
            raise ContractError("source target must have one exact string")
        expected = normalize(target["values"][0],kind)
    else:
        expected = normalize(target["values"],kind)
    try:
        actual = normalize(prediction,kind)
    except ContractError as exc:
        return {"valid":False,"exact":False,"precision":0.0,"recall":0.0,"error":str(exc)}
    if kind == "source":
        return {"valid":True,"exact":actual == expected,"precision":float(actual == expected),"recall":float(actual == expected),"predicted_utf8_bytes":len(actual),"target_utf8_bytes":len(expected)}
    hits = len(actual & expected)
    # Empty/empty is exact with P=R=1; an invented answer to empty gold has P=R=0.
    precision = hits / len(actual) if actual else float(not expected)
    recall = hits / len(expected) if expected else float(not actual)
    return {"valid":True,"exact":actual == expected,"precision":precision,"recall":recall,"true_positives":hits,"false_positives":len(actual-expected),"false_negatives":len(expected-actual)}
