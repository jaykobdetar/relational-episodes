"""Strict input contract and frozen semantic values.

JSON bool is never accepted as int. Unknown fields, duplicate keys, nonfinite
numbers, dangling references, duplicate occurrence ordinals within a scope and type errors
are rejected before either evaluator runs.
"""
from dataclasses import dataclass
import json
import re


class ContractError(ValueError):
    pass


def keys(value, required, where):
    if type(value) is not dict or set(value) != set(required):
        raise ContractError(f"{where}: expected exactly {sorted(required)}")


def seq(value, where, maximum=10000):
    if type(value) is not list or len(value) > maximum:
        raise ContractError(f"{where}: expected list of at most {maximum}")
    return value


def token(value, where):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value):
        raise ContractError(f"{where}: expected safe identifier")
    return value


def integer(value, where, low=0, high=10000):
    if type(value) is not int or not low <= value <= high:
        raise ContractError(f"{where}: expected integer in [{low},{high}]")
    return value


def text(value, where):
    if type(value) is not str:
        raise ContractError(f"{where}: expected string")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ContractError(f"{where}: invalid UTF-8 text") from exc
    if len(value.encode("utf-8")) > 1_000_000:
        raise ContractError(f"{where}: text exceeds byte bound")
    return value


def loads(raw):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ContractError(f"duplicate JSON key: {k}")
            out[k] = v
        return out
    def constant(x):
        raise ContractError(f"nonfinite JSON number: {x}")
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=constant)
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ContractError(f"invalid JSON: {exc}") from exc


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class Entity:
    id: str
    type: str


@dataclass(frozen=True)
class Relation:
    id: str
    subject_type: str
    object_type: str


@dataclass(frozen=True)
class Edge:
    id: str
    subject: str
    relation: str
    object: str
    episode_id: str | None
    acquisition_batch: int
    occurrence: int


@dataclass(frozen=True)
class Alias:
    id: str
    alias: str
    entity: str
    episode_id: str


@dataclass(frozen=True)
class Episode:
    id: str
    cue: str
    source_text: str


@dataclass(frozen=True)
class World:
    mode: str
    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...]
    edges: tuple[Edge, ...]
    aliases: tuple[Alias, ...]
    episodes: tuple[Episode, ...]


@dataclass(frozen=True)
class Start:
    kind: str
    value: str
    cue: str | None


@dataclass(frozen=True)
class Query:
    id: str
    kind: str
    start: Start | None
    relations: tuple[str, ...]
    episode_constraint: str
    cue: str | None
    first_cue: str | None
    second_cue: str | None


def unique_ids(rows, where):
    ids = [row.id for row in rows]
    if len(set(ids)) != len(ids):
        raise ContractError(f"{where}: duplicate id")


def parse_world(data):
    keys(data, ("mode", "entities", "relations", "source_edges", "aliases_with_scope", "episodes"), "world")
    if data["mode"] not in ("structural", "episodic"):
        raise ContractError("mode: structural or episodic required")
    entities = []
    for v in seq(data["entities"], "entities", 1024):
        keys(v, ("id", "type"), "entity")
        entities.append(Entity(token(v["id"], "entity.id"), token(v["type"], "entity.type")))
    relations = []
    for v in seq(data["relations"], "relations", 16):
        keys(v, ("id", "subject_type", "object_type"), "relation")
        relations.append(Relation(*(token(v[k], k) for k in ("id", "subject_type", "object_type"))))
    episodes = []
    for v in seq(data["episodes"], "episodes", 128):
        keys(v, ("id", "cue", "source_text"), "episode")
        episodes.append(Episode(token(v["id"], "episode.id"), token(v["cue"], "episode.cue"), text(v["source_text"], "source_text")))
    for name, rows in (("entities", entities), ("relations", relations), ("episodes", episodes)):
        unique_ids(rows, name)
    if not entities or not relations:
        raise ContractError("nonempty entities and relations required")
    et = {e.id: e.type for e in entities}
    rs = {r.id: r for r in relations}
    epids = {e.id for e in episodes}
    if len({e.cue for e in episodes}) != len(episodes):
        raise ContractError("visible episode cues must be unique")
    for r in relations:
        if r.subject_type not in set(et.values()) or r.object_type not in set(et.values()):
            raise ContractError("relation has undeclared entity type")
    edges = []
    facts = set()
    for v in seq(data["source_edges"], "source_edges", 8192):
        keys(v, ("id", "subject", "relation", "object", "episode_id", "acquisition_batch", "occurrence"), "edge")
        eid, s, r, o = (token(v[k], k) for k in ("id", "subject", "relation", "object"))
        ep = v["episode_id"]
        batch = integer(v["acquisition_batch"], "acquisition_batch", 0, 127)
        if s not in et or o not in et or r not in rs:
            raise ContractError("edge contains unknown entity or relation")
        if et[s] != rs[r].subject_type or et[o] != rs[r].object_type:
            raise ContractError("relation domain/range mismatch")
        if data["mode"] == "structural":
            if ep is not None:
                raise ContractError("structural edge cannot name an episode")
        else:
            token(ep, "episode_id")
            if ep not in epids:
                raise ContractError("unknown edge episode")
        ordinal = integer(v["occurrence"], "occurrence", 1, 8192)
        fact = (ep, ordinal)
        if fact in facts:
            raise ContractError("duplicate public occurrence in one scope")
        facts.add(fact)
        edges.append(Edge(eid, s, r, o, ep, batch, ordinal))
    unique_ids(edges, "edges")
    aliases = []
    bindings = set()
    for v in seq(data["aliases_with_scope"], "aliases", 8192):
        keys(v, ("id", "alias", "entity", "episode_id"), "alias")
        a = Alias(*(token(v[k], k) for k in ("id", "alias", "entity", "episode_id")))
        if a.entity not in et or a.episode_id not in epids:
            raise ContractError("dangling alias binding")
        if (a.alias, a.entity, a.episode_id) in bindings:
            raise ContractError("duplicate alias binding")
        bindings.add((a.alias, a.entity, a.episode_id))
        aliases.append(a)
    unique_ids(aliases, "aliases")
    if data["mode"] == "structural" and (episodes or aliases):
        raise ContractError("structural world cannot contain episodes/aliases")
    if data["mode"] == "episodic" and not episodes:
        raise ContractError("episodic world requires episodes")
    return World(data["mode"], tuple(entities), tuple(relations), tuple(edges), tuple(aliases), tuple(episodes))


def parse_query(data, world):
    keys(data, ("id", "kind", "start", "relations", "episode_constraint", "cue", "first_cue", "second_cue"), "query")
    qid = token(data["id"], "query.id")
    kind = data["kind"]
    if kind not in ("atomic", "join", "all_matching", "reconstruct"):
        raise ContractError("unknown query kind")
    rels = seq(data["relations"], "query.relations", 2)
    for r in rels:
        token(r, "query.relation")
        if r not in {v.id for v in world.relations}:
            raise ContractError("query relation unknown")
    if data["episode_constraint"] not in ("any", "distinct"):
        raise ContractError("invalid episode_constraint")
    if data["episode_constraint"] == "distinct" and (kind != "join" or world.mode != "episodic"):
        raise ContractError("distinct episodes requires an episodic join")
    cue = data["cue"]
    cues = {e.cue for e in world.episodes}
    first_cue, second_cue = data["first_cue"], data["second_cue"]
    for scope in (first_cue,second_cue):
        if scope is not None:
            token(scope,"join cue")
            if kind != "join" or world.mode != "episodic" or scope not in cues:
                raise ContractError("join cue requires episodic join and known public cue")
    if kind == "reconstruct":
        token(cue, "query.cue")
        if world.mode != "episodic" or cue not in cues or data["start"] is not None or rels:
            raise ContractError("reconstruction requires known visible cue, no start or relations")
        return Query(qid, kind, None, (), "any", cue, None, None)
    if cue is not None or len(rels) != (2 if kind == "join" else 1):
        raise ContractError("invalid relation count or unexpected cue")
    keys(data["start"], ("kind", "value", "cue"), "query.start")
    s = data["start"]
    val = token(s["value"], "start.value")
    if s["kind"] not in ("entity", "alias"):
        raise ContractError("invalid start kind")
    if s["cue"] is not None:
        token(s["cue"], "start.cue")
        if s["cue"] not in cues:
            raise ContractError("unknown visible cue")
    if s["kind"] == "entity":
        if val not in {e.id for e in world.entities}:
            raise ContractError("unknown start entity")
    elif world.mode != "episodic" or val not in {a.alias for a in world.aliases}:
        raise ContractError("unknown start alias")
    if kind == "join" and first_cue != s["cue"]:
        raise ContractError("first_cue must equal the explicit start scope")
    return Query(qid, kind, Start(s["kind"], val, s["cue"]), tuple(rels), data["episode_constraint"], None, first_cue, second_cue)
