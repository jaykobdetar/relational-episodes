"""Optional JSON Schema check of a caller-supplied generated release.

Requires jsonschema in an isolated environment. Does not recreate historical
receipts or overwrite the committed examples.
"""
import argparse
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jsonschema import Draft202012Validator
from relational_episodes.core import dumps, loads
from relational_episodes.resources import check_headroom, limits

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('release', type=Path)
parser.add_argument('--report', required=True, type=Path)
args = parser.parse_args()
limits(); check_headroom()
schema = loads(files('relational_episodes').joinpath('schemas/record-v1.schema.json').read_text(encoding='utf-8'))
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema)
count = 0
with (args.release/'records.jsonl').open(encoding='utf-8') as stream:
    for line in stream:
        validator.validate(loads(line))
        count += 1
report = {'status': 'passed', 'schema_validator': 'jsonschema '+version('jsonschema'),
          'draft': '2020-12', 'records_validated': count,
          'scope': 'Current release schema validation only; no historical comparison'}
args.report.parent.mkdir(parents=True, exist_ok=True)
with args.report.open('x', encoding='utf-8') as stream:
    stream.write(dumps(report)+'\n')
print(dumps(report))
