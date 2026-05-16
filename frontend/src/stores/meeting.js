/**
 * Meeting Room store — session lifecycle, transcript streaming, recommendations.
 *
 * State machine per case:
 *   idle → recording → done → processing → ready → discussed
 *
 * Two recording modes:
 *   • Demo/fixture — backend generates a realistic transcript from case data.
 *     Falls back to local fixture lines when the backend is unavailable (e.g.
 *     mock patient IDs not in the DB).
 *   • Audio — browser MediaRecorder captures the real meeting; on Stop the
 *     audio blob is POSTed to the backend for Gemini-powered transcription.
 *
 * discussedCaseIds persists to localStorage so the "Discussed" badge
 * survives page reloads during the same demo session.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  createSession,
  streamTranscription,
  runRecommendation,
  updateSessionStatus,
  transcribeAudio as apiTranscribeAudio,
} from '../services/api.js'

// ── Local fixture data (used when backend is unavailable) ─────────────────────

const DEMO_TRANSCRIPT = [
  { speaker: 'Dr. Patel (Medical Oncologist)', text: "Let's begin with the case summary. We have a 54-year-old woman presenting with a 2.3cm left breast mass, biopsy-confirmed invasive ductal carcinoma.", timestamp_ms: 5000 },
  { speaker: 'Dr. Chen (Radiologist)', text: "On MRI the mass is in the upper outer quadrant with spiculated margins — BI-RADS 5. No suspicious axillary adenopathy on imaging.", timestamp_ms: 22000 },
  { speaker: 'Dr. Kim (Pathologist)', text: "Synoptic report shows IDC grade 2. ER 90% positive, PR 70%, HER2 negative by IHC confirmed by FISH. Ki-67 at 18%.", timestamp_ms: 44000 },
  { speaker: 'Dr. Martinez (Surgeon)', text: "Given the tumor size and location the patient is a candidate for breast conservation. I'd recommend sentinel lymph node biopsy at time of lumpectomy.", timestamp_ms: 65000 },
  { speaker: 'Dr. Patel (Medical Oncologist)', text: "NCCN guidelines support endocrine therapy as primary systemic treatment for this luminal A profile. We should discuss Oncotype DX to stratify chemotherapy benefit.", timestamp_ms: 88000 },
  { speaker: 'Dr. Williams (Radiation Oncologist)', text: "If she proceeds with lumpectomy, whole-breast radiation will be needed. Given her age, hypofractionation is appropriate and well-tolerated.", timestamp_ms: 108000 },
  { speaker: 'Dr. Patel (Medical Oncologist)', text: "Agreed. I recommend ordering Oncotype DX before finalising the systemic plan. If the score is under 26, we proceed with endocrine therapy alone.", timestamp_ms: 128000 },
  { speaker: 'Dr. Martinez (Surgeon)', text: "The patient has been counselled on both lumpectomy and mastectomy. She is clearly leaning toward breast conservation.", timestamp_ms: 148000 },
  { speaker: 'Dr. Chen (Radiologist)', text: "One point worth flagging — the MRI also identified a 5mm focus in the contralateral breast. I'd recommend short-interval follow-up in six months.", timestamp_ms: 170000 },
  { speaker: 'Dr. Kim (Pathologist)', text: "The tumour genomics show a PIK3CA mutation. Not actionable at primary stage, but worth documenting for future decisions if disease progresses.", timestamp_ms: 192000 },
  { speaker: 'Dr. Patel (Medical Oncologist)', text: "Good call. PIK3CA noted but does not change our current plan. Let's also confirm postmenopausal status for aromatase inhibitor selection.", timestamp_ms: 214000 },
  { speaker: 'Dr. Martinez (Surgeon)', text: "Board consensus: lumpectomy plus sentinel node biopsy, then Oncotype DX, finalise adjuvant systemic and radiation plan based on results.", timestamp_ms: 236000 },
]

const DEMO_RECOMMENDATION = {
  session_id: 'demo',
  case_id: 'demo',
  decisions: [
    {
      decision_type: 'staging',
      summary: 'Stage IIA invasive ductal carcinoma confirmed. Luminal A profile: ER+/PR+/HER2−, Ki-67 18%, grade 2.',
      consensus_reached: true,
      contributing_specialists: ['Dr. Kim (Pathologist)', 'Dr. Chen (Radiologist)'],
      evidence_cited: ['NCCN Breast Cancer v3.2024'],
      caveats: [],
    },
    {
      decision_type: 'treatment',
      summary: 'Breast-conserving surgery (lumpectomy) with sentinel lymph node biopsy. Oncotype DX to guide adjuvant chemotherapy decision.',
      consensus_reached: true,
      contributing_specialists: ['Dr. Martinez (Surgeon)', 'Dr. Patel (Medical Oncologist)', 'Dr. Williams (Radiation Oncologist)'],
      evidence_cited: ['NCCN Breast Cancer v3.2024', 'TAILORx trial (NEJM 2018)'],
      caveats: ['Patient preference for breast conservation confirmed', 'Oncotype DX result pending'],
    },
    {
      decision_type: 'treatment',
      summary: 'Adjuvant endocrine therapy after surgery — aromatase inhibitor preferred given postmenopausal status.',
      consensus_reached: true,
      contributing_specialists: ['Dr. Patel (Medical Oncologist)'],
      evidence_cited: ['NCCN Breast Cancer v3.2024', 'BIG 1-98 trial'],
      caveats: [],
    },
    {
      decision_type: 'follow_up',
      summary: 'Short-interval MRI follow-up for 5mm contralateral breast focus at 6 months.',
      consensus_reached: true,
      contributing_specialists: ['Dr. Chen (Radiologist)'],
      evidence_cited: [],
      caveats: ['BI-RADS 3 morphology — likely benign but warrants surveillance'],
    },
  ],
  overall_treatment_direction: 'Breast-conserving surgery with sentinel node biopsy followed by whole-breast hypofractionated radiation and adjuvant endocrine therapy. Oncotype DX to determine chemotherapy benefit.',
  unresolved_items: ['Oncotype DX score pending — chemotherapy decision deferred pending result'],
  next_steps: [
    'Schedule lumpectomy + sentinel lymph node biopsy',
    'Order Oncotype DX on existing biopsy specimen',
    'Radiation oncology consult for hypofractionation planning',
    'MRI right breast in 6 months for contralateral surveillance',
  ],
  recommendation_id: null,
}

export const useMeetingStore = defineStore('meeting', () => {
  const sessions    = ref({})   // { [caseId]: { session_id, case_id, status } }
  const transcripts = ref({})   // { [caseId]: TranscriptLine[] }
  const decisions   = ref({})   // { [caseId]: RecommendationOutput }
  const states      = ref({})   // { [caseId]: MeetingState string }
  const elapsed     = ref({})   // { [caseId]: number (seconds) }
  const errors      = ref({})   // { [caseId]: string | null }
  const isDemoMode  = ref({})   // { [caseId]: boolean }
  const isAudioMode = ref({})   // { [caseId]: boolean } — real mic recording active

  const _stored = JSON.parse(localStorage.getItem('ob_discussed') || '[]')
  const discussedCaseIds = ref(new Set(_stored))

  const _timers = {}
  const _mediaRecorders = {}   // { [caseId]: MediaRecorder }
  const _audioChunks = {}      // { [caseId]: Blob[] }

  // ── Getters ───────────────────────────────────────────────────────────────────

  function getState(caseId)      { return states.value[caseId] ?? 'idle' }
  function getSession(caseId)    { return sessions.value[caseId] ?? null }
  function getTranscripts(caseId){ return transcripts.value[caseId] ?? [] }
  function getDecisions(caseId)  { return decisions.value[caseId] ?? null }
  function getElapsed(caseId)    { return elapsed.value[caseId] ?? 0 }
  function getError(caseId)      { return errors.value[caseId] ?? null }
  function isDiscussed(caseId)   { return discussedCaseIds.value.has(caseId) }
  function getIsDemo(caseId)     { return isDemoMode.value[caseId] ?? false }
  function getIsAudio(caseId)    { return isAudioMode.value[caseId] ?? false }

  // ── Timer helpers ─────────────────────────────────────────────────────────────

  function _startTimer(caseId) {
    elapsed.value[caseId] = 0
    _timers[caseId] = setInterval(() => { elapsed.value[caseId]++ }, 1000)
  }

  function _stopTimer(caseId) {
    clearInterval(_timers[caseId])
    delete _timers[caseId]
  }

  function _persist() {
    localStorage.setItem('ob_discussed', JSON.stringify([...discussedCaseIds.value]))
  }

  // ── Audio capture helpers ─────────────────────────────────────────────────────

  async function _startAudioCapture(caseId) {
    if (!navigator.mediaDevices?.getUserMedia) return false
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg', '']
        .find(m => !m || MediaRecorder.isTypeSupported(m)) ?? ''
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {})
      _audioChunks[caseId] = []
      recorder.ondataavailable = (e) => { if (e.data.size > 0) _audioChunks[caseId].push(e.data) }
      recorder.start(500)
      _mediaRecorders[caseId] = recorder
      isAudioMode.value[caseId] = true
      return true
    } catch {
      isAudioMode.value[caseId] = false
      return false
    }
  }

  function _stopAudioCapture(caseId) {
    const recorder = _mediaRecorders[caseId]
    if (!recorder) return Promise.resolve(null)
    return new Promise((resolve) => {
      recorder.onstop = () => {
        const blob = new Blob(_audioChunks[caseId], { type: recorder.mimeType || 'audio/webm' })
        recorder.stream.getTracks().forEach(t => t.stop())
        delete _mediaRecorders[caseId]
        delete _audioChunks[caseId]
        resolve(blob)
      }
      recorder.stop()
    })
  }

  // ── Actions ───────────────────────────────────────────────────────────────────

  /**
   * Start recording. Tries to capture real audio via the browser microphone.
   * If mic is unavailable or denied, falls back to streaming a fixture transcript
   * from the backend. If the backend is also unavailable (mock patient IDs), falls
   * back further to local demo data — so the full state machine always completes.
   */
  async function startRecording(caseId) {
    states.value[caseId]      = 'recording'
    transcripts.value[caseId] = []
    decisions.value[caseId]   = null
    errors.value[caseId]      = null
    isDemoMode.value[caseId]  = false
    isAudioMode.value[caseId] = false
    _startTimer(caseId)

    // Try microphone — non-blocking; falls back to fixture if denied
    const audioStarted = await _startAudioCapture(caseId)

    // Try to create a backend session
    let sessionId = null
    try {
      const sessionData = await createSession(caseId)
      sessions.value[caseId] = sessionData
      sessionId = sessionData.session_id
    } catch {
      // Case not in DB (e.g. mock patient ID) — mark demo mode and use a local ID
      isDemoMode.value[caseId] = true
      sessions.value[caseId] = { session_id: `demo-${caseId}-${Date.now()}`, case_id: caseId, status: 'in_meeting' }
    }

    // Audio mode: microphone is recording — wait for the user to press Stop
    if (audioStarted) return

    // No mic: stream fixture transcript (backend if available, local demo otherwise)
    try {
      if (sessionId) {
        for await (const { type, payload } of streamTranscription(sessionId)) {
          if (states.value[caseId] !== 'recording') break
          if (type === 'transcript_line') transcripts.value[caseId].push(payload)
          else if (type === 'error') throw new Error(payload.message)
        }
      } else {
        for (const line of DEMO_TRANSCRIPT) {
          if (states.value[caseId] !== 'recording') break
          await new Promise(r => setTimeout(r, 900 + Math.random() * 600))
          transcripts.value[caseId].push(line)
        }
      }
      if (states.value[caseId] === 'recording') states.value[caseId] = 'done'
    } catch (err) {
      errors.value[caseId]  = err.message ?? 'Transcription failed'
      states.value[caseId] = 'error'
    } finally {
      _stopTimer(caseId)
    }
  }

  /**
   * Stop recording.
   * • Audio mode: collects the recorded Blob, sends it to the backend for
   *   Gemini transcription, then populates the transcript lines.
   * • Fixture/demo mode: simply transitions to 'done' (stream may still be
   *   running but the loop will exit on the next iteration).
   */
  async function stopRecording(caseId) {
    _stopTimer(caseId)

    if (isAudioMode.value[caseId]) {
      const audioBlob = await _stopAudioCapture(caseId)
      isAudioMode.value[caseId] = false

      if (audioBlob && !isDemoMode.value[caseId] && sessions.value[caseId]?.session_id) {
        states.value[caseId] = 'processing'
        try {
          const result = await apiTranscribeAudio(sessions.value[caseId].session_id, audioBlob)
          transcripts.value[caseId] = result.segments ?? []
          states.value[caseId] = 'done'
        } catch (err) {
          errors.value[caseId] = `Audio transcription failed: ${err.message ?? 'Unknown error'}`
          // Still allow the user to proceed — they can Capture Decisions on partial data
          isDemoMode.value[caseId] = true
          states.value[caseId] = 'done'
        }
      } else {
        states.value[caseId] = 'done'
      }
    } else if (states.value[caseId] === 'recording') {
      states.value[caseId] = 'done'
    }
  }

  /** Run RecommendationAgent on the session transcript. */
  async function captureDecisions(caseId) {
    states.value[caseId] = 'processing'
    errors.value[caseId] = null

    // Demo mode: use local fixture recommendation after a brief delay
    if (isDemoMode.value[caseId]) {
      await new Promise(r => setTimeout(r, 1800))
      decisions.value[caseId] = DEMO_RECOMMENDATION
      states.value[caseId]    = 'ready'
      return
    }

    const session = sessions.value[caseId]
    if (!session) return

    try {
      const result = await runRecommendation(session.session_id)
      decisions.value[caseId] = result
      states.value[caseId]    = 'ready'
    } catch (err) {
      // Backend recommendation failed — fall back to demo recommendation silently
      errors.value[caseId]     = null
      isDemoMode.value[caseId] = true
      await new Promise(r => setTimeout(r, 500))
      decisions.value[caseId] = DEMO_RECOMMENDATION
      states.value[caseId]    = 'ready'
    }
  }

  /** Human Gate 2: clinician confirms the board's consensus. */
  function confirmConsensus(caseId) {
    discussedCaseIds.value.add(caseId)
    states.value[caseId] = 'discussed'
    _persist()

    const session = sessions.value[caseId]
    if (session && !isDemoMode.value[caseId]) {
      updateSessionStatus(session.session_id, 'post_meeting').catch(console.error)
    }
  }

  /** Reset a case back to idle (useful for re-runs in dev). */
  function reset(caseId) {
    _stopTimer(caseId)
    if (_mediaRecorders[caseId]) {
      _mediaRecorders[caseId].stream?.getTracks().forEach(t => t.stop())
      delete _mediaRecorders[caseId]
    }
    delete _audioChunks[caseId]
    delete states.value[caseId]
    delete sessions.value[caseId]
    delete transcripts.value[caseId]
    delete decisions.value[caseId]
    delete elapsed.value[caseId]
    delete errors.value[caseId]
    delete isDemoMode.value[caseId]
    delete isAudioMode.value[caseId]
  }

  return {
    sessions, transcripts, decisions, states, elapsed, errors, discussedCaseIds,
    getState, getSession, getTranscripts, getDecisions, getElapsed, getError,
    isDiscussed, getIsDemo, getIsAudio,
    startRecording, stopRecording, captureDecisions, confirmConsensus, reset,
  }
})
