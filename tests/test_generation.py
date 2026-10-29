import copy
import tempfile
from pathlib import Path
import unittest
from relational_episodes.core import ContractError, dumps, loads, parse_world
from relational_episodes.canonical import fingerprint
from relational_episodes.generate import families, SPLITS
from relational_episodes.release import build
from relational_episodes.validate import validate_family, validate_record, validate_release, world_of, WORLD_KEYS
from relational_episodes.render import model_question, selector_export


def config():
    return {"schema_version":"relational-episodes-config/1.0","semantic_contract":"protocol-semantic-conventions/1.2","seed":8391,"structural":dict.fromkeys(SPLITS,0),"episodic":dict.fromkeys(SPLITS,0)}


class Generation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c = config(); c["structural"]["interface_train"] = 1; c["episodic"]["development"] = 1
        cls.groups = list(families(c))

    def test_retained_regular_episode_collision_regression(self):
        evidence = loads((Path(__file__).resolve().parents[1]/"reports/canonical_collision_01.json").read_text())
        first,second = evidence["first"],evidence["second"]
        self.assertEqual(first["audit"]["fingerprint"],second["audit"]["fingerprint"])
        self.assertNotEqual(fingerprint(world_of(first)),fingerprint(world_of(second)))
        # Check full 64-entity/4-relation renaming and row-order invariance,
        # including the exact regular world that previously collided.
        raw = {k:copy.deepcopy(first[k]) for k in WORLD_KEYS}
        mapping = {}
        for key in ("entities","relations","source_edges","aliases_with_scope","episodes"):
            for row in raw[key]:
                mapping[row["id"]] = "Renamed"+row["id"]
                for field in ("cue","alias"):
                    if field in row:mapping[row[field]] = "Renamed"+row[field]
        def rename(v):
            if type(v) is str:return mapping.get(v,v)
            if type(v) is list:return [rename(x) for x in reversed(v)]
            if type(v) is dict:return {k:rename(x) for k,x in v.items()}
            return v
        self.assertEqual(fingerprint(world_of(first)),fingerprint(parse_world(rename(raw))))

    def test_controls_every_frozen_cell(self):
        for group in self.groups:
            report = validate_family(group)
            self.assertTrue(report["lexical_invariance"])
            self.assertTrue(report["source_byte_invariance"])
            for record in group:
                validate_record(record)
        episodic = self.groups[1]
        self.assertEqual({r["audit"]["variant"] for r in episodic},{"base","overlap","aliases","distractors","compressibility"})
        bycell = {r["audit"]["variant"]:r for r in episodic}
        self.assertEqual(bycell["base"]["audit"]["alias_distinct_entity_histogram"],{"1":64})
        self.assertEqual(bycell["aliases"]["audit"]["alias_distinct_entity_histogram"],{"2":64})
        self.assertGreater(bycell["compressibility"]["audit"]["source_zlib_bytes"],bycell["base"]["audit"]["source_zlib_bytes"])

    def test_bag_of_words_cannot_resolve_motif_pair(self):
        a,b = self.groups[0]
        self.assertEqual(a["audit"]["lexical_counts"],b["audit"]["lexical_counts"])
        self.assertEqual(a["queries"],b["queries"])
        self.assertTrue(any(a["target_sets"][k] != b["target_sets"][k] for k in a["target_sets"] if k.startswith("join")))

    def test_targets_and_traces_cannot_be_tampered(self):
        original = self.groups[0][0]
        mutations = [lambda r:r["target_sets"].update(extra={"kind":"entity_set","values":[]}),lambda r:r["queries"][0].update(prompt="Give any answer"),lambda r:r["audit"].update(source_utf8_bytes=True),lambda r:r.update(source_text=r["source_text"]+"\n"),lambda r:r["source_edges"][0].update(acquisition_batch=True),lambda r:r["audit"].update(query_exposure="evaluation_only")]
        for mut in mutations:
            r = copy.deepcopy(original); mut(r)
            with self.assertRaises(ContractError): validate_record(r)
        for qid, paths in original["proof_paths"].items():
            if paths:
                r = copy.deepcopy(original)
                r["proof_paths"][qid][0]["cross_batch"] = int(paths[0]["cross_batch"])
                with self.assertRaises(ContractError): validate_record(r)
                break

    def test_malformed_audit_and_proof_containers(self):
        for field in ("audit","target_sets","proof_paths","queries","entities","counterfactual_links"):
            for bad in (True,None,7):
                r = copy.deepcopy(self.groups[0][0]); r[field] = bad
                with self.subTest(field=field,bad=bad), self.assertRaises(ContractError): validate_record(r)

    def test_source_and_question_allowlists(self):
        for group in self.groups:
            for r in group:
                export = selector_export(r)
                self.assertEqual(set(export),{"episode_set_or_graph_id","variant_id","mode","source_records"})
                self.assertNotIn("target_sets",dumps(export))
                self.assertNotIn("proof_paths",dumps(export))
                for q in r["queries"]:
                    self.assertEqual(set(model_question(q)),{"question","answer_format"})
                    self.assertNotIn(r["id"],dumps(model_question(q)))
                    self.assertNotIn("seed",dumps(model_question(q)))

    def test_family_integrity(self):
        group = copy.deepcopy(self.groups[0]); group[1]["split"] = "id_test"
        with self.assertRaises(ContractError): validate_family(group)
        group = copy.deepcopy(self.groups[1]); group.pop()
        with self.assertRaises(ContractError): validate_family(group)
        group = copy.deepcopy(self.groups[0]); group[0]["counterfactual_links"] = []
        with self.assertRaises(ContractError): validate_family(group)

    def test_reproducibility_and_grouped_split_release(self):
        c = config()
        c["structural"]["interface_train"] = 1; c["structural"]["id_test"] = 1
        c["episodic"]["development"] = 1; c["episodic"]["ood_names"] = 1
        with tempfile.TemporaryDirectory() as d:
            left,right = Path(d)/"one",Path(d)/"two"
            build(c,left); build(c,right)
            self.assertEqual({p.name:p.read_bytes() for p in left.iterdir()},{p.name:p.read_bytes() for p in right.iterdir()})
            report = validate_release(left)
            self.assertEqual(report["counts"]["records"],14)
            self.assertEqual(report["split_family_overlap"],0)
            with self.assertRaises(FileExistsError): build(c,left)
            with (left/"sources.jsonl").open("a") as f: f.write('{"target_sets":{}}\n')
            with self.assertRaises(ContractError): validate_release(left)

    def test_split_relabeling_rejected_by_concrete_regimes(self):
        c = config(); c["structural"]["ood_names"] = 1; c["structural"]["ood_topology"] = 1
        for group in families(c):
            r = copy.deepcopy(group[0]); r["split"] = "id_test"
            with self.assertRaises(ContractError): validate_record(r)

    def test_ood_name_template_and_topology_boundaries(self):
        c = config()
        for split in ("interface_train","ood_names","ood_template","ood_topology"):
            c["structural"][split] = 1
        groups = list(families(c))
        bysplit = {g[0]["split"]:g[0] for g in groups}
        known = {e["id"] for e in bysplit["interface_train"]["entities"]}
        novel = {e["id"] for e in bysplit["ood_names"]["entities"]}
        self.assertFalse(known & novel)
        self.assertEqual(bysplit["ood_template"]["audit"]["template"],"reverse")
        self.assertEqual(bysplit["ood_topology"]["audit"]["cluster_width"],16)
        self.assertEqual(bysplit["interface_train"]["audit"]["cluster_width"],8)
        self.assertEqual(len({r["episode_set_or_graph_id"] for r in bysplit.values()}),4)


if __name__ == "__main__": unittest.main()
