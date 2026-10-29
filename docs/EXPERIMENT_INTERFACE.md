# Experiment adapter boundary

This package does not implement replay training or sparse memories. A downstream experiment can consume it without passing evaluation labels into adaptation:

1. Assign a complete family to its existing split. Never mix its motif/alias variants across conditions outside the paired design, and never resplit question rows.
2. Teach query syntax on `interface_train` graphs/sets, using their source rows and exact interface targets. The target worlds have different fingerprints.
3. For an adaptation world, load only its `sources.jsonl` row. Expose batches sequentially. In L3, batches partition immutable facts; an edge never overwrites another edge. In L5, batches introduce whole bundles; aliases remain local.
4. Give replay selection only the retained/acquired subset returned by `retained_selector_view`. The function receives no record with queries, target sets or proof paths. Do not place the full generator/world object inside selector state.
5. Count the exact serialized retained source rows plus whatever indexing, IDs or selection state the implementation stores. The manifest's byte counts are lower-level accounting primitives, not a fixed total memory budget.
6. At evaluation, give the model only each question's `model_input` and the method's explicitly allowed retrieved/retained context. Predictions are evaluated with `scoring.score`. Keep targets and proof prerequisites in a separate evaluator process or object boundary.

For L3, the unconditional exact join-set score is primary. The evaluator may use the complete proof paths to report cross-batch prerequisites, bridge edges and performance conditioned on correct atom recall. That descriptive stratification must not drive selection or alter the primary test bank. The generator never exposes the test paths through the source-only export. Explicit join examples synthesized from retained edges would be a separately declared intervention and are not supplied here.

For L5, primary joins explicitly name two distinct legitimate public `first_cue` and `second_cue` values. The first and second facts are constrained to those respective bundles. All witnesses and the complete answer set are checked to remain inside this pair; the retrieval budget is two episodes. This tests scoped two-source composition and cue-to-memory routing, not autonomous discovery of a second episode. The generator chooses the second cue from the other bundle containing the first fact's intermediate entity, using source bindings before evaluating targets.

All-matching-event queries have their own explicitly declared equal budget of two episodes in this pilot: each queried alias occurs in exactly two bundles. This is a property checked for this corpus, not a general two-source assumption about all-event questions. Reconstruction and scoped atoms get one; unscoped atoms get two. Audit metadata reports exact minimum positive-answer episode cover and all supporting episode count per question. Never pool these task kinds as one accuracy endpoint.

The low-level engine also accepts uncued-second joins as a separate diagnostic. Its `episode_support` report computes the exact minimum union of source episodes needed to witness every positive endpoint, not an arbitrary single proof path. It reports whether a two-episode cap is feasible. Empty-answer positive support is zero, which does not certify absence without reading the declared scopes. A diagnostic needing more sources than its cap cannot be counted as a memory/storage/routing failure.

Compression notes are part of original source bytes and must be reconstructed. They are not instructions, summaries or labels. The compressibility cell shuffles this fixed source-symbol multiset; no hidden seed may be handed to a method as a compression code. Target-world exact source text may be retained only by explicitly budgeted source storage or replay; reconstructed text is inference-only and never a new training target.

The five-cell L5 pilot measures one-factor mechanical changes. Matching cardinality entropy or routing ambiguity by selecting examples after seeing labels would bias the intended bank. No such selection is performed. A future balanced design should be separately versioned and frozen before independent confirmation.
