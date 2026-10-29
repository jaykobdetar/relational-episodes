"""Production evaluator: literal source-edge and edge-pair enumeration."""
from .core import dumps


def _bindings(world, query, edge):
    s = query.start
    ep_by_id = {e.id: e for e in world.episodes}
    if s.cue is not None and (edge.episode_id is None or ep_by_id[edge.episode_id].cue != s.cue):
        return ()
    if s.kind == "entity":
        return (None,) if edge.subject == s.value else ()
    # Aliases bind locally. An unscoped query ranges over occurrences; it never
    # imports another episode's binding merely because the entity is shared.
    return tuple(a.id for a in world.aliases if a.alias == s.value and a.entity == edge.subject and a.episode_id == edge.episode_id)


def evaluate(world, query):
    if query.kind == "reconstruct":
        ep = next(e for e in world.episodes if e.cue == query.cue)
        return {"kind": "source", "values": [ep.source_text]}, [{"answer": ep.source_text, "edge_ids": [], "binding_ids": [], "source_episode_id": ep.id, "cross_batch": False, "cross_episode": False}]
    answers = {}
    paths = []
    eps = {e.id: e.cue for e in world.episodes}
    for first in world.edges:
        if first.relation != query.relations[0]:
            continue
        for binding in _bindings(world, query, first):
            seconds = world.edges if query.kind == "join" else (None,)
            for second in seconds:
                if second is not None:
                    if second.subject != first.object or second.relation != query.relations[1]:
                        continue
                    if query.second_cue is not None and eps.get(second.episode_id) != query.second_cue:
                        continue
                    if query.episode_constraint == "distinct" and first.episode_id == second.episode_id:
                        continue
                if query.kind == "all_matching":
                    answer = {"cue": eps.get(first.episode_id), "occurrence": first.occurrence, "subject": first.subject, "relation": first.relation, "object": first.object}
                else:
                    answer = first.object if second is None else second.object
                answers[dumps(answer)] = answer
                paths.append({"answer": answer, "edge_ids": [first.id] + ([second.id] if second else []), "binding_ids": [] if binding is None else [binding], "source_episode_id": None, "cross_batch": second is not None and first.acquisition_batch != second.acquisition_batch, "cross_episode": second is not None and first.episode_id != second.episode_id})
    target = {"kind": "event_set" if query.kind == "all_matching" else "entity_set", "values": [answers[k] for k in sorted(answers)]}
    return target, sorted(paths, key=dumps)
