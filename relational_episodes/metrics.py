"""Evaluation-only source and response-distribution measurements."""
from collections import Counter, defaultdict
import math
from .core import dumps


def answer_entropies(queries, targets):
    by_kind = defaultdict(Counter)
    for q in queries:
        # Exact categorical answer sets/strings. This is empirical bank entropy,
        # not a balanced latent task distribution or a probability training label.
        by_kind[q["kind"]][dumps(targets[q["id"]])] += 1
    result = {}
    for kind, counts in sorted(by_kind.items()):
        n = sum(counts.values())
        result[kind] = {"queries":n,"distinct_answer_values":len(counts),"empirical_answer_entropy_bits":-sum((c/n)*math.log2(c/n) for c in counts.values())}
    return result
