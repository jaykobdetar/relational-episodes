"""Exact support-cover accounting for positive answers, never selector input."""
from .core import ContractError, dumps


def episode_support(world, target, paths):
    if world.mode != "episodic":
        return None
    edges = {e.id:e.episode_id for e in world.edges}
    cues = {e.id:e.cue for e in world.episodes}
    choices = {}
    supporting = set()
    for path in paths:
        episodes = {edges[e] for e in path["edge_ids"]}
        if path["source_episode_id"] is not None:
            episodes.add(path["source_episode_id"])
        supporting.update(episodes)
        choices.setdefault(dumps(path["answer"]),set()).add(frozenset(episodes))
    states = {frozenset()}
    for answer in target["values"]:
        paths_for_answer = choices.get(dumps(answer),set())
        if not paths_for_answer:
            raise ContractError("positive answer has no episode support")
        unions = {s|p for s in states for p in paths_for_answer}
        # Keep exact Pareto-minimal sets. No greedy approximation or arbitrary
        # witness choice can make an infeasible retrieval budget appear feasible.
        kept = []
        for candidate in sorted(unions,key=lambda s:(len(s),sorted(s))):
            if not any(prev <= candidate for prev in kept): kept.append(candidate)
        if len(kept) > 10000:
            raise ContractError("exact episode-cover diagnostic exceeds bounded state budget")
        states = set(kept)
    minimum = min(map(len,states))
    return {"minimum_positive_answer_episode_cover":minimum,"all_supporting_episode_count":len(supporting),"supporting_public_cues":sorted(cues[e] for e in supporting),"two_episode_positive_cover_feasible":minimum <= 2,"empty_answer_note":"zero positive support does not certify absence without reading the declared scopes" if not target["values"] else None}
