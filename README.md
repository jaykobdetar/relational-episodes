# Relational episodes

A standard-library Python toolkit for generating finite graph-relation and episodic-memory tasks with exact answers and supporting witnesses. This is an experimental source release, not a validated learning benchmark or a reproduction of the original research delivery.

- Structural lane: immutable typed facts, atomic queries, two-edge joins, acquisition batches, and matched graph pairs.
- Episodic lane: scoped aliases, visible episode cues, event-set queries, two-episode joins, and exact UTF-8 reconstruction.
- Direct evaluation cross-checked against a separate SQLite join evaluator; set scoring, source/question exports, and deterministic generation.

## Setup and quick start

Python 3.10+ on **Linux**, with the standard `sqlite3` module. Linux is required by the resource guards (`/proc`, process affinity, and address-space limits). No runtime packages, model downloads, GPU, network services, or API keys are needed.

From a checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/relational-episodes --help
.venv/bin/relational-episodes solve examples/problem.json
.venv/bin/relational-episodes score examples/scoring.json
```

Installing may download setuptools from PyPI for the isolated build. The library also runs directly from the checkout without installation. Configs, examples, docs and helper scripts live in the source checkout; the wheel includes the runtime schema.

Run the bounded tests from the checkout:

```bash
python3 scripts/guarded_run.py --prefix reports/tests -- python3 scripts/run_tests.py
```

Tests create numbered reports. One historical collision regression is explicitly skipped because its original fixture is absent; fresh generated-world renaming coverage runs independently. Do not interpret a successful run with that skip as verification of the historical collision.

Optional smoke generation (small synthetic data, not a training run):

```bash
python3 -m relational_episodes headroom
python3 -m relational_episodes generate --config configs/smoke.json --out data/smoke
mkdir -p reports
python3 -m relational_episodes validate data/smoke --report reports/smoke-validation.json
python3 scripts/reproduce.py data/smoke data/reproduced reports/reproduction.json
```

Use new output paths for repeat runs: existing outputs are refused. Generation and validation require at least 3 GiB available host memory and no observed growth in swap pressure; Python address space is capped at 256 MiB. The optional supervisor adds one-core affinity and monitors its own child. A resource refusal means defer the run. `configs/protocol_capacity.json` is a planning configuration, not a supported small smoke run.

Optional independent JSON Schema validation requires installing `jsonschema` in your virtual environment, then running `.venv/bin/python scripts/final_checks.py data/smoke --report reports/schema.json`. It checks only newly supplied data and does not recreate historical receipts or change examples.

## Format and limitations

See [semantics](docs/SEMANTICS.md), [experiment interface](docs/EXPERIMENT_INTERFACE.md), [validation scope](docs/VALIDATION_SCOPE.md), and [record schema](relational_episodes/schemas/record-v1.schema.json).

`sources.jsonl` carries source records; `questions.jsonl` exposes only the question/answer-format allowlist; `interface_supervision.jsonl` labels disjoint interface-training worlds. `records.jsonl` contains evaluator-only targets and proofs and must not be exposed to a target-world learner or replay selector.

The L5 generator implements five one-factor pilot cells, not a complete factorial. Answer-entropy matching, tokenizer audits, competence gates, and confirmatory sample sizes remain outstanding. The fingerprint is a conservative isomorphism guard and can reject distinct worlds. Downstream memory accounting and correct data isolation remain the experimenter's responsibility. No model-performance or memory-retention claim follows from these checks.

## Provenance and release status

The repository began with a single source-preservation commit for the user-selected P0254 project on 2026-10-29. The user described the work as AI-assisted. Original development history was not imported; authorship and scientific evidence cannot be established by this snapshot alone.

The pinned `inputs/` specifications, historical datasets, dataset card, validation reports, and `reports/canonical_collision_01.json` were not included. They have not been invented or recovered. The semantic-contract identifier in configs is a historical identifier, not proof of conformance to an available specification. Fresh manifests explicitly mark missing pinned specifications. [README.source.md](README.source.md) preserves historical documentation with this qualification.

No license has been granted in this repository. The owner must confirm provenance, third-party rights and a license before an open-source release. Keep the repository private pending the [release checklist](docs/RELEASE_READINESS.md).
