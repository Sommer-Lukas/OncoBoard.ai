"""TranscriptionAgent — live audio → speaker-tagged transcript.

Two entry points:

  execute(db, session_id)
      Demo / fixture path. Generates a realistic meeting transcript for the
      session's case using Gemini Flash, saves the segments to the transcripts
      table, and returns a structured TranscriptionOutput. Used when no real
      audio is available (CI, demos, pre-production testing).

  transcribe_audio(db, session_id, audio_bytes, *, mime_type="audio/wav")
      Real-audio path. Sends audio bytes to Gemini Flash for speaker-tagged
      transcription, saves segments to the transcripts table, and returns the
      same TranscriptionOutput. This is the live-meeting entry point.

Both paths use the same output schema and DB writes, so downstream agents
(RecommendationAgent) are agnostic to which path produced the transcript.

ARCHITECTURE NOTE:
  Full live audio requires a HIPAA-compliant audio pipeline. In this build
  the demo path is the default; transcribe_audio() is the hook for when a
  real audio stream is wired up. See ARCHITECTURE.md §5.

GEMINI AUDIO API:
  Gemini Flash supports inline audio via Part.from_bytes() — the same
  multimodal mechanism used for images. For short clips (<20 MB), inline
  bytes work without uploading to the Files API. For longer recordings,
  pre-upload via the Files API and pass the file URI instead. Here we use
  the inline approach to keep the MVP self-contained.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aiosqlite
from pydantic import BaseModel, ValidationError

from src.agents.session_base import SessionBaseAgent
from src.agents.types import AgentError, CaseNotFoundError, SessionNotFoundError
from src.db import repository as repo
from src.db.models import Case, Session, Transcript, AgentOutput

_FIXTURE_SYSTEM = (
    "You are simulating a multidisciplinary tumor board meeting transcript for a "
    "breast cancer case. Generate a clinically accurate dialogue between four "
    "specialists — Oncologist, Radiologist, Pathologist, and Surgeon — discussing "
    "the patient. The discussion should cover imaging findings, pathology, applicable "
    "guidelines, treatment options, and a closing consensus. "
    "Each turn should be 1–3 sentences. Generate 12–16 turns total. "
    "Timestamps begin at 0 ms and increment by 8000–15000 ms per turn. "
    "Respond strictly as JSON matching the provided schema."
)

_AUDIO_SYSTEM = (
    "You are a medical meeting transcription specialist. "
    "Transcribe the audio and identify each speaker as their clinical role "
    "(e.g. Oncologist, Radiologist, Pathologist, Surgeon, Coordinator) based on "
    "context. If the role cannot be determined, label as 'Speaker N'. "
    "Preserve medical terminology exactly. Timestamps are millisecond offsets from "
    "the start of the audio. "
    "Respond strictly as JSON matching the provided schema."
)


class TranscriptSegment(BaseModel):
    speaker: str
    text: str
    timestamp_ms: int


class _SegmentList(BaseModel):
    segments: list[TranscriptSegment]


class TranscriptionOutput(BaseModel):
    session_id: str
    segment_count: int
    speakers_detected: list[str]


def _build_output(session_id: str, segments: list[TranscriptSegment]) -> TranscriptionOutput:
    speakers = sorted({s.speaker for s in segments})
    return TranscriptionOutput(
        session_id=session_id,
        segment_count=len(segments),
        speakers_detected=speakers,
    )


def _parse_segments(raw_text: str, session_id: str) -> list[TranscriptSegment]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise AgentError(
            f"TranscriptionAgent could not parse Gemini response as JSON: {e}"
        ) from e
    try:
        return _SegmentList.model_validate(payload).segments
    except ValidationError as e:
        raise AgentError(
            f"Gemini response did not match transcript segment schema: {e}"
        ) from e


async def _save_segments(
    db: aiosqlite.Connection,
    session_id: str,
    segments: list[TranscriptSegment],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for seg in segments:
        await repo.add_transcript(
            db,
            Transcript(
                session_id=session_id,
                speaker=seg.speaker,
                text=seg.text,
                timestamp_ms=seg.timestamp_ms,
                created_at=now,
            ),
        )


class TranscriptionAgent(SessionBaseAgent[TranscriptionOutput]):
    """Produces a speaker-tagged transcript for a tumor board session."""

    name = "TranscriptionAgent"
    model_tier = "flash"
    output_schema = TranscriptionOutput

    async def run(
        self, db: aiosqlite.Connection, session: Session, case: Case, *, run_id: str
    ) -> TranscriptionOutput:
        """Demo path: generate a fixture transcript via Gemini from case data."""
        prompt = (
            "Generate a realistic tumor board meeting transcript for this breast "
            "cancer case:\n\n"
            f"  Case ID: {case.case_id}\n"
            f"  Age at diagnosis: {case.age_at_diagnosis or 'Unknown'}\n"
            f"  AJCC stage: {case.ajcc_stage or 'Unknown'} "
            f"(T{case.ajcc_t or '?'} N{case.ajcc_n or '?'} M{case.ajcc_m or '?'})\n"
            f"  ER: {case.er_status or 'Unknown'}  "
            f"PR: {case.pr_status or 'Unknown'}  "
            f"HER2: {case.her2_status or 'Unknown'}\n"
            f"  Molecular subtype: {case.molecular_subtype or 'Unknown'}\n"
            f"  Histological type: {case.histological_type or 'Unknown'}\n"
            f"  Surgical procedure: {case.surgical_procedure or 'Not yet performed'}\n\n"
            "Produce a speaker-tagged dialogue with realistic clinical content. "
            "The transcript must end with an emerging consensus statement."
        )

        resp = await self.call_gemini(
            prompt=prompt,
            system_instruction=_FIXTURE_SYSTEM,
            response_schema=_SegmentList,
        )

        segments = _parse_segments(resp.text, session.session_id)
        if not segments:
            raise AgentError("TranscriptionAgent: Gemini returned an empty transcript")

        await _save_segments(db, session.session_id, segments)
        return _build_output(session.session_id, segments)

    async def transcribe_audio(
        self,
        db: aiosqlite.Connection,
        session_id: str,
        audio_bytes: bytes,
        *,
        mime_type: str = "audio/wav",
    ) -> TranscriptionOutput:
        """Real-audio path: transcribe audio bytes using Gemini's audio understanding.

        Sends audio inline to Gemini Flash (suitable for clips under ~20 MB).
        Speaker identification is inferred from clinical role context in speech.
        All segments are saved to the transcripts table before returning.

        For recordings larger than ~20 MB, pre-upload to the Gemini Files API and
        use a URI-based call instead of this inline approach.
        """
        import time as _time

        start = _time.perf_counter()
        run_id = str(uuid.uuid4())

        session = await repo.get_session(db, session_id)
        if session is None:
            raise SessionNotFoundError(f"session {session_id} not found")
        case = await repo.get_case(db, session.case_id)
        if case is None:
            raise CaseNotFoundError(
                f"case {session.case_id} not found for session {session_id}"
            )

        prompt = (
            "Transcribe this tumor board meeting recording. Identify each speaker "
            "by their clinical role based on context clues in their speech. "
            "Produce speaker-tagged segments with millisecond timestamps. "
            "Preserve all medical terminology exactly as spoken."
        )

        resp = await self.gemini.generate(
            model_tier=self.model_tier,
            prompt=prompt,
            system_instruction=_AUDIO_SYSTEM,
            response_schema=_SegmentList,
            audio_data=audio_bytes,
            audio_mime_type=mime_type,
        )
        tokens_used = resp.tokens_used

        segments = _parse_segments(resp.text, session_id)
        if not segments:
            raise AgentError("TranscriptionAgent: Gemini returned an empty transcript")

        await _save_segments(db, session_id, segments)
        output = _build_output(session_id, segments)

        duration_ms = int((_time.perf_counter() - start) * 1000)
        await repo.save_agent_output(
            db,
            AgentOutput(
                case_id=session.case_id,
                agent_name=self.name,
                run_id=run_id,
                output=output.model_dump(),
                status="success",
                duration_ms=duration_ms,
                tokens_used=tokens_used,
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
        return output
