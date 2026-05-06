from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def model_to_dict(model: Any) -> Any:
    if isinstance(model, BaseModel):
        if hasattr(model, "model_dump"):
            return model.model_dump(mode="json")
        return json.loads(model.json())
    if isinstance(model, list):
        return [model_to_dict(item) for item in model]
    if isinstance(model, dict):
        return {key: model_to_dict(value) for key, value in model.items()}
    return model
