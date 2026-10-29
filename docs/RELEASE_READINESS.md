# Release readiness review — 2026-10-29

Repository visibility must remain private pending owner review. This review prepared source distribution fixes; it does not restore the original research bundle.

## Completed

- [x] Used an isolated checkout of `jaykobdetar/relational-episodes`, starting at `787c27c`; installed project dependencies only in a task-local virtual environment.
- [x] Reviewed the current documentation, manifests, runtime paths, tests and the sole imported Git commit. No original pre-preservation history exists in this repository.
- [x] Scanned all 36 unique tracked blobs in that commit for common credential patterns, personal absolute paths and email addresses: no matches. Commit attribution uses a GitHub noreply address. This is a bounded review, not a guarantee of absence of every possible secret.
- [x] Preserved provenance qualifications and distinguished historical execution claims from current results; repaired dangling documentation links.
- [x] Packaged the JSON Schema as a runtime resource, tested the installed wheel outside the checkout, and explicitly marked unavailable pinned specifications in fresh manifests.
- [x] Made the test report directory self-initializing and numbered reports respect both existing log and JSON paths.
- [x] Kept the missing historical collision test as an explicit skip; added independent generated-world renaming coverage. No fabricated collision evidence or experiment specification was added.
- [x] Reworked optional schema checking to accept current data without missing historical snapshots or rewriting committed examples. The collision diagnostic writes a differently named current receipt, never the missing historical fixture.
- [x] Ignored local build, dataset and report outputs so newly generated evidence is not accidentally committed.

## Verification

Linux, CPython 3.14.7. No model, GPU, training workload, full-capacity generation, or paid service was run.

| Check | Actual result |
|---|---|
| `python3 scripts/guarded_run.py --prefix reports/release-review-tests -- python3 scripts/run_tests.py` | Passed: 29 discovered, 28 passed, 1 explicitly skipped; no errors/failures. Test runner 8.05 s, peak RSS 35,792 KiB; supervisor plus child peak 50,984 KiB. |
| Exhaustive small-world oracle checks (within suite) | 3,072 structural and 9,216 episodic query comparisons, including complete witnesses. |
| Release round trip (within suite) | Two identical 14-record builds and validation; existing-output refusal and tampered-export rejection passed. |
| Isolated wheel build/install | Built with isolated PyPI build dependencies; installed without runtime dependencies. Initial `--no-build-isolation` attempt failed because fresh venv lacked setuptools; normal isolated build succeeded. |
| Installed package, working directory outside checkout | Built and validated one structural family / two records under the supervisor; packaged schema digest `7bf509020273eeb6e6be56a4bb26bcc43568e832a84901572b5152111076fc55`; missing-spec status explicitly present. |
| CLI help, committed solve/score examples | Passed; solve cross-checks direct/SQLite answers; scoring reports valid and exact. |
| Optional schema helper | Fresh two-record CLI build passed Draft 2020-12 validation with jsonschema 4.26.0 under the supervisor. |
| Whitespace review | `git diff --check` passed. |

Detailed generated execution receipts remain local under ignored `reports/`; the facts above are a human-readable review record. Historical reports have not been restored. Python 3.10–3.13 and non-Linux systems were not tested. Full smoke/configuration-capacity runs and cross-version reproducibility are not claimed.

## Owner decisions and remaining blockers

- [ ] Confirm authorship and third-party provenance, preserve any required notices, then choose and add an appropriate license. No license was invented or applied during this review.
- [ ] Decide whether public scope is explicitly the experimental source-only toolkit. If claiming historical reproduction or protocol conformance, recover and review the missing pinned specifications, original collision fixture, dataset card and original validation artifacts first. Do not substitute freshly generated data for historical evidence.
- [ ] Review the private draft PR and its exact branch, then separately authorize any public visibility change.
- [ ] Before research claims: complete answer-entropy balancing, pretrained-tokenizer audit, competence gates, adequate independent samples and external review. Current tests establish finite implementation behavior only.
