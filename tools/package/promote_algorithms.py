"""Extract the selected, unchanged prediction functions from frozen experiments.

Build-time migration tool only. The installed product never imports experiments.
The dependency closure excludes evaluation, CLI entrypoints and cache readers.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "models/SoloShuttlePose/.runtime"
DEST = ROOT / "backend/app/algorithms"
SOURCES = {
    "player_paths": "c1-player-path-20261017/player_paths.py",
    "person_gate": "c1-region-smoothing-20261017/person_gate.py",
    "seeded_source": "c1-region-smoothing-20261017/seeded_source.py",
    "region_gate": "c1-region-smoothing-20261017/region_gate.py",
    "arc_features": "c1-spatial-support-20261017/arc_features.py",
    "shuttle_paths": "c1-player-path-20261017/shuttle_paths.py",
    "coherent_flights": "c1-player-path-20261017/coherent_flights.py",
    "check_short_events": "c1-player-path-20261017/check_short_events.py",
    "high_return": "c1-flight-identity-20261017/high_return.py",
    "connected_flight_filter": "c1-flight-identity-20261017/connected_flight_filter.py",
    "supported_start": "c1-flight-identity-20261017/supported_start.py",
    "attached_motion": "c1-flight-identity-20261017/attached_motion.py",
    "court_pipeline": "a1-c-parameters-20261017/replay.py",
    "players_v2": "d1-person-motion-20261017/players_v2.py",
    "body_features": "d1-person-motion-20261017/features.py",
    "trials": "d1-person-motion-20261017/trials.py",
    "pose_context": "d1-person-motion-20261017/pose_context.py",
    "pose_lk_motion_count": "d1-person-motion-20261017/pose_lk_motion_count.py",
    "buffer_actions": "d1-person-motion-20261017/buffer_actions.py",
    "selected_algorithm": "d1-person-motion-20261017/selected_algorithm.py",
    "refined_person": "d1-person-motion-20261017/d1-refined-person-20261018/refine.py",
}
ALIASES = {"players": "player_paths", "evaluate_full_context": "court_rules"}
SOURCES["court_rules"] = "c1-weak-tracks-20261017/evaluate_full_context.py"
OVERRIDES = {
    ("court_pipeline", "CONFIG"): json.loads((BASE / "c1-weak-tracks-20261017/full-C1-comparison/comparison.json").read_text())["results"][0]["variants"][0]["config"],
}


def main():
    parsed = {}
    for name, path in SOURCES.items():
        source = (BASE / path).read_text()
        tree = ast.parse(source)
        symbols = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                symbols[node.name] = node
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols[target.id] = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    symbols[alias.asname or alias.name.split(".")[0]] = node
        parsed[name] = source, symbols
    selected = {}

    def need(module, symbol):
        if symbol in selected.setdefault(module, {}):
            return
        if symbol in ("R", "ROOT", "B", "BASE", "SOURCE", "MAN", "CACHE", "W", "P", "F"):
            raise RuntimeError(f"Runtime repository dependency: {module}.{symbol}")
        source, symbols = parsed[module]
        node = symbols[symbol]
        selected[module][symbol] = node
        if (module, symbol) in OVERRIDES:
            selected[module][symbol] = f"{symbol} = {OVERRIDES[module, symbol]!r}"
            return
        if isinstance(node, ast.ImportFrom):
            dependency = ALIASES.get(node.module, node.module)
            if dependency in SOURCES:
                alias = next(a for a in node.names if (a.asname or a.name) == symbol)
                need(dependency, alias.name)
            return
        if isinstance(node, ast.Import):
            return
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id in symbols and child.id != symbol:
                need(module, child.id)

    for module, names in {
        "court_pipeline": ["pipeline"], "player_paths": ["descriptor", "appearance", "foot", "height", "tracks"],
        "shuttle_paths": ["observed_candidates", "associate"],
        "coherent_flights": ["split", "moving_points", "fit", "contact_points"],
        "players_v2": ["track_all", "select", "follow"], "body_features": ["body_motion"],
        "pose_context": ["extract"], "refined_person": ["predict"],
    }.items():
        for name in names:
            need(module, name)

    # The approved C selector replaces only main_players; both its initializer
    # and the same global used by tracks() resolve to this one implementation.
    selector = (BASE / "c2-current-algorithm-20261018/relaxed-selection/selector.py").read_text()
    definition = next(n for n in ast.parse(selector).body if isinstance(n, ast.FunctionDef))
    selected["player_paths"]["main_players"] = ast.get_source_segment(selector, definition)
    need("player_paths", "cv2")
    need("player_paths", "np")
    selected["player_paths"]["COURT"] = "COURT = np.array([[700,400],[1380,400],[1920,1080],[0,1080]], np.float32)"
    selected.pop("person_gate", None)

    DEST.mkdir(exist_ok=True)
    (DEST / "__init__.py").write_text('"""Frozen first-product prediction functions; provenance in provenance.json."""\n')
    provenance = {}
    for module, symbols in selected.items():
        source, _ = parsed[module]
        imports, definitions, seen = [], [], set()
        for symbol, node in symbols.items():
            if isinstance(node, str):
                definitions.append(node)
            elif isinstance(node, ast.ImportFrom):
                alias = next(a for a in node.names if (a.asname or a.name) == symbol)
                dependency = ALIASES.get(node.module, node.module)
                target = f".{dependency}" if dependency in SOURCES else node.module
                imports.append(f"from {target} import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""))
            elif isinstance(node, ast.Import):
                alias = next(a for a in node.names if (a.asname or a.name.split('.')[0]) == symbol)
                imports.append(f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""))
            elif id(node) not in seen:
                seen.add(id(node))
                definitions.append(ast.get_source_segment(source, node))
        result = '"""Selected prediction code, preserved from the recorded experiment."""\nfrom __future__ import annotations\n'
        result += "\n".join(sorted(set(imports))) + "\n\n" + "\n\n".join(reversed(definitions)) + "\n"
        (DEST / f"{module}.py").write_text(result)
        provenance[module] = dict(source=str((BASE / SOURCES[module]).relative_to(ROOT)),
                                  source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                                  symbols=sorted(symbols))
    # Replace the discarded legacy selector import with the approved function.
    path = DEST / "player_paths.py"
    text = path.read_text().replace("from .person_gate import main_players\n", "")
    path.write_text(text)
    (DEST / "person_gate.py").unlink(missing_ok=True)
    selector_path = BASE / "c2-current-algorithm-20261018/relaxed-selection/selector.py"
    provenance["player_paths"]["main_players_override"] = dict(
        source=str(selector_path.relative_to(ROOT)), source_sha256=hashlib.sha256(selector.encode()).hexdigest())
    model_path = ROOT / "models/SoloShuttlePose/src/models/TrackNet.py"
    provenance["tracknet_model"] = dict(source=str(model_path.relative_to(ROOT)),
                                        source_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
                                        symbols=[n.name for n in ast.parse(model_path.read_text()).body if isinstance(n, ast.ClassDef)])
    (DEST / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"Promoted {len(selected)} modules; no evaluation or CLI functions included.")


if __name__ == "__main__":
    main()
