"""RadiologyAgent — interprets imaging findings in BI-RADS language.

Reads MRI/SVS patch paths from case_files, passes representative tiles to
Gemini Vision, and returns structured findings in BI-RADS format. Falls back
to text-only generation if image files are not accessible on disk.
"""
from __future__ import annotations

import json
import os
import tempfile

import asyncpg
import httpx
from pydantic import BaseModel, ValidationError

from src.agents.base import BaseAgent
from src.agents.types import AgentError
from src.db import repository as repo
from src.db.models import Case

_MAX_TILES = 5


def _is_accessible(path: str) -> bool:
    if path.startswith(("http://", "https://")):
        return True
    return os.path.isfile(path)


async def _resolve_image_paths(paths: list[str]) -> tuple[list[str], list[str]]:
    """Return (local_paths, temp_file_paths_to_clean_up).

    URL paths are downloaded to named temp files. Local paths are returned as-is.
    Inaccessible URLs are silently dropped.
    """
    local: list[str] = []
    tmp: list[str] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for path in paths:
            if path.startswith(("http://", "https://")):
                try:
                    r = await client.get(path)
                    r.raise_for_status()
                    suffix = ".jpg" if path.lower().endswith((".jpg", ".jpeg")) else ".png"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
                        tf.write(r.content)
                        tmp.append(tf.name)
                        local.append(tf.name)
                except Exception:
                    pass
            else:
                local.append(path)
    return local, tmp


_SYSTEM = (
    "You are a breast-specialized radiologist reviewing imaging for a tumor board. "
    "Describe findings using formal BI-RADS lexicon (ACR BI-RADS 5th edition). "
    "Do not issue treatment recommendations — surface imaging findings only. "
    "Respond strictly as JSON matching the provided schema."
)


class BiRadsFindings(BaseModel):
    case_id: str
    overall_birads_category: str          # e.g. "BI-RADS 4B — Suspicious"
    breast_density: str                   # e.g. "ACR C — Heterogeneously dense"
    mass_findings: list[str]
    calcification_findings: list[str]
    associated_features: list[str]
    comparison_with_prior: str | None
    radiologist_impression: str
    imaging_modalities_reviewed: list[str]
    data_gaps: list[str]


class RadiologyAgent(BaseAgent[BiRadsFindings]):
    name = "RadiologyAgent"
    model_tier = "vision"
    output_schema = BiRadsFindings

    async def run(
        self, db: asyncpg.Connection, case: Case, *, run_id: str
    ) -> BiRadsFindings:
        files = await repo.list_case_files(db, case.case_id)

        mri = [f for f in files if f.file_type == "mri_patch"]
        svs = [f for f in files if f.file_type == "svs_patch"]
        candidates = mri or svs

        # One tile per series up to _MAX_TILES
        seen_series: set[str | None] = set()
        sampled_paths: list[str] = []
        for f in candidates:
            if f.series_id not in seen_series:
                seen_series.add(f.series_id)
                sampled_paths.append(f.file_path)
                if len(sampled_paths) >= _MAX_TILES:
                    break

        accessible = [p for p in sampled_paths if _is_accessible(p)]
        modalities: list[str] = []
        if mri:
            modalities.append("MRI")
        if svs:
            modalities.append("H&E Whole Slide (SVS patch)")

        clinical_ctx = (
            f"Patient: {case.age_at_diagnosis or 'unknown'} yo, "
            f"Stage {case.ajcc_stage or 'unknown'}, "
            f"ER {case.er_status or 'unknown'}, "
            f"PR {case.pr_status or 'unknown'}, "
            f"HER2 {case.her2_status or 'unknown'}. "
            f"Histology: {case.histological_type or 'unknown'}. "
            f"Anatomic subdivision: {case.anatomic_subdivision or 'unknown'}."
        )

        if accessible:
            prompt = (
                f"Clinical context: {clinical_ctx}\n"
                f"Imaging modalities: {', '.join(modalities)}.\n\n"
                "Review the attached imaging tiles and provide BI-RADS findings. "
                "Include: overall BI-RADS category (0–6 with modifier), breast density "
                "(ACR A–D), mass findings (shape/margin/density), calcification findings "
                "(morphology/distribution), associated features, radiologist impression, "
                "and data gaps."
            )
        else:
            prompt = (
                f"Clinical context: {clinical_ctx}\n"
                f"Image files are recorded in the database "
                f"({len(candidates)} file(s): "
                f"{', '.join(set(f.file_type for f in candidates)) if candidates else 'none'}) "
                "but are not accessible on disk.\n\n"
                "Generate a placeholder BI-RADS report noting incomplete imaging review. "
                "Set overall_birads_category to 'BI-RADS 0 (Incomplete — images not available)' "
                "and list the missing files as data_gaps."
            )

        local_paths, tmp_files = await _resolve_image_paths(accessible)
        try:
            resp = await self.call_gemini(
                prompt=prompt,
                system_instruction=_SYSTEM,
                response_schema=BiRadsFindings,
                image_paths=local_paths or None,
            )
        finally:
            for tf in tmp_files:
                try:
                    os.unlink(tf)
                except OSError:
                    pass

        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"RadiologyAgent could not parse Gemini response as JSON: {e}"
            ) from e

        payload["case_id"] = case.case_id
        payload.setdefault("imaging_modalities_reviewed", modalities)
        try:
            return BiRadsFindings.model_validate(payload)
        except ValidationError as e:
            raise AgentError(
                f"Gemini response did not match BiRadsFindings schema: {e}"
            ) from e
