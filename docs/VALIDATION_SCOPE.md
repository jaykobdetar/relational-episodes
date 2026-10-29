# Validation coverage and exclusions

The numbered execution reports, not this plan, determine which checks actually ran.

| Check | Exact covered domain | Exclusions |
|---|---|---|
| Structural exhaustive oracle | 2 entities, 2 relation types, every one of 256 edge subsets; 4 atomic + 8 join questions per graph; complete witnesses | Not exhaustive over 64-node worlds or heterogeneous type systems |
| Episodic exhaustive oracle | 2 entities, 2 episodes, 1 relation; every 256 edge subset, 4 alias assignments, 6 scoped/unscoped atomic/event + 3 distinct-episode join questions (uncued and both cue orders) | Not exhaustive over arbitrary alias multiplicity, 32 episodes, or source grammar |
| Hand semantic cases | Repeated occurrences, local alias scope, ambiguous aliases, many witnesses to one answer, cross-episode restriction, heterogeneous relation type rejection, UTF-8 bytes | Hand cases are independent assertions, not corpus balancing |
| Malformed cases | bool/float/int distinction, dangling references, duplicate keys/IDs/ordinals, unknown fields, invalid Unicode, query arity/scope, tampered targets/proofs | Not a parser-fuzzer or unbounded adversarial stress claim |
| Canonicalization | Arbitrary renaming and row reversal on hand worlds; grouped release fingerprints | Color refinement can collide for nonisomorphic graphs; collision rejection is conservative |
| Split/access controls | Counterfactual family integrity; source/question allowlists; no test labels in interface supervision; acquired/retained intersection | Cannot prevent a downstream experiment from improperly loading evaluator files |
| Generation | Both exact evaluators on every emitted target and all supporting witnesses; degree/lexical/byte counts; source rerender | Runtime self-checks share the validator and parser; cross-review remains necessary |
| Reproducibility | Same explicit config yields byte-identical files/manifest in the same Python environment | Cross-Python/SQLite-version reproducibility is not yet certified |
| Shortcut audit | Always-empty heuristic, observed set cardinalities, matched bags of words with changed L3 join answers | Does not rule out every lexical, ordinal, grammar or positional shortcut |

No probabilities are generated. Zero-probability tests are not applicable; zero-answer relational cases are extensively included. Scoring accepts all set orderings; complete witnesses remain available without making an arbitrary single-witness target. Repeated source events have public occurrence identity.

Before reporting generalization or memory conclusions, a downstream study must satisfy its competence gates, use independent world/set replication, budget every index/source/metadata byte, complete the required tokenizer/balance work, and use sufficient development/confirmation seeds. A correct finite generator is evidence about labels, not about learning performance.
