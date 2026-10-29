import copy
from dataclasses import FrozenInstanceError
import itertools
import unittest
from relational_episodes.core import ContractError, dumps, loads, parse_query, parse_world
from relational_episodes.coverage import episode_support
from relational_episodes.engine import evaluate
from relational_episodes.oracle import evaluate_sql
from relational_episodes.canonical import fingerprint
from relational_episodes.generate import query, start, validate_config
from relational_episodes.scoring import score
from relational_episodes.render import retained_selector_view


def small_world(mask=0, episodic=False, binding=(0,1)):
    w = {"mode":"episodic" if episodic else "structural","entities":[{"id":"A","type":"node"},{"id":"B","type":"node"}],"relations":[{"id":r,"subject_type":"node","object_type":"node"} for r in (("R",) if episodic else ("R","S"))],"source_edges":[],"aliases_with_scope":[],"episodes":[]}
    if episodic:
        w["episodes"] = [{"id":"p0","cue":"CueA","source_text":"first\n"},{"id":"p1","cue":"CueB","source_text":"second\n"}]
        w["aliases_with_scope"] = [{"id":f"a{i}","alias":"Alias","entity":("A","B")[binding[i]],"episode_id":f"p{i}"} for i in range(2)]
        possibilities = [(s,"R",o,f"p{p}") for p in range(2) for s in ("A","B") for o in ("A","B")]
    else:
        possibilities = [(s,r,o,None) for s in ("A","B") for r in ("R","S") for o in ("A","B")]
    for i,(s,r,o,ep) in enumerate(possibilities):
        if mask & (1<<i): w["source_edges"].append({"id":f"e{i}","subject":s,"relation":r,"object":o,"episode_id":ep,"acquisition_batch":i%2,"occurrence":i+1})
    return w


class Exhaustive(unittest.TestCase):
    def agree(self,w,q):
        world = parse_world(w); query_value = parse_query(q,world)
        self.assertEqual(dumps(evaluate(world,query_value)),dumps(evaluate_sql(world,query_value)))

    def test_all_two_node_two_relation_graphs(self):
        # 2^(2*2*2)=256 graphs, 12 questions each, 3072 complete exact cross-checks.
        n = 0
        for mask in range(256):
            w = small_world(mask)
            for entity in ("A","B"):
                for r in ("R","S"):
                    self.agree(w,query("Q","atomic",start("entity",entity),[r])); n += 1
                for r,s in itertools.product(("R","S"),repeat=2):
                    self.agree(w,query("Q","join",start("entity",entity),[r,s])); n += 1
        self.assertEqual(n,3072)

    def test_all_two_episode_alias_worlds(self):
        # All 256 fact subsets x 4 alias assignments x 9 questions = 9216.
        n = 0
        for mask in range(256):
            for bindings in itertools.product(range(2),repeat=2):
                w = small_world(mask,True,bindings)
                for cue in (None,"CueA","CueB"):
                    for kind in ("atomic","all_matching"):
                        self.agree(w,query("Q",kind,start("alias","Alias",cue),["R"])); n += 1
                self.agree(w,query("Q","join",start("alias","Alias"),["R","R"],True)); n += 1
                for first,second in (("CueA","CueB"),("CueB","CueA")):
                    self.agree(w,query("Q","join",start("alias","Alias",first),["R","R"],True,second_cue=second)); n += 1
        self.assertEqual(n,9216)


class Semantics(unittest.TestCase):
    def solve(self,w,q):
        world = parse_world(w)
        return evaluate(world,parse_query(q,world))

    def test_duplicate_occurrences_and_alias_ambiguity(self):
        w = small_world(255,True,(0,1))
        dup = dict(w["source_edges"][0],id="extra",occurrence=20)
        w["source_edges"].append(dup)
        q = query("Q","all_matching",start("alias","Alias"),["R"])
        target, paths = self.solve(w,q)
        self.assertEqual(len(target["values"]),5)
        self.assertEqual(len(paths),5)
        self.assertEqual({v["cue"] for v in target["values"]},{"CueA","CueB"})
        world = parse_world(w)
        self.assertEqual(dumps((target,paths)),dumps(evaluate_sql(world,parse_query(q,world))))

    def test_alias_can_bind_multiple_entities_inside_visible_scope(self):
        raw = small_world(15,True,(0,1))
        raw["aliases_with_scope"].append({"id":"a2","alias":"Alias","entity":"B","episode_id":"p0"})
        q = query("Q","all_matching",start("alias","Alias","CueA"),["R"])
        target,paths = self.solve(raw,q)
        self.assertEqual(len(target["values"]),4)
        self.assertEqual({p["binding_ids"][0] for p in paths},{"a0","a2"})
        w = parse_world(raw)
        self.assertEqual(dumps((target,paths)),dumps(evaluate_sql(w,parse_query(q,w))))

    def test_local_alias_does_not_import_shared_entity_binding(self):
        w = small_world(0,True,(0,1))
        w["source_edges"] = [{"id":"e","subject":"A","relation":"R","object":"B","episode_id":"p1","acquisition_batch":1,"occurrence":1}]
        q = query("Q","atomic",start("alias","Alias"),["R"])
        self.assertEqual(self.solve(w,q)[0]["values"],[])

    def test_two_episode_constraint_excludes_same_episode(self):
        w = small_world(15,True,(0,0))
        any_q = query("Q","join",start("alias","Alias","CueA"),["R","R"])
        distinct_q = query("Q","join",start("alias","Alias","CueA"),["R","R"],True)
        self.assertEqual(set(self.solve(w,any_q)[0]["values"]),{"A","B"})
        self.assertEqual(self.solve(w,distinct_q)[0]["values"],[])

    def test_reconstruction_is_exact_utf8_including_newlines(self):
        w = small_world(0,True)
        w["episodes"][0]["source_text"] = "café e\u0301\r\n尾\n"
        q = query("Q","reconstruct",cue="CueA")
        target,_ = self.solve(w,q)
        self.assertTrue(score(w["episodes"][0]["source_text"],target)["exact"])
        self.assertFalse(score(w["episodes"][0]["source_text"].replace("\r\n","\n"),target)["exact"])
        self.assertFalse(score(w["episodes"][0]["source_text"].rstrip(),target)["exact"])

    def test_multiple_witnesses_single_endpoint_are_preserved(self):
        w = small_world(255)
        target,paths = self.solve(w,query("Q","join",start("entity","A"),["R","S"]))
        self.assertEqual(target["values"],["A","B"])
        self.assertEqual(len(paths),4)

    def test_world_is_frozen_and_detached_from_input(self):
        raw = small_world(1); w = parse_world(raw)
        raw["source_edges"][0]["subject"] = "B"
        self.assertEqual(w.edges[0].subject,"A")
        with self.assertRaises(FrozenInstanceError): w.edges[0].subject = "B"

    def test_scoped_second_source_and_exact_episode_cover(self):
        raw = small_world(0,True,(0,0))
        raw["episodes"].append({"id":"p2","cue":"CueC","source_text":"third\n"})
        raw["source_edges"] = [
            {"id":"x0","subject":"A","relation":"R","object":"A","episode_id":"p0","acquisition_batch":0,"occurrence":1},
            {"id":"x1","subject":"A","relation":"R","object":"A","episode_id":"p1","acquisition_batch":1,"occurrence":1},
            {"id":"x2","subject":"A","relation":"R","object":"B","episode_id":"p2","acquisition_batch":2,"occurrence":1}]
        q = query("Q","join",start("entity","A","CueA"),["R","R"],True)
        w = parse_world(raw); target,paths = evaluate(w,parse_query(q,w))
        coverage = episode_support(w,target,paths)
        self.assertEqual(coverage["minimum_positive_answer_episode_cover"],3)
        self.assertFalse(coverage["two_episode_positive_cover_feasible"])
        scoped = dict(q,second_cue="CueB")
        scoped_target,scoped_paths = evaluate(w,parse_query(scoped,w))
        self.assertEqual(scoped_target["values"],["A"])
        self.assertEqual(dumps((scoped_target,scoped_paths)),dumps(evaluate_sql(w,parse_query(scoped,w))))
        raw["source_edges"].append({"id":"x3","subject":"A","relation":"R","object":"B","episode_id":"p1","acquisition_batch":1,"occurrence":2})
        w = parse_world(raw); target,paths = evaluate(w,parse_query(q,w))
        coverage = episode_support(w,target,paths)
        self.assertEqual(coverage["minimum_positive_answer_episode_cover"],2)
        self.assertEqual(coverage["all_supporting_episode_count"],3)
        for bad in (dict(q,second_cue="p1"),dict(q,first_cue="CueB"),dict(q,second_cue=True)):
            with self.assertRaises(ContractError): parse_query(bad,w)

    def test_relation_type_checks(self):
        w = small_world(0)
        w["entities"][1]["type"] = "artifact"
        w["relations"][0]["object_type"] = "artifact"
        w["source_edges"] = [{"id":"E","subject":"A","relation":"R","object":"B","episode_id":None,"acquisition_batch":0,"occurrence":1}]
        w["source_edges"].append({"id":"E2","subject":"A","relation":"S","object":"A","episode_id":None,"acquisition_batch":0,"occurrence":2})
        self.assertEqual(self.solve(w,query("Q","join",start("entity","A"),["R","S"]))[0]["values"],[])
        w["source_edges"][0]["object"] = "A"
        with self.assertRaises(ContractError): parse_world(w)


class Adversarial(unittest.TestCase):
    def test_strict_numeric_fields_and_shapes(self):
        for field in ("occurrence","acquisition_batch"):
            for value in (True,False,1.0,"1",None,[],{},-1,100000000):
                w = small_world(1); w["source_edges"][0][field] = value
                with self.subTest(field=field,value=value), self.assertRaises(ContractError): parse_world(w)
        w = small_world(1); w["source_edges"][0]["occurrence"] = 0
        with self.assertRaises(ContractError): parse_world(w)
        for field,value in (("subject","Missing"),("relation","Missing"),("object",True),("id","bad\n"),("episode_id","p0")):
            w = small_world(1); w["source_edges"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ContractError): parse_world(w)
        for value in (None,[],True,{},[1]):
            with self.assertRaises(ContractError): parse_world(value)

    def test_duplicates_unknown_fields_and_broken_scopes(self):
        mutations = [lambda w:w["entities"].append(w["entities"][0]),lambda w:w.update(extra=0),lambda w:w["source_edges"].append(dict(w["source_edges"][0],id="fresh")),lambda w:w["episodes"][1].update(cue="CueA"),lambda w:w["aliases_with_scope"][0].update(episode_id="missing"),lambda w:w["source_edges"][0].update(episode_id=None)]
        for mut in mutations:
            w = small_world(1,True); mut(w)
            with self.assertRaises(ContractError): parse_world(w)
        for raw in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}','[','{"x":{"a":1,"a":2}}'):
            with self.assertRaises(ContractError): loads(raw)
        w = small_world(0,True); w["episodes"][0]["source_text"] = "\ud800"
        with self.assertRaises(ContractError): parse_world(w)

    def test_query_validation(self):
        w = parse_world(small_world(1,True))
        base = query("Q","atomic",start("alias","Alias"),["R"])
        mutations = [lambda q:q.update(kind="bogus"),lambda q:q.update(relations=["R","R"]),lambda q:q.update(cue="CueA"),lambda q:q.update(episode_constraint="distinct"),lambda q:q["start"].update(cue="p0"),lambda q:q["start"].update(value="Unknown"),lambda q:q["start"].update(kind="entity",value="Alias"),lambda q:q.update(start=None),lambda q:q.update(relations=[False])]
        for mut in mutations:
            q = copy.deepcopy(base); mut(q)
            with self.assertRaises(ContractError): parse_query(q,w)
        for cue in (None,"p0",True,"Unknown"):
            with self.assertRaises(ContractError): parse_query(query("Q","reconstruct",cue=cue),w)

    def test_config_bool_int(self):
        from relational_episodes.generate import SPLITS
        good = {"schema_version":"relational-episodes-config/1.0","semantic_contract":"protocol-semantic-conventions/1.2","seed":3,"structural":dict.fromkeys(SPLITS,0),"episodic":dict.fromkeys(SPLITS,0)}
        for bad in (True,False,1.0,-1,"2"):
            c = copy.deepcopy(good); c["seed"] = bad
            with self.assertRaises(ContractError): validate_config(c)
            c = copy.deepcopy(good); c["structural"]["development"] = bad
            with self.assertRaises(ContractError): validate_config(c)
        c = copy.deepcopy(good); c["episodic"]["ood_topology"] = 1
        with self.assertRaises(ContractError): validate_config(c)


class ScoringAndLeakage(unittest.TestCase):
    def test_set_order_empty_and_invented_answers(self):
        target = {"kind":"entity_set","values":["A","B"]}
        self.assertTrue(score(["B","A"],target)["exact"])
        result = score(["A","C"],target)
        self.assertEqual((result["precision"],result["recall"]),(0.5,0.5))
        self.assertFalse(score(["A","A"],target)["valid"])
        self.assertFalse(score([True],target)["valid"])
        empty = {"kind":"entity_set","values":[]}
        self.assertEqual(score([],empty)["precision"],1)
        self.assertEqual(score(["A"],empty)["recall"],0)
        self.assertEqual(score([],target)["precision"],0)
        evt = {"cue":"CueA","occurrence":1,"subject":"A","relation":"R","object":"B"}
        target = {"kind":"event_set","values":[evt]}
        for bad in (True,1.0,0):
            self.assertFalse(score([dict(evt,occurrence=bad)],target)["valid"])

    def test_renaming_and_order_invariance(self):
        for episodic in (False,True):
            raw = small_world(237,episodic)
            fp = fingerprint(parse_world(raw))
            remap = {"A":"RenamedZ","B":"RenamedY","R":"OtherT","S":"OtherU","p0":"EpisodeZ","p1":"EpisodeY","CueA":"VisibleZ","CueB":"VisibleY","Alias":"Nick"}
            remap.update({e["id"]:"New"+e["id"] for e in raw["source_edges"]})
            remap.update({a["id"]:"New"+a["id"] for a in raw["aliases_with_scope"]})
            def rename(v):
                if type(v) is str: return remap.get(v,v)
                if type(v) is list: return [rename(x) for x in reversed(v)]
                if type(v) is dict: return {k:rename(x) for k,x in v.items()}
                return v
            self.assertEqual(fp,fingerprint(parse_world(rename(raw))))

    def test_retained_source_boundary(self):
        export = {"mode":"structural","source_records":[{"edge_id":"e0","acquisition_batch":0,"text":"one"},{"edge_id":"e1","acquisition_batch":1,"text":"two"},{"edge_id":"e2","acquisition_batch":2,"text":"three"}]}
        view = retained_selector_view(export,["e0","e2"],1)
        self.assertEqual([r["edge_id"] for r in view],["e0"])
        self.assertNotIn("queries",dumps(view))
        with self.assertRaises(ValueError): retained_selector_view(export,["missing"],9)
        with self.assertRaises(ValueError): retained_selector_view(export,["e0"],True)


if __name__ == "__main__": unittest.main()
