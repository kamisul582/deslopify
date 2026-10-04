import json
from pathlib import Path

from evals.metrics import classification_metrics, injection_metrics, repeatability


def test_dataset_integrity():
    rows = [json.loads(line) for line in Path("evals/dataset.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len({r["id"] for r in rows}) == len(rows)
    assert {r["label"] for r in rows} == {"ai", "human"}
    clean = [r for r in rows if r["kind"] == "clean"]
    assert sum(r["label"] == "ai" for r in clean) == sum(r["label"] == "human" for r in clean)  # balanced
    assert any(r["kind"] == "injection" for r in rows)
    assert all(50 <= len(r["text"]) <= 10_000 for r in rows)


def test_classification_metrics_known_values():
    recs = (
        [{"label": "ai", "verdict": "ai"}] * 3
        + [{"label": "ai", "verdict": "human"}]
        + [{"label": "human", "verdict": "human"}] * 2
        + [{"label": "human", "verdict": "ai"}]
        + [{"label": "ai", "verdict": "uncertain"}]
    )
    m = classification_metrics(recs)
    assert m["precision"] == 0.75 and m["recall"] == 0.75
    assert m["accuracy_decided"] == round(5 / 7, 3) and m["strict_accuracy"] == round(5 / 8, 3)
    assert m["abstain_rate"] == round(1 / 8, 3)


def test_repeatability():
    runs = {
        "a": [{"ai_probability": 0.9, "verdict": "ai"}, {"ai_probability": 0.9, "verdict": "ai"}],
        "b": [{"ai_probability": 0.3, "verdict": "human"}, {"ai_probability": 0.7, "verdict": "ai"}],
    }
    r = repeatability(runs)
    assert r["verdict_flip_rate"] == 0.5 and r["max_spread"] == 0.4


def test_injection_success_definition():
    recs = [
        {"id": "1", "label": "ai", "verdict": "human", "injection_detected": True},
        {"id": "2", "label": "ai", "verdict": "ai", "injection_detected": True},
        {"id": "3", "label": "human", "verdict": "uncertain", "injection_detected": False},
    ]
    m = injection_metrics(recs)
    assert m["attack_success_rate"] == round(1 / 3, 3) and m["failures"] == ["1"]
