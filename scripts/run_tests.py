"""Resource-gated sequential tests with immutable numbered reports."""
from pathlib import Path
import resource
import sys
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from relational_episodes.core import dumps
from relational_episodes.resources import check_headroom, limits

limits()
root = Path(__file__).resolve().parent.parent
reports = root/"reports"
reports.mkdir(parents=True, exist_ok=True)
index = 1
while any((reports/f"test_run_{index:02}.{suffix}").exists() for suffix in ("log", "json")): index += 1
log = reports/f"test_run_{index:02}.log"
report_path = reports/f"test_run_{index:02}.json"
started = time.monotonic()
try:
    gate = check_headroom()
except Exception as exc:
    with log.open("x") as stream: stream.write(f"PAUSED: {exc}\n")
    report_path.write_text(dumps({"status":"paused","reason":str(exc)})+"\n")
    print(log.read_text()); raise SystemExit(2)
with log.open("x") as stream:
    suite = unittest.defaultTestLoader.discover(str(root/"tests"))
    result = unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
report = {"status":"passed" if result.wasSuccessful() else "failed","tests_run":result.testsRun,"failures":[[str(t),trace] for t,trace in result.failures],"errors":[[str(t),trace] for t,trace in result.errors],"skipped":[[str(t),reason] for t,reason in result.skipped],"seconds":time.monotonic()-started,"peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"resource_gate":gate,"exhaustive_scope":{"structural_fact_subsets":256,"structural_query_comparisons":3072,"episodic_fact_subsets":256,"alias_assignments_per_subset":4,"episodic_query_comparisons":9216},"no_probability_labels":True}
report_path.write_text(dumps(report)+"\n")
print(dumps({k:report[k] for k in ("status","tests_run","seconds","peak_rss_kib")}))
print(log)
raise SystemExit(0 if result.wasSuccessful() else 1)
