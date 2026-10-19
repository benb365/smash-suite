"""Available rally scenarios and their model dependencies."""
SCENARIOS = ("high", "courtside", "personal")

def required_models(scene):
    if scene not in SCENARIOS:
        raise ValueError(f"Unknown rally scene: {scene}")
    names = ["ball_track.pt"]
    if scene != "high":
        names.append("yolo11n.pt")
    if scene == "personal":
        names.append("pose_kpRCNN.pth")
    return names
