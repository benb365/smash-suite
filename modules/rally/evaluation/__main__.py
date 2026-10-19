"""Evaluate saved rally predictions against reviewed annotations."""
import argparse
import json
from pathlib import Path
from modules.rally.types import RallyInterval
from .rally_eval import evaluate_rallies, load_rally_annotations, load_rally_exclusions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True, help="result.json containing predictions")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.predictions.read_text())
    report = evaluate_rallies([RallyInterval(**p) for p in data["predictions"]],
        load_rally_annotations(args.annotations), excluded_events=load_rally_exclusions(args.annotations))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")


if __name__ == "__main__":
    main()
