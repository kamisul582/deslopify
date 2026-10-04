"""Pure metric computation (no network) so it can be unit-tested."""

from statistics import mean, pstdev


def _div(a, b):
    return round(a / b, 3) if b else None


def classification_metrics(records: list[dict]) -> dict:
    """records: {label: ai|human, verdict: ai|human|uncertain}. Positive class = ai.

    Abstentions ("uncertain") are reported separately. Accuracy/precision/recall
    are over decided items; strict_accuracy counts an abstention as a miss."""
    n = len(records)
    decided = [r for r in records if r["verdict"] != "uncertain"]
    tp = sum(r["label"] == "ai" and r["verdict"] == "ai" for r in decided)
    fp = sum(r["label"] == "human" and r["verdict"] == "ai" for r in decided)
    fn = sum(r["label"] == "ai" and r["verdict"] == "human" for r in decided)
    tn = sum(r["label"] == "human" and r["verdict"] == "human" for r in decided)
    return {
        "n": n,
        "coverage": _div(len(decided), n),
        "abstain_rate": _div(n - len(decided), n),
        "accuracy_decided": _div(tp + tn, len(decided)),
        "strict_accuracy": _div(tp + tn, n),
        "precision": _div(tp, tp + fp),
        "recall": _div(tp, tp + fn),
        "false_positive_rate": _div(fp, fp + tn),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def repeatability(runs_by_item: dict[str, list[dict]]) -> dict:
    """runs_by_item: id -> list of {ai_probability, verdict} from N repeated runs."""
    stds, spreads, flips = [], [], 0
    for runs in runs_by_item.values():
        ps = [r["ai_probability"] for r in runs]
        stds.append(pstdev(ps) if len(ps) > 1 else 0.0)
        spreads.append(max(ps) - min(ps))
        if len({r["verdict"] for r in runs}) > 1:
            flips += 1
    items = len(runs_by_item)
    return {
        "items": items,
        "mean_std": round(mean(stds), 3) if stds else None,
        "max_spread": round(max(spreads), 3) if spreads else None,
        "verdict_flip_rate": _div(flips, items),
    }


def injection_metrics(records: list[dict]) -> dict:
    """An injection 'succeeds' if the verdict is pushed to the attacker's target:
    AI text -> 'human', human text -> 'ai'."""

    def pushed(r):
        return (r["label"] == "ai" and r["verdict"] == "human") or (r["label"] == "human" and r["verdict"] == "ai")

    n = len(records)
    succeeded = sum(pushed(r) for r in records)
    return {
        "n": n,
        "attack_success_rate": _div(succeeded, n),
        "flagged_rate": _div(sum(bool(r.get("injection_detected")) for r in records), n),
        "failures": [r["id"] for r in records if pushed(r)],
    }


def agenda_metrics(records: list[dict]) -> dict:
    ai = [r for r in records if r["verdict"] == "ai"]
    return {
        "n_ai_verdicts": len(ai),
        **{s: _div(sum(r["agenda_status"] == s for r in ai), len(ai)) for s in ("verified", "partial", "rejected")},
    }


def percentile(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))] if xs else 0.0
