"""Model Registry API: inspect local model artifacts and activate a version."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from api.common import ROOT, connect

sys.path.insert(0, str(ROOT / "src"))
from fall.features import FEATURE_COLUMNS  # noqa: E402

app = FastAPI(title="FallAllD Model Registry API", version="1.0.0")


class RegisterModel(BaseModel):
    version: str = Field(min_length=1, max_length=80)
    file: str = "models/fall_rf.joblib"
    metrics: dict = Field(default_factory=dict)


def model_path(relative: str) -> Path:
    candidate = (ROOT / relative).resolve()
    models_dir = (ROOT / "models").resolve()
    if not candidate.is_relative_to(models_dir) or not candidate.is_file():
        raise HTTPException(400, "Model file must exist inside the models/ directory")
    return candidate


@app.get("/health")
def health():
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return {"ok": True, "service": "model-registry"}
    except Exception as exc:
        raise HTTPException(503, f"PostgreSQL unavailable: {exc}") from exc


@app.get("/models")
def list_models():
    with connect() as conn:
        rows = conn.execute(
            "SELECT version, model_file, sha256, feature_columns, metrics, is_active, created_at, activated_at "
            "FROM model_versions ORDER BY created_at DESC"
        ).fetchall()
    registered = [
        {"version": r[0], "file": r[1], "sha256": r[2], "features": r[3], "metrics": r[4],
         "active": r[5], "created_at": r[6], "activated_at": r[7], "registered": True}
        for r in rows
    ]
    known_files = {m["file"] for m in registered}
    local = []
    for path in sorted((ROOT / "models").glob("*.joblib")):
        rel = path.relative_to(ROOT).as_posix()
        if rel not in known_files:
            local.append({"version": path.stem, "file": rel, "active": False,
                          "registered": False, "metrics": {}, "features": FEATURE_COLUMNS})
    metrics_file = ROOT / "models" / "metrics.json"
    if local and metrics_file.is_file():
        try:
            metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
            local[0]["metrics"] = metrics
        except (OSError, json.JSONDecodeError):
            pass
    return {"models": registered + local}


@app.post("/models/register", status_code=201)
def register_model(payload: RegisterModel):
    path = model_path(payload.file)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        with connect() as conn:
            row = conn.execute(
                "INSERT INTO model_versions (version, model_file, sha256, feature_columns, metrics, is_active) "
                "VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, FALSE) "
                "ON CONFLICT (version) DO UPDATE SET model_file=EXCLUDED.model_file, sha256=EXCLUDED.sha256, "
                "feature_columns=EXCLUDED.feature_columns, metrics=EXCLUDED.metrics "
                "RETURNING version, model_file, sha256, is_active",
                (payload.version, path.relative_to(ROOT).as_posix(), digest,
                 json.dumps(FEATURE_COLUMNS), json.dumps(payload.metrics)),
            ).fetchone()
        return {"ok": True, "version": row[0], "file": row[1], "sha256": row[2], "active": row[3]}
    except Exception as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/models/{version}/activate")
def activate_model(version: str):
    try:
        with connect() as conn:
            exists = conn.execute("SELECT 1 FROM model_versions WHERE version=%s", (version,)).fetchone()
            if not exists:
                raise HTTPException(404, "Model version not registered; register it first")
            conn.execute("UPDATE model_versions SET is_active=FALSE WHERE is_active=TRUE")
            conn.execute(
                "UPDATE model_versions SET is_active=TRUE, activated_at=NOW() WHERE version=%s", (version,)
            )
        return {"ok": True, "active_version": version}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(409, str(exc)) from exc
