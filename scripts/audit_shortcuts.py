"""Measured non-model heuristic controls; does not filter examples or targets."""
from collections import Counter, defaultdict
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from relational_episodes.core import dumps, loads
from relational_episodes.resources import check_headroom, limits

limits(); check_headroom()
release = Path(sys.argv[1]); output = Path(sys.argv[2])
groups = defaultdict(list); by_kind = defaultdict(Counter); by_cell = defaultdict(Counter)
for line in (release/'records.jsonl').open():
    r = loads(line); groups[r['episode_set_or_graph_id']].append(r)
    for q in r['queries']:
        target = r['target_sets'][q['id']]
        if target['kind'] == 'source': continue
        bucket = by_kind[r['mode']+'/'+q['kind']]
        bucket['queries'] += 1
        bucket['always_empty_exact'] += not target['values']
        bucket['multiple_answers'] += len(target['values']) > 1
        bucket['singleton_answers'] += len(target['values']) == 1
        cell = by_cell[r['mode']+'/'+r['audit']['variant']]
        cell['queries'] += 1
        cell['empty'] += not target['values']
        cell['multiple'] += len(target['values']) > 1
pair_reports = []
for family,records in groups.items():
    if records[0]['mode'] != 'structural': continue
    a,b = records
    changes = sum(a['target_sets'][q['id']] != b['target_sets'][q['id']] for q in a['queries'] if q['kind']=='join')
    pair_reports.append({'family':family,'same_lexical_multiset':a['audit']['lexical_counts']==b['audit']['lexical_counts'],'same_questions':a['queries']==b['queries'],'changed_join_targets':changes,'total_join_questions':16})
report = {'schema_version':'relational-episodes-shortcut-audit/1.0','status':'measured_no_filtering','heuristics':{k:dict(v,always_empty_accuracy=v['always_empty_exact']/v['queries']) for k,v in by_kind.items()},'cells':{k:dict(v) for k,v in by_cell.items()},'structural_bag_of_words_pairs':pair_reports,'scope':'Simple source-agnostic empty-answer and cardinality controls only. Does not rule out other shortcuts. L5 answer-cardinality balance remains a protocol gate; no examples removed or resampled.'}
with output.open('x') as f: f.write(dumps(report)+'\n')
print(dumps(report))
