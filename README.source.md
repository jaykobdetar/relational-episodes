# Relational episodes (G3)

A standard-library Python generator for two separate experiment lanes:

- **L3 structural replay:** immutable typed relation facts, atomic queries, two-edge joins, eight acquisition batches, and paired clustered/bridge-heavy graphs with exactly matched directed degree and lexical counts.
- **L5 episodic memory:** 32 immutable episode bundles, explicit local alias bindings, atomic/all-event/two-episode questions, and byte-exact source reconstruction using a visible cue.

These are mechanically generated source systems. Neither implementation nor data uses a model API, model output, teacher, distillation target, embedding, logits, judgment, paraphrase, training run, GPU, or paid resource. The production edge enumerator and the independent SQLite join oracle compute every answer and supporting witness.

The generator implements a bounded **phase-one L5 pilot**, with five one-factor cells rather than a complete factorial. Full L5 claims remain blocked on answer-entropy matching, pretrained-tokenizer auditing, appropriate competence gates, and the requested confirmatory sample sizes. No model performance claim follows from the generator checks.

## Run locally

Python 3.10+ and its standard `sqlite3` module are sufficient. Run from this directory; installation is optional.

```bash
python -m relational_episodes headroom
python scripts/run_tests.py
python -m relational_episodes generate --config configs/smoke.json --out data/smoke
python -m relational_episodes validate data/smoke --report reports/release_validation_01.json
```

The CLI and test runner cap address space at 256 MiB. This delivery ran them through scripts/guarded_run.py, which pins its own process and child to one CPU core, monitors their combined RSS, and stops its own child if host memory drops below 2 GiB, swap-out/used-swap pressure grows, or combined RSS exceeds 256 MiB. It never controls unrelated processes. Generation and validation require at least 3 GiB host MemAvailable and no observed swap-out or used-swap growth during two samples 250 ms apart. In this shared-host session, the parent also allocates a serialized slot. A refused capacity check is a pause, not a failed semantic test. The code does not stop other processes or change host settings. It uses one Python process and no worker pool.

Output directories and validation reports must be new; earlier evidence is never overwritten. `configs/protocol_capacity.json` documents the planned sample counts but is **not run** in this delivery. Its output will exceed the small-release budget, so a separately budgeted/sharded future run is required.

`solve` accepts an object containing `world` and `query`, checks the two evaluators, and prints the target and all witnesses. `score` accepts `prediction` and `target`; entity/event predictions are JSON arrays, and exact-source predictions are strings.

```bash
python -m relational_episodes solve examples/problem.json
python -m relational_episodes score examples/scoring.json
```

## Data access boundaries

The release contains four separate streams:

| File | Intended access |
|---|---|
| `sources.jsonl` | Original source records, acquisition batches, and charged storage keys. Subset to actually acquired and retained records before replay selection. |
| `questions.jsonl` | Bookkeeping plus the model-input allowlist: `question`, `answer_format`. No target, proof, seed or hidden episode ID enters the model question. |
| `interface_supervision.jsonl` | Exact labels **only** for disjoint `interface_train` worlds. Join with that world's source records to teach the interface. |
| `records.jsonl` | Full formal worlds, evaluator targets and proofs, counterfactual links, and audit metadata. Never hand this file to a replay selector or target-world adapter. |

`render.retained_selector_view` intersects caller-supplied retained keys with acquired batches and returns only original source rows. It does not inspect test questions, reconstruct unretained edges, implement a replay algorithm, or synthesize join training targets. A later experiment adding join supervision must identify it as a separate factorial intervention.

The data format cannot enforce memory accounting in downstream code. The manifest reports raw source bytes and serialized export bytes; any stored keys, indices, timestamps, replay loss values, extra source copies, adapters, optimizer state and checkpoints still count under the protocol. Dataset duplication between evaluator and model files is a packaging cost, not a free deployed-memory allowance.

## Formal semantics

See [SEMANTICS.md](docs/SEMANTICS.md) and [record schema](schemas/record-v1.schema.json). Runtime validation adds reference, type, occurrence, renderer, oracle and lineage checks that JSON Schema cannot express.

Atomic and join answers are **sets of public entity names**, including the empty set. Multiple paths to an endpoint do not duplicate the answer, but every edge/binding witness is retained in evaluation traces. All-matching answers are sets of public `{cue, occurrence, subject, relation, object}` event values. Repeated identical facts keep different visible ordinals. There is no closed-world claim beyond evaluating this finite immutable source system, and no probability label.

An alias binds only inside the episode where it is declared. A question with a visible cue restricts the first fact to that episode. Without a cue, it ranges over every local occurrence. A primary cross-episode join names both public cues and restricts each fact to its respective bundle. Its complete answer set fits the two-source budget. This tests scoped composition and cue-to-memory routing, not discovery of the second source. Acquisition order records what was shown, not a temporal state-update rule.

Exact reconstruction is UTF-8 byte equality, including final newlines and Unicode distinctions. A source question must supply a unique public cue. Hidden IDs and seeds cannot resolve ambiguity.

## Splits and scientific use

A unit of assignment is a whole graph or episode-set family, including all matched variants. Source names and relation names are randomized independently of labels. A conservative, name/order-invariant incidence-graph fingerprint prevents cross-family duplicates modulo renaming; color-refinement collisions can reject distinct graphs, so it is not advertised as a general exact graph-isomorphism solver. Rejection is explicit, without hidden reseeding or label-based cell deletion.

- `interface_train`: separate worlds with exact interface labels.
- `development`: separate families for choosing an experiment configuration.
- `id_test`: untouched in-distribution families; smoke only, not 40-graph confirmation.
- `ood_names`: held-out entity/relation/alias/cue/symbol dictionaries.
- `ood_template`: held-out reverse-direction source grammar, with the same query interface.
- `ood_topology`: **L3 only**, cluster width 16 instead of 8 at fixed 64 entities, 256 facts, four relations and eight batches. Degree distributions remain controlled.

The smoke contains one family per supported mode/split; it does not meet L3's five-development/40-confirmation requirement or L5's 12-development/40-confirmation requirement. Evaluation paths and prerequisite edges are recorded for the evaluator only. Use graph/set-level paired analysis; sentences, aliases and witnesses are not independent replications.

For L3, stop or redesign if initial join competence is below 70% while atom accuracy exceeds 95%. For L5, separately measure routing, exact reconstruction given routing, and unconditional single-/multi-episode answers per counted byte. This package supplies inputs and exact evaluation targets; it does not establish those empirical gates.

## Evidence and delivery status

[DATASET_CARD.md](DATASET_CARD.md) describes cells, metrics and limitations. [reports/VALIDATION.md](reports/VALIDATION.md) records actual execution outcomes, resource pauses, failures and repairs. The delivered smoke has 37 records / 11 families, 857 questions and 919 witnesses/certificates. All 28 tests and the complete independent oracle checks passed, and regeneration is byte-identical. The four exported streams total 4,784,001 bytes. The parent will arrange independent cross-review before Library packaging; none is claimed here.

Pinned experiment specs are in `inputs/`; `semantic_conventions_v1.2.json` is authoritative. Its SHA-256 is `ce59d56544010c31acc676d31539074263addbb954ebfc226d40ec8d93b76dcb`. The semantic history explicitly identifies the architect's initial-history snapshot as reconstructed, not contemporaneous. Our earlier local v1 copy is retained as read at the time and superseded by v1.2.

The retained data/smoke_initial snapshot predates final validator hardening; data/smoke is the final release and data/reproduced its byte-identical regeneration. The initial four data streams match the final streams; manifest provenance fields and validator code changed. Failed/paused receipts and the false-positive canonical collision are retained in reports. The optional scripts/final_checks.py used an already-installed generic JSON Schema validator; it is not a runtime dependency of the generator.
