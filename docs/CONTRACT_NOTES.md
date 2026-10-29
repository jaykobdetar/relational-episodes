# G3 contract decisions and pending architect response

2026-10-02 initial implementation questions were sent to the coordinating parent before generating any examples or labels:

- Relation signatures: explicit subject/object types, with the bounded generated core using one `node` sort and four edge relation types.
- Event meaning: an immutable fact occurrence; no event times, revisions, overwrites, or temporal lookup.
- All-matching events: public cue/subject/relation/object tuples, retaining occurrences from distinct episodes.
- Alias resolution: a binding is local to its visible episode cue. Without a cue, evaluate every matching local occurrence. Alias ambiguity never selects an arbitrary witness.
- Reconstruction: a unique visible cue retrieves the exact source string, interpreted as UTF-8 bytes. Hidden IDs cannot be used as query cues.

Architect response received and pinned in inputs/semantic_conventions_v1.json before dataset generation. All-matches now includes the visible local occurrence ordinal; duplicate facts within one episode are legal and retain separate identity. The engine rejects reused ordinals within a scope. Original questions are retained above as development history.

Planned bounded controls: L3 paired rewiring preserves per-entity/per-relation directed degree and lexical counts. L5 overlap and alias interventions preserve global entity/alias token multiplicities by rearranging occurrences; density redistributes edges at fixed source length and total endpoint frequency. Compressibility reorders a fixed multiset of mechanically generated symbols. This is a measured compression control, not a claim of independent semantic entropy. Full answer-entropy matching and an external tokenizer audit remain separate protocol gates.

Resource gate from parent: do not generate datasets or run exhaustive tests below 3 GiB MemAvailable or while swap is actively growing. No changes to unrelated processes or system settings. Own Python processes limited to one CPU and 256 MiB address space.

Authoritative update: pinned semantic_conventions_v1.1.json, SHA-256 9b1a6718c446b9337187af8eea895bf5b3808b9d597a4cfdf2ab02110992d2ed. G3 semantics unchanged from the confirmed v1 response. Source semantic_contract_history.json retains the explicit reconstructed-history warning. The earlier v1 copy is preserved, not rewritten.
