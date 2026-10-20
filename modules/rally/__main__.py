"""Run a selected rally scenario on a local video; export remains a product choice."""
import argparse
import json
from pathlib import Path
from modules.media.video import probe
from modules.models.assets import ensure_models
from .scenarios import SCENARIOS, required_models
from .recognize import recognize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--scene", choices=SCENARIOS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--court", help="Four normalized [x,y] corners as JSON")
    args = parser.parse_args()
    court = json.loads(args.court) if args.court else None
    if court is not None and (len(court)!=4 or any(len(p)!=2 or any(not 0<=v<=1 for v in p) for p in court)):
        parser.error("court must contain four normalized [x,y] corners")
    args.output.mkdir(parents=True, exist_ok=True)
    info = probe(args.video, args.video.name)
    weights = ensure_models(required_models(args.scene))
    predictions, details = recognize(args.video, info, args.scene, weights,
        lambda stage, fraction: print(f"{fraction:.0%} {stage}", flush=True), args.output, court=court)
    (args.output/"result.json").write_text(json.dumps(dict(predictions=predictions, **details), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
