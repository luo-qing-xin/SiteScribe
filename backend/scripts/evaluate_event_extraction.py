"""Offline, synthetic-safe evaluation for the deterministic Event extractor."""

# ruff: noqa: E402, I001

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.event_schemas import SiteEventPayload
from app.site_event_extractor import MockEventExtractor


ROOT = Path(__file__).resolve().parents[2]


def fact_paths(payload: SiteEventPayload) -> list[str]:
    paths = [
        f"construction.{field}"
        for field in ("activity", "crew", "worker_count", "progress")
        if getattr(payload.construction, field) is not None
    ]
    for index, issue in enumerate(payload.issues):
        paths.extend((f"issues.{index}.description", f"issues.{index}.category"))
        if issue.responsible_person is not None:
            paths.append(f"issues.{index}.responsible_person")
    return paths


def issue_scores(predicted: list[str], expected: list[str]) -> tuple[float, float, float]:
    predicted_set = {value.strip() for value in predicted}
    expected_set = {value.strip() for value in expected}
    matches = len(predicted_set & expected_set)
    precision = matches / len(predicted_set) if predicted_set else float(not expected_set)
    recall = matches / len(expected_set) if expected_set else float(not predicted_set)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def evaluate_sample(path: Path) -> dict[str, Any]:
    sample = json.loads(path.read_text(encoding="utf-8"))
    if not sample.get("synthetic"):
        raise ValueError(f"{path}: sample must declare synthetic=true or be separately reviewed")
    transcript = sample["confirmed_transcript"]
    snapshot = {
        "confirmed_text": {
            "text": transcript,
            "source": "manual_description",
            "source_id": f"sample:{sample['id']}:confirmed",
        },
        "photo_ids": sample.get("photo_references", []),
        "location": sample["record_metadata"]["location"],
        "record_metadata": sample["record_metadata"],
    }
    predicted = MockEventExtractor().extract(snapshot, []).payload
    gold = SiteEventPayload.model_validate(sample["gold_event"])
    predicted_responsible = predicted.issues[0].responsible_person if predicted.issues else None
    gold_responsible = gold.issues[0].responsible_person if gold.issues else None
    precision, recall, f1 = issue_scores(
        [issue.description for issue in predicted.issues], sample["expected_issues"]
    )
    paths = fact_paths(predicted)
    evidenced = sum(bool(predicted.field_evidence.get(path)) for path in paths)
    coverage = evidenced / len(paths) if paths else 1.0
    return {
        "id": sample["id"],
        "synthetic": True,
        "activity_correct": predicted.construction.activity == gold.construction.activity,
        "crew_correct": predicted.construction.crew == gold.construction.crew,
        "worker_count_correct": predicted.construction.worker_count
        == gold.construction.worker_count,
        "progress_correct": predicted.construction.progress == gold.construction.progress,
        "responsible_person_correct": predicted_responsible == gold_responsible,
        "issue_precision": precision,
        "issue_recall": recall,
        "issue_f1": f1,
        "evidence_coverage": coverage,
        "no_evidence_field_ratio": 1 - coverage,
    }


def mean(results: list[dict[str, Any]], key: str) -> float:
    return sum(float(item[key]) for item in results) / len(results) if results else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--samples",
        type=Path,
        default=ROOT / "data" / "samples" / "event_extraction",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = [evaluate_sample(path) for path in sorted(args.samples.glob("*.json"))]
    if not results:
        raise SystemExit("No evaluation samples found")
    keys = [
        "activity_correct",
        "crew_correct",
        "worker_count_correct",
        "progress_correct",
        "responsible_person_correct",
        "issue_precision",
        "issue_recall",
        "issue_f1",
        "evidence_coverage",
        "no_evidence_field_ratio",
    ]
    report = {
        "dataset_kind": "synthetic",
        "sample_count": len(results),
        "metrics": {key: round(mean(results, key), 4) for key in keys},
        "samples": results,
        "disclaimer": "Synthetic fixture metrics are regression checks, not production accuracy claims.",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"JSON report: {args.output}")
    else:
        print(rendered)
    print(
        "Summary: "
        f"samples={len(results)} issue_f1={report['metrics']['issue_f1']:.4f} "
        f"evidence_coverage={report['metrics']['evidence_coverage']:.4f}"
    )


if __name__ == "__main__":
    main()
