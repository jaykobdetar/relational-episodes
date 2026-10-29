"""Optional generic schema verification and mechanically derived API examples."""
from pathlib import Path
import hashlib
from importlib.metadata import version
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from jsonschema import Draft202012Validator
from relational_episodes.core import dumps, loads, parse_query
from relational_episodes.engine import evaluate
from relational_episodes.oracle import evaluate_sql
from relational_episodes.resources import check_headroom, limits
from relational_episodes.validate import WORLD_KEYS, world_of
limits();check_headroom()
root=Path(__file__).resolve().parent.parent
schema=loads((root/'schemas/record-v1.schema.json').read_text())
Draft202012Validator.check_schema(schema);validator=Draft202012Validator(schema)
count=0;example=None
for line in (root/'data/smoke/records.jsonl').open():
    record=loads(line);validator.validate(record);count+=1
    if example is None and record['mode']=='episodic':example=record
world=world_of(example)
q=next(q for q in example['queries'] if q['kind']=='join')
formal={k:v for k,v in q.items() if k!='prompt'}
target,proof=evaluate(world,parse_query(formal,world))
assert dumps([target,proof])==dumps(evaluate_sql(world,parse_query(formal,world)))
(root/'examples/problem.json').write_text(json.dumps({'world':{k:example[k] for k in WORLD_KEYS},'query':formal},indent=2)+'\n')
(root/'examples/problem.answer.json').write_text(dumps({'target':target,'proof_paths':proof})+'\n')
(root/'examples/scoring.json').write_text(dumps({'target':target,'prediction':list(reversed(target['values']))})+'\n')
(root/'examples/episode_bundle.txt').write_text(example['episodes'][0]['source_text'])
initial=root/'data/smoke_initial';final=root/'data/smoke'
unchanged={name:(initial/name).read_bytes()==(final/name).read_bytes() for name in ('records.jsonl','sources.jsonl','questions.jsonl','interface_supervision.jsonl')}
report={'status':'passed','schema_validator':'jsonschema '+version('jsonschema'),'draft':'2020-12','records_validated':count,'initial_to_final_data_files_identical':unchanged,'initial_snapshot_note':'Final manifest adds runtime/config/schema hashes and updated implementation hashes after validator hardening; no data labels/worlds changed. Initial snapshot retained in data/smoke_initial.','schema_sha256':hashlib.sha256((root/'schemas/record-v1.schema.json').read_bytes()).hexdigest(),'examples':'Derived from first emitted episodic record; exact production/SQL agreement; example predictions are mechanical fixtures, not model outputs.'}
if not all(unchanged.values()):raise AssertionError('unexpected scientific data change')
with (root/'reports/schema_and_examples_01.json').open('x') as f:f.write(dumps(report)+'\n')
print(dumps(report))
