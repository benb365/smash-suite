from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PREDICTOR = ROOT / "modules/models/tracknet/predictor.py"
SIZE_HELPER = ROOT / "docs/ai/opt08a-size/run.py"
SIZES = ("color9", "gray9", "gray3")
FOLD_HELPER = '''
def _opt08c_fold_first_layer(model):
    import torch
    conv = model.conv2d_1.conv
    assert conv.in_channels == 9
    assert conv.weight.shape == (64, 9, 3, 3)
    assert conv.groups == 1
    requires_grad = conv.weight.requires_grad
    weight = conv.weight.detach()
    folded = weight.reshape(64, 3, 3, 3, 3).sum(dim=2)
    conv.weight = torch.nn.Parameter(folded, requires_grad=requires_grad)
    conv.in_channels = 3

'''
LOAD_BLOCK = '''        self.model.load_state_dict(torch.load(weight, map_location="cpu", weights_only=True))
        self.model.eval().to(device)'''
FOLD_CALL = '''        self.model.load_state_dict(torch.load(weight, map_location="cpu", weights_only=True))
        _opt08c_fold_first_layer(self.model)
        self.model.eval().to(device)'''


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise AssertionError(f"expected one derivation point, found {count}: {old!r}")
    return source.replace(old, new)


def derive_predictor_source(source: str, variant: str, size_helper=None) -> str:
    if variant not in SIZES:
        raise ValueError(f"unsupported variant: {variant}")
    helper = size_helper or load_helper("_opt08a_size_helper")
    derived = helper.derive_source(source, "288x512")
    rgb = "rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)"
    if variant == "gray9":
        return replace_once(
            derived, rgb,
            "gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)\n"
            "                rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)",
        )
    if variant == "gray3":
        old = (
            "rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)\n"
            "                tensor = self.torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255)"
        )
        new = (
            "gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)\n"
            "                tensor = self.torch.from_numpy(gray).unsqueeze(0).float().div_(255)"
        )
        derived = replace_once(derived, old, new)
        derived = replace_once(derived, LOAD_BLOCK, FOLD_CALL)
        return derived + "\n" + FOLD_HELPER
    return derived


def load_helper(name: str):
    spec = importlib.util.spec_from_file_location(name, SIZE_HELPER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=SIZES, required=True)
    parser.add_argument("--case", choices=("A-short",), default="A-short")
    parser.add_argument("--inputs", type=Path, default=ROOT / "apps/video-clipper/reports/performance-first-round/inputs.json")
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output directory already exists: {args.output}")

    source = PREDICTOR.read_text(encoding="utf-8")
    size_helper = load_helper("_opt08a_size_source_helper")
    derived = derive_predictor_source(source, args.variant, size_helper)
    helper = load_helper("_opt08a_size_runner")
    helper.derive_source = lambda original, size: derive_predictor_source(original, args.variant, size_helper)
    original_argv = sys.argv
    error = None
    try:
        sys.argv = [str(SIZE_HELPER), "--size", "288x512", "--case", args.case,
                    "--inputs", str(args.inputs), "--models", str(args.models),
                    "--output", str(args.output)]
        try:
            helper.main()
        except Exception as exc:
            error = exc
        finally:
            sys.argv = original_argv

        if args.output.is_dir() and (args.output / "run.json").exists():
            module = sys.modules.get("modules.models.tracknet._opt07a_reference")
            run_path = args.output / "run.json"
            run = json.loads(run_path.read_text(encoding="utf-8"))
            derived_path = args.output / "derived_predictor.py"
            derived_path.write_text(derived, encoding="utf-8")
            run.update({
                "variant": args.variant,
                "input_channels": 3 if args.variant == "gray3" else 9,
                "actual_predictor_class": (
                    f"{module.TrackNetPredictor.__module__}.{module.TrackNetPredictor.__qualname__}"
                    if module else None
                ),
                "source_predictor_sha256": sha256(PREDICTOR),
                "derived_predictor_path": str(derived_path),
                "derived_predictor_sha256": sha256(derived_path),
                "opt08c_runner_sha256": sha256(Path(__file__)),
                "helper_runner_sha256": run.get("runner_sha256"),
                "helper_reported_variant": run.get("helper_reported_variant"),
                "helper_reported_size": run.get("input_size"),
                "helper_layer": "OPT-08A full recognition runner; internal size_candidate label means the 288x512 size wrapper was used.",
                "model_observations": getattr(module, "OPT08A_OBSERVATIONS", None) if module else None,
            })
            run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        if error is not None:
            raise error


if __name__ == "__main__":
    main()
