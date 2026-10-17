#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.vision.soloshuttlepose_adapter import (  # noqa: E402
    build_needs_converter_report,
    convert_soloshuttlepose_artifacts,
    scan_artifacts,
)


DEFAULT_INPUT = REPO_ROOT / "datasets/badminton-v1/local/test001/test001.mp4"
DEFAULT_SOLO_REPO = REPO_ROOT / "models" / "SoloShuttlePose"
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "models/SoloShuttlePose/.runtime/soloshuttlepose/test001"
)
DEFAULT_MANUAL = REPO_ROOT / "datasets/badminton-v1/annotations/seed/test001/manual_scene"
DEFAULT_SOLO_PYTHON = DEFAULT_SOLO_REPO / ".venv" / "bin" / "python"
REQUIRED_WEIGHT_FILES = (
    "src/models/weights/court_kpRCNN.pth",
    "src/models/weights/net_kpRCNN.pth",
    "src/models/weights/pose_kpRCNN.pth",
    "src/models/weights/ball_track.pt",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a PC-only SoloShuttlePose spike against test001.mp4."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--solo-repo", type=Path, default=DEFAULT_SOLO_REPO)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manual-scene", type=Path, default=DEFAULT_MANUAL)
    parser.add_argument("--python", default=default_python_executable())
    parser.add_argument("--skip-run", action="store_true")
    parser.add_argument("--skip-weight-check", action="store_true")
    parser.add_argument("--force", action="store_true", default=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    input_dir = output_dir / "input"
    raw_result_dir = output_dir / "raw"
    log_dir = output_dir / "logs"
    manifest_path = output_dir / "artifact_manifest.json"
    report_path = output_dir / "spike_report.md"
    converted_path = output_dir / "test001_soloshuttlepose_scene_gate.json"
    eval_json_path = output_dir / "test001_soloshuttlepose_eval.json"
    eval_report_path = output_dir / "test001_soloshuttlepose_eval.md"

    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    checks = validate_environment(
        solo_repo=args.solo_repo,
        input_path=args.input,
        skip_weight_check=args.skip_weight_check,
    )
    if checks["status"] != "ready":
        manifest = build_manifest(
            status=checks["status"],
            args=args,
            raw_result_dir=raw_result_dir,
            checks=checks,
            artifacts=[],
        )
        write_json(manifest_path, manifest)
        report_path.write_text(build_spike_report(manifest), encoding="utf-8")
        print(f"SoloShuttlePose spike status: {checks['status']}")
        print(f"Artifact manifest: {manifest_path}")
        print(f"Spike report: {report_path}")
        return 0

    run_status = "skipped"
    return_code: Optional[int] = None
    log_evidence: dict[str, Any] = {}
    command = build_command(
        python_executable=args.python,
        solo_repo=args.solo_repo,
        input_dir=input_dir,
        raw_result_dir=raw_result_dir,
        force=args.force,
    )
    if not args.skip_run:
        if args.force and raw_result_dir.exists():
            shutil.rmtree(raw_result_dir)
        prepare_input(input_path=args.input, input_dir=input_dir)
        raw_result_dir.mkdir(parents=True, exist_ok=True)
        completed = run_soloshuttlepose(
            command=command,
            cwd=args.solo_repo,
            stdout_path=log_dir / "stdout.log",
            stderr_path=log_dir / "stderr.log",
        )
        return_code = completed.returncode
        run_status = "succeeded" if completed.returncode == 0 else "failed"
        log_evidence = analyze_soloshuttlepose_logs(
            stdout_path=log_dir / "stdout.log",
            stderr_path=log_dir / "stderr.log",
        )

    converted, adapter_manifest = convert_soloshuttlepose_artifacts(raw_result_dir, args.input)
    artifacts = scan_artifacts(raw_result_dir)
    status = adapter_manifest.get("parse_status", "unknown")
    if run_status == "failed":
        status = "run_failed"

    manifest = build_manifest(
        status=status,
        args=args,
        raw_result_dir=raw_result_dir,
        checks=checks,
        artifacts=artifacts,
        command=command,
        run_status=run_status,
        return_code=return_code,
        log_evidence=log_evidence,
        adapter_manifest=adapter_manifest,
    )
    write_json(manifest_path, manifest)

    if converted is not None and status != "run_failed":
        write_json(converted_path, converted)
        if args.manual_scene.exists():
            from evaluate_manual_scene import build_report, evaluate_scene_gate_file

            metrics = evaluate_scene_gate_file(args.manual_scene, converted_path)
            write_json(eval_json_path, metrics)
            eval_report_path.write_text(
                build_report(metrics, args.manual_scene, converted_path),
                encoding="utf-8",
            )
            manifest["evaluation"] = {
                "json": str(eval_json_path),
                "report": str(eval_report_path),
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "manual_hit_rate": metrics["manual_hit_rate"],
            }
            write_json(manifest_path, manifest)

    report_path.write_text(build_spike_report(manifest), encoding="utf-8")

    print(f"SoloShuttlePose spike status: {manifest['status']}")
    print(f"Artifact manifest: {manifest_path}")
    print(f"Spike report: {report_path}")
    if converted is not None:
        print(f"Converted SceneGate JSON: {converted_path}")
    if "evaluation" in manifest:
        evaluation = manifest["evaluation"]
        print(
            "Evaluation: "
            f"precision {evaluation['precision']:.2%}, recall {evaluation['recall']:.2%}, "
            f"F1 {evaluation['f1']:.2%}, manual hit rate {evaluation['manual_hit_rate']:.2%}"
        )
    return 0


def validate_environment(
    solo_repo: Path,
    input_path: Path,
    skip_weight_check: bool,
) -> dict[str, Any]:
    issues = []
    if not input_path.exists():
        issues.append(f"Input video does not exist: {input_path}")
    if not solo_repo.exists():
        issues.append(f"SoloShuttlePose repo not found: {solo_repo}")
    if not (solo_repo / "main.py").exists():
        issues.append(f"SoloShuttlePose main.py not found: {solo_repo / 'main.py'}")

    documented_model_dir = solo_repo / "src" / "model"
    runtime_weight_dir = solo_repo / "src" / "models" / "weights"
    required_weight_paths = [solo_repo / path for path in REQUIRED_WEIGHT_FILES]
    missing_weight_files: list[str] = []
    if not skip_weight_check:
        missing_weight_files = [
            str(path) for path in required_weight_paths if not path.is_file()
        ]
        if missing_weight_files:
            issues.append(
                "SoloShuttlePose runtime weights missing under "
                f"{runtime_weight_dir}: {', '.join(missing_weight_files)}"
            )
        documented_weights_present = documented_model_dir.exists() and any(
            item.is_file() for item in documented_model_dir.rglob("*")
        )
        if missing_weight_files and not documented_weights_present:
            issues.append(
                "SoloShuttlePose downloaded weight folder not found under documented "
                f"path: {documented_model_dir}"
            )

    return {
        "status": "ready" if not issues else "blocked",
        "issues": issues,
        "solo_repo": str(solo_repo),
        "input": str(input_path),
        "documented_weight_dir": str(documented_model_dir),
        "runtime_weight_dir": str(runtime_weight_dir),
        "required_weight_files": [str(path) for path in required_weight_paths],
        "missing_weight_files": missing_weight_files,
        "weight_check_skipped": skip_weight_check,
    }


def prepare_input(input_path: Path, input_dir: Path) -> None:
    input_dir.mkdir(parents=True, exist_ok=True)
    target = input_dir / input_path.name
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        target.symlink_to(input_path.resolve())
    except OSError:
        shutil.copy2(input_path, target)


def build_command(
    python_executable: str,
    solo_repo: Path,
    input_dir: Path,
    raw_result_dir: Path,
    force: bool,
) -> list[str]:
    command = [
        python_executable,
        str(solo_repo / "main.py"),
        "--folder_path",
        str(input_dir),
        "--result_path",
        str(raw_result_dir),
    ]
    if force:
        command.append("--force")
    return command


def analyze_soloshuttlepose_logs(stdout_path: Path, stderr_path: Path) -> dict[str, Any]:
    stdout_text = _read_log(stdout_path)
    stderr_text = _read_log(stderr_path)
    evidence: dict[str, Any] = {
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "stdout_size_bytes": stdout_path.stat().st_size if stdout_path.exists() else 0,
        "stderr_size_bytes": stderr_path.stat().st_size if stderr_path.exists() else 0,
    }

    preprocess_failure_count = stdout_text.count("Fail to pre-process")
    if preprocess_failure_count:
        evidence["upstream_preprocess_failed"] = True
        evidence["preprocess_failure_count"] = preprocess_failure_count

    court_last_frame = _last_logged_frame(
        stdout_text,
        r"current frame is (?P<frame>\d+) for court",
    )
    if court_last_frame is not None:
        evidence["court_last_frame"] = court_last_frame

    net_last_frame = _last_logged_frame(
        stdout_text,
        r"for net, current frame is (?P<frame>\d+)",
    )
    if net_last_frame is not None:
        evidence["net_last_frame"] = net_last_frame

    stderr_tail = _tail_non_empty_lines(stderr_text)
    if stderr_tail:
        evidence["stderr_tail"] = stderr_tail

    return evidence


def run_soloshuttlepose(
    command: list[str],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
    mpl_config_dir = Path(tempfile.gettempdir()) / "mpl-soloshuttlepose"
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    env.setdefault("MPLCONFIGDIR", str(mpl_config_dir))
    compat_dir = build_torch_compat_dir()
    env["PYTHONPATH"] = (
        f"{compat_dir}{os.pathsep}{env['PYTHONPATH']}"
        if env.get("PYTHONPATH")
        else str(compat_dir)
    )

    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
        "w",
        encoding="utf-8",
    ) as stderr_file:
        return subprocess.run(  # noqa: S603
            command,
            cwd=cwd,
            check=False,
            text=True,
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
        )


def build_manifest(
    status: str,
    args: argparse.Namespace,
    raw_result_dir: Path,
    checks: dict[str, Any],
    artifacts: list[dict[str, Any]],
    command: Optional[list[str]] = None,
    run_status: Optional[str] = None,
    return_code: Optional[int] = None,
    log_evidence: Optional[dict[str, Any]] = None,
    adapter_manifest: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    manifest = {
        "source": "SoloShuttlePose",
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "solo_repo": str(args.solo_repo),
        "raw_result_dir": str(raw_result_dir),
        "checks": checks,
        "command": command,
        "run_status": run_status,
        "return_code": return_code,
        "terminated_by_signal": (
            -return_code if return_code is not None and return_code < 0 else None
        ),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "adapter": adapter_manifest or {},
    }
    if log_evidence:
        manifest["run_evidence"] = log_evidence
    return manifest


def build_spike_report(manifest: dict[str, Any]) -> str:
    adapter = manifest.get("adapter") or {}
    evaluation = manifest.get("evaluation")
    run_evidence = manifest.get("run_evidence") or {}
    lines = [
        "# SoloShuttlePose test001 spike",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Input: `{manifest['input']}`",
        f"- SoloShuttlePose repo: `{manifest['solo_repo']}`",
        f"- Raw result dir: `{manifest['raw_result_dir']}`",
        f"- Run status: `{manifest.get('run_status')}`",
        f"- Return code: `{manifest.get('return_code')}`",
        f"- Artifact count: `{manifest.get('artifact_count', 0)}`",
        "",
        "## Environment Checks",
        "",
        *_format_list(manifest.get("checks", {}).get("issues", [])),
        "",
    ]
    if run_evidence:
        lines.extend(
            [
                "## Run Evidence",
                "",
                *_format_run_evidence(run_evidence, manifest.get("terminated_by_signal")),
                "",
            ]
        )
    lines.extend(
        [
            "## Adapter",
            "",
            (
                build_needs_converter_report(adapter).strip()
                if adapter
                else "- Adapter did not run."
            ),
        ]
    )
    if evaluation:
        lines.extend(
            [
                "",
                "## Evaluation",
                "",
                f"- Precision: `{evaluation['precision']:.2%}`",
                f"- Recall: `{evaluation['recall']:.2%}`",
                f"- F1: `{evaluation['f1']:.2%}`",
                f"- Manual hit rate: `{evaluation['manual_hit_rate']:.2%}`",
                f"- JSON: `{evaluation['json']}`",
                f"- Report: `{evaluation['report']}`",
            ]
        )
    if manifest["status"] in {"blocked", "needs_converter", "run_failed"}:
        lines.extend(
            [
                "",
                "## Next Step",
                "",
                next_step_for_status(manifest),
            ]
        )
    return "\n".join(lines) + "\n"


def next_step_for_status(manifest: dict[str, Any]) -> str:
    if manifest["status"] == "blocked":
        checks = manifest.get("checks", {})
        issues = checks.get("issues", [])
        if any("repo not found" in issue for issue in issues):
            return (
                "Clone SoloShuttlePose into `models/SoloShuttlePose`, place weights under "
                "`models/SoloShuttlePose/src/models/weights`, then rerun this script."
            )
        if checks.get("missing_weight_files"):
            return (
                "Download the upstream SoloShuttlePose weights, then ensure the runtime files "
                "`court_kpRCNN.pth`, `net_kpRCNN.pth`, `pose_kpRCNN.pth`, and "
                "`ball_track.pt` exist under `models/SoloShuttlePose/src/models/weights`. "
                "The upstream Quick Start mentions `src/model`, but the current source code "
                "loads from `src/models/weights`."
            )
        return (
            "Fix the blocked environment checks above, then rerun this script."
        )
    if manifest["status"] == "run_failed":
        run_evidence = manifest.get("run_evidence") or {}
        if run_evidence.get("upstream_preprocess_failed"):
            return (
                "SoloShuttlePose loaded the runtime weights, but upstream preprocessing failed "
                "on `test001.mp4` before producing rally clips. Avoid rerunning the full clip "
                "until a reference-frame/crop strategy or a different model baseline is chosen."
            )
        return "Inspect `logs/stdout.log` and `logs/stderr.log`, then rerun after fixing the environment."
    return "Inspect raw artifacts and add/adjust a converter for SoloShuttlePose's actual output format."


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _format_list(items: list[Any]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _format_run_evidence(
    evidence: dict[str, Any],
    terminated_by_signal: Optional[int],
) -> list[str]:
    lines = [
        f"- Stdout log: `{evidence.get('stdout_log')}`",
        f"- Stderr log: `{evidence.get('stderr_log')}`",
        f"- Stdout size: `{evidence.get('stdout_size_bytes', 0)} bytes`",
        f"- Stderr size: `{evidence.get('stderr_size_bytes', 0)} bytes`",
    ]
    if evidence.get("upstream_preprocess_failed"):
        lines.append(
            "- Upstream preprocess failures: "
            f"`{evidence.get('preprocess_failure_count', 0)}`"
        )
    if evidence.get("court_last_frame") is not None:
        lines.append(f"- Last court preprocess frame: `{evidence['court_last_frame']}`")
    if evidence.get("net_last_frame") is not None:
        lines.append(f"- Last net preprocess frame: `{evidence['net_last_frame']}`")
    if terminated_by_signal is not None:
        lines.append(f"- Terminated by signal: `{terminated_by_signal}`")
    if evidence.get("stderr_tail"):
        lines.append(f"- Stderr tail: `{'; '.join(evidence['stderr_tail'])}`")
    return lines


def _read_log(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _last_logged_frame(text: str, pattern: str) -> Optional[int]:
    last_frame: Optional[int] = None
    for match in re.finditer(pattern, text):
        last_frame = int(match.group("frame"))
    return last_frame


def _tail_non_empty_lines(text: str, limit: int = 8) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()][-limit:]


def build_torch_compat_dir() -> Path:
    compat_dir = Path(tempfile.gettempdir()) / "soloshuttlepose-compat"
    compat_dir.mkdir(parents=True, exist_ok=True)
    (compat_dir / "sitecustomize.py").write_text(
        "\n".join(
            [
                "import torch",
                "",
                "_original_torch_load = torch.load",
                "",
                "def _smash_suite_torch_load(*args, **kwargs):",
                "    kwargs.setdefault('map_location', 'cpu')",
                "    kwargs.setdefault('weights_only', False)",
                "    return _original_torch_load(*args, **kwargs)",
                "",
                "torch.load = _smash_suite_torch_load",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return compat_dir


def default_python_executable() -> str:
    if os.environ.get("SOLOSHUTTLEPOSE_PYTHON"):
        return os.environ["SOLOSHUTTLEPOSE_PYTHON"]
    if DEFAULT_SOLO_PYTHON.exists():
        return str(DEFAULT_SOLO_PYTHON)
    return sys.executable


if __name__ == "__main__":
    raise SystemExit(main())
