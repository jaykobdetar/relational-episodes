# Relational episodes dataset generator

A standard-library generator for graph-relation and episodic-memory experiments.

## What is preserved

Contains relational queries, episodic alias binding, independent oracle/validation logic and scoring utilities.

This is a private, source-only preservation snapshot of the user-selected local project **P0254**, prepared on 2026-10-29. The user described these projects as arising from AI-assisted work. This note records archival provenance, not a claim about authorship or scientific validity. The original Git history was not imported.

## Setup and dependencies

Python 3.10+; runtime dependencies are standard-library according to pyproject.toml.

## Entry points

Inspect python3 -m relational_episodes --help. configs/, schemas/, docs/ and source tests describe the supported lanes.

## Status and limitations

Pinned input specifications, generated datasets and historical reports remain local. A test references reports/canonical_collision_01.json, which is not included. Do not treat this source snapshot as a complete reproduction bundle; restore required evidence before attempting those checks.

No project code, installation steps or tests were executed during preservation. Existing README/source claims have not been independently revalidated. For the original project documentation, see [README.source.md](README.source.md).

## Backup scope

Only the reviewed text source, tests, selected manifests/configurations and technical documentation are included. Credentials, .env/auth configuration, raw conversations, personal documents, live state, model weights, dependencies, generated datasets and bulky outputs were excluded. Local originals remain in place until separately approved and safe to remove. A successful source backup alone is not proof that all runtime data or experiment evidence has been preserved.
