"""Conservative isomorphism-invariant split guard, not a general GI solver.

Names, IDs, text, row order and query variants are omitted. Each world becomes
an incidence graph containing entities, relations, edges, episodes, alias tokens
and bindings. Exact colour refinement is invariant to any renaming/permutation.
Up to four relation roles are exhaustively individualized modulo all role
permutations before taking the minimum fingerprint. Nonisomorphic worlds can collide: the release rejects such collisions across
families rather than pretending this is an exact graph-isomorphism algorithm.
"""
import hashlib
import itertools
from functools import lru_cache
from collections import Counter
from .core import dumps


@lru_cache(maxsize=64)
def fingerprint(world):
    relations = [r.id for r in world.relations]
    if len(relations) <= 4:
        # Individualizing all four relation roles resolves the observed regular
        # episode collision, while enumerating EVERY role permutation preserves
        # relation-renaming invariance. No symbol-name tie-break or reseeding.
        assignments = (dict(zip(relations,order)) for order in itertools.permutations(range(len(relations))))
    else:
        # General engine inputs can contain more relation types. Use a bounded
        # conservative anchor invariant rather than factorial explosion.
        assignments = ({r:int(r == anchor) for r in relations} for anchor in relations)
    return min(_refined_fingerprint(world,marks) for marks in assignments)


def _refined_fingerprint(world, relation_marks):
    nodes, links = {}, []
    def node(key, color):
        nodes[key] = color
    def link(left, right, role):
        links.append((left, right, role))
    for e in world.entities:
        node(("entity", e.id), ("entity", e.type))
    for r in world.relations:
        node(("relation", r.id), ("relation", r.subject_type, r.object_type, relation_marks[r.id]))
    for ep in world.episodes:
        node(("episode", ep.id), ("episode",))
    for edge in world.edges:
        k = ("edge", edge.id)
        node(k, ("edge", edge.acquisition_batch))
        for kind, val, role in (("entity",edge.subject,"subject"),("entity",edge.object,"object"),("relation",edge.relation,"relation")):
            link(k,(kind,val),role)
        if edge.episode_id is not None:
            link(k,("episode",edge.episode_id),"episode")
    for a in world.aliases:
        node(("alias_token",a.alias), ("alias_token",))
        k = ("binding",a.id)
        node(k, ("binding",))
        for kind, val in (("alias_token",a.alias),("entity",a.entity),("episode",a.episode_id)):
            link(k,(kind,val),kind)
    adjacency = {k: [] for k in nodes}
    for left,right,role in links:
        adjacency[left].append(("out",role,right))
        adjacency[right].append(("in",role,left))
    unique = sorted(set(nodes.values()))
    codes = {x:i for i,x in enumerate(unique)}
    colors = {k:codes[v] for k,v in nodes.items()}
    while True:
        signatures = {k:(colors[k],tuple(sorted((direction,role,colors[other]) for direction,role,other in adjacency[k]))) for k in nodes}
        codebook = {x:i for i,x in enumerate(sorted(set(signatures.values())))}
        refined = {k:codebook[v] for k,v in signatures.items()}
        stable = len(set(refined.values())) == len(set(colors.values()))
        colors = refined
        if stable:
            break
    # Initial color categories remain encoded explicitly, including types and batches.
    summary = {"mode":world.mode,"nodes":sorted((nodes[k],colors[k]) for k in nodes),"links":sorted((colors[l],colors[r],role) for l,r,role in links)}
    return hashlib.sha256(dumps(summary).encode()).hexdigest()


def degree_signature(world):
    counts = Counter()
    for e in world.edges:
        counts[(e.subject,e.relation,"out")] += 1
        counts[(e.object,e.relation,"in")] += 1
    return sorted((key,counts[key]) for key in counts)
