"""Byte regeneration into a caller-specified new directory; retain evidence."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from relational_episodes.core import dumps, loads
from relational_episodes.release import build
from relational_episodes.resources import check_headroom, limits
limits(); gate=check_headroom()
source=Path(sys.argv[1]); dest=Path(sys.argv[2]); report=Path(sys.argv[3])
manifest=loads((source/'manifest.json').read_text())
build(manifest['config'],dest)
names=sorted(p.name for p in source.iterdir() if p.is_file())
checks={name:(source/name).read_bytes()==(dest/name).read_bytes() for name in names}
with report.open('x') as f:f.write(dumps({'status':'passed' if all(checks.values()) else 'failed','files_identical':checks,'resource_gate':gate})+'\n')
print(dumps(checks))
raise SystemExit(0 if all(checks.values()) else 1)
