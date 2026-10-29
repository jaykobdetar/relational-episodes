"""Independent exact SQLite oracle.

Does not call engine binding, traversal, target or witness helpers. SQL joins
bind aliases to local fact occurrences, compose two relations and independently
materialize EVERY supporting edge/binding combination. No probabilistic labels.
"""
import json
import sqlite3


def evaluate_sql(world, query):
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript("""
        CREATE TABLE fact(id TEXT, s TEXT, r TEXT, o TEXT, ep TEXT, batch INTEGER, ordinal INTEGER);
        CREATE TABLE episode(id TEXT, cue TEXT, source TEXT);
        CREATE TABLE binding(id TEXT, alias TEXT, entity TEXT, ep TEXT);
        """)
        conn.executemany("INSERT INTO fact VALUES(?,?,?,?,?,?,?)", [(e.id,e.subject,e.relation,e.object,e.episode_id,e.acquisition_batch,e.occurrence) for e in world.edges])
        conn.executemany("INSERT INTO episode VALUES(?,?,?)", [(e.id,e.cue,e.source_text) for e in world.episodes])
        conn.executemany("INSERT INTO binding VALUES(?,?,?,?)", [(a.id,a.alias,a.entity,a.episode_id) for a in world.aliases])
        if query.kind == "reconstruct":
            eid, source = conn.execute("SELECT id,source FROM episode WHERE cue=?", (query.cue,)).fetchone()
            return {"kind":"source", "values":[source]}, [{"answer":source,"edge_ids":[],"binding_ids":[],"source_episode_id":eid,"cross_batch":False,"cross_episode":False}]
        params = [query.relations[0]]
        joins = "LEFT JOIN episode p ON p.id=a.ep"
        conditions = ["a.r=?"]
        binding_select = "NULL"
        if query.start.kind == "alias":
            joins += " JOIN binding b ON b.entity=a.s AND b.ep=a.ep"
            binding_select = "b.id"
            conditions.append("b.alias=?")
        else:
            conditions.append("a.s=?")
        params.append(query.start.value)
        if query.start.cue is not None:
            conditions.append("p.cue=?")
            params.append(query.start.cue)
        if query.kind == "join":
            joins += " JOIN fact z ON a.o=z.s"
            conditions.append("z.r=?")
            params.append(query.relations[1])
            if query.second_cue is not None:
                joins += " JOIN episode p2 ON p2.id=z.ep"
                conditions.append("p2.cue=?")
                params.append(query.second_cue)
            if query.episode_constraint == "distinct":
                conditions.append("a.ep <> z.ep")
            second_select = "z.id,z.o,z.ep,z.batch"
        else:
            second_select = "NULL,NULL,NULL,NULL"
        statement = f"SELECT a.id,a.s,a.r,a.o,a.ep,a.batch,a.ordinal,p.cue,{binding_select},{second_select} FROM fact a {joins} WHERE " + " AND ".join(conditions)
        targets, paths = {}, []
        encode = lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",",":"), allow_nan=False)
        for fid, s, r, o, ep, batch, ordinal, cue, bid, zid, zo, zep, zb in conn.execute(statement, params):
            answer = {"cue":cue,"occurrence":ordinal,"subject":s,"relation":r,"object":o} if query.kind == "all_matching" else (zo if query.kind == "join" else o)
            targets[encode(answer)] = answer
            paths.append({"answer":answer,"edge_ids":[fid] + ([zid] if zid is not None else []),"binding_ids":[bid] if bid is not None else [],"source_episode_id":None,"cross_batch":zid is not None and batch != zb,"cross_episode":zid is not None and ep != zep})
        return {"kind":"event_set" if query.kind == "all_matching" else "entity_set","values":[targets[k] for k in sorted(targets)]}, sorted(paths, key=encode)
    finally:
        conn.close()
