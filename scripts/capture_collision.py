"""Preserve the first failed split-guard case before changing canonicalization."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from relational_episodes.core import dumps
from relational_episodes.generate import SPLITS, families
from relational_episodes.resources import check_headroom, limits
limits();check_headroom()
c={"schema_version":"relational-episodes-config/1.0","semantic_contract":"protocol-semantic-conventions/1.2","seed":8391,"structural":dict.fromkeys(SPLITS,0),"episodic":dict.fromkeys(SPLITS,0)}
c['structural']['interface_train']=1;c['structural']['id_test']=1;c['episodic']['development']=1;c['episodic']['ood_names']=1
seen={}
for family in families(c):
    for r in family:
        fp=r['audit']['fingerprint']
        if fp in seen and seen[fp]['episode_set_or_graph_id']!=r['episode_set_or_graph_id']:
            out=Path('reports/canonical_collision_01.json')
            with out.open('x') as f:f.write(dumps({'status':'retained_failed_guard_case','config':c,'first':seen[fp],'second':r})+'\n')
            print(dumps({'first':seen[fp]['id'],'second':r['id'],'fingerprint':fp,'evidence':str(out)}));raise SystemExit(0)
        seen[fp]=r
raise SystemExit('expected collision was not reproduced')
