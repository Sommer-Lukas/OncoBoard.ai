<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useMeetingStore } from '../src/stores/meeting.js'

const props = defineProps({
  caseId: { type: String, required: true },
})

const meeting = useMeetingStore()

// ── Derived state ─────────────────────────────────────────────────────────────

const state       = computed(() => meeting.getState(props.caseId))
const lines       = computed(() => meeting.getTranscripts(props.caseId))
const decisions   = computed(() => meeting.getDecisions(props.caseId))
const elapsed     = computed(() => meeting.getElapsed(props.caseId))
const error       = computed(() => meeting.getError(props.caseId))
const isAudio     = computed(() => meeting.getIsAudio(props.caseId))
const isDemo      = computed(() => meeting.getIsDemo(props.caseId))

const isRecording   = computed(() => state.value === 'recording')
const isDone        = computed(() => state.value === 'done')
const isProcessing  = computed(() => state.value === 'processing')
const isReady       = computed(() => state.value === 'ready')
const isDiscussed   = computed(() => state.value === 'discussed')
const hasError      = computed(() => state.value === 'error')
const isActive      = computed(() => !['idle'].includes(state.value))

const elapsedFmt = computed(() => {
  const s = elapsed.value
  const m = Math.floor(s / 60).toString().padStart(2, '0')
  const sec = (s % 60).toString().padStart(2, '0')
  return `${m}:${sec}`
})

// ── Tabs ──────────────────────────────────────────────────────────────────────

const activeTab = ref('transcript')

// Switch to decisions tab automatically when recommendation is ready
watch(() => state.value, (s) => {
  if (s === 'ready' || s === 'discussed') activeTab.value = 'decisions'
})

const decisionCount = computed(() => decisions.value?.decisions?.length ?? 0)

// ── Scroll to bottom on new lines ────────────────────────────────────────────

const transcriptEl = ref(null)

watch(() => lines.value.length, async () => {
  await nextTick()
  if (transcriptEl.value) {
    transcriptEl.value.scrollTop = transcriptEl.value.scrollHeight
  }
})

// ── Actions ───────────────────────────────────────────────────────────────────

function handleStart() {
  if (!props.caseId || isRecording.value) return
  if (isActive.value) meeting.resumeRecording(props.caseId)
  else meeting.startRecording(props.caseId)
}

function handleStop() {
  meeting.stopRecording(props.caseId)
}

async function handleCaptureDecisions() {
  await meeting.captureDecisions(props.caseId)
}

function handleConfirm() {
  meeting.confirmConsensus(props.caseId)
}

// ── Decision type display ─────────────────────────────────────────────────────

const DECISION_ICONS = {
  treatment:       'medication',
  staging:         'bar_chart',
  workup:          'science',
  follow_up:       'event',
  clinical_trial:  'biotech',
  pathology_review:'biotech',
  imaging_review:  'image',
  other:           'help_outline',
}

function decisionIcon(type) {
  return DECISION_ICONS[type] ?? 'help_outline'
}

function formatTimestamp(ms) {
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  if (m === 0) return `${sec}s`
  return `${m}m ${sec}s`
}
</script>

<template>
  <div class="live-panel">

    <!-- ── Header ── -->
    <div class="panel-header">
      <div class="panel-title">
        <span class="material-symbols-outlined" style="font-size:18px">{{ isAudio && isRecording ? 'mic' : 'mic_none' }}</span>
        Live Transcript
        <span v-if="isDemo && isActive" class="demo-chip">Demo</span>
      </div>

      <div class="panel-controls">
        <!-- Timer while recording -->
        <div v-if="isRecording" class="recording-status">
          <span class="pulse-dot"></span>
          <span class="elapsed">{{ elapsedFmt }}</span>
        </div>

        <!-- Done/processing/ready labels -->
        <span v-else-if="isDone" class="status-label label-done">Stopped</span>
        <span v-else-if="isProcessing" class="status-label label-processing">
          <span class="mini-spinner"></span>Analyzing…
        </span>
        <span v-else-if="isReady" class="status-label label-ready">
          <span class="material-symbols-outlined" style="font-size:13px">check_circle</span>
          Ready
        </span>
        <span v-else-if="isDiscussed" class="status-label label-discussed">
          <span class="material-symbols-outlined" style="font-size:13px">verified</span>
          Discussed
        </span>

        <!-- Buttons -->
        <button v-if="isRecording" class="stop-btn" @click="handleStop">
          <span class="material-symbols-outlined" style="font-size:14px">stop</span>
          Stop
        </button>
        <template v-else-if="!isProcessing">
          <button class="start-btn" @click="handleStart">
            <span class="material-symbols-outlined" style="font-size:14px">fiber_manual_record</span>
            {{ isActive ? 'Resume' : hasError ? 'Retry' : 'Start' }}
          </button>
        </template>
      </div>
    </div>

    <!-- ── Tabs (only after session starts) ── -->
    <div v-if="isActive" class="tab-bar">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'transcript' }"
        @click="activeTab = 'transcript'"
      >
        Transcript
        <span v-if="lines.length" class="tab-count">{{ lines.length }}</span>
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'decisions' }"
        @click="activeTab = 'decisions'"
      >
        Decisions
        <span v-if="decisionCount" class="tab-count tab-count-green">{{ decisionCount }}</span>
      </button>
    </div>

    <!-- ── Content ── -->
    <div class="panel-body" ref="transcriptEl">

      <!-- TRANSCRIPT TAB -->
      <template v-if="activeTab === 'transcript'">

        <!-- Idle: not started yet -->
        <div v-if="!isActive" class="empty-state">
          <span class="material-symbols-outlined" style="font-size:36px;color:#DADCE0">mic_none</span>
          <div>Press <strong>Start</strong> to begin<br>capturing the meeting</div>
        </div>

        <!-- Error -->
        <div v-else-if="hasError" class="empty-state is-error">
          <span class="material-symbols-outlined" style="font-size:36px;color:#EA4335">error_outline</span>
          <div>{{ error || 'An error occurred' }}</div>
          <button class="retry-btn" @click="handleStart">Retry</button>
        </div>

        <!-- Audio recording in progress (no lines yet — mic is capturing) -->
        <div v-else-if="isRecording && isAudio" class="empty-state audio-recording-state">
          <div class="audio-wave">
            <span></span><span></span><span></span><span></span><span></span>
          </div>
          <div>Microphone recording in progress<br><small>Press <strong>Stop</strong> to transcribe with Gemini</small></div>
        </div>

        <!-- Lines -->
        <TransitionGroup v-else name="line-in" tag="div" class="transcript-lines">
          <div
            v-for="(line, idx) in lines"
            :key="idx"
            class="transcript-line"
          >
            <div class="line-meta">
              <span class="speaker">{{ line.speaker }}</span>
              <span class="ts">{{ formatTimestamp(line.timestamp_ms) }}</span>
            </div>
            <div class="line-text">{{ line.text }}</div>
          </div>
        </TransitionGroup>

        <!-- Typing indicator while streaming -->
        <div v-if="isRecording && lines.length > 0" class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </template>

      <!-- DECISIONS TAB -->
      <template v-else-if="activeTab === 'decisions'">

        <!-- Processing spinner -->
        <div v-if="isProcessing" class="empty-state">
          <div class="processing-ring"></div>
          <div>RecommendationAgent is analyzing<br>the transcript…</div>
        </div>

        <!-- No decisions yet -->
        <div v-else-if="!decisions" class="empty-state">
          <span class="material-symbols-outlined" style="font-size:36px;color:#DADCE0">pending_actions</span>
          <div>Decisions will appear here<br>after capturing the transcript</div>
        </div>

        <!-- Decisions content -->
        <template v-else>

          <!-- Overall treatment direction -->
          <div class="direction-card">
            <div class="direction-label">Overall Treatment Direction</div>
            <div class="direction-text">{{ decisions.overall_treatment_direction }}</div>
          </div>

          <!-- Decision moments -->
          <div
            v-for="(d, i) in decisions.decisions"
            :key="i"
            class="decision-card"
            :class="{ 'is-consensus': d.consensus_reached }"
          >
            <div class="decision-top">
              <div class="decision-type-wrap">
                <span class="material-symbols-outlined decision-type-icon">{{ decisionIcon(d.decision_type) }}</span>
                <span class="decision-type">{{ d.decision_type.replace('_', ' ') }}</span>
              </div>
              <span v-if="d.consensus_reached" class="consensus-badge">
                <span class="material-symbols-outlined" style="font-size:12px">check</span>
                Consensus
              </span>
              <span v-else class="pending-badge">Pending</span>
            </div>

            <div class="decision-summary">{{ d.summary }}</div>

            <div v-if="d.contributing_specialists?.length" class="decision-meta">
              <span class="material-symbols-outlined" style="font-size:12px;color:#5F6368">group</span>
              {{ d.contributing_specialists.join(', ') }}
            </div>

            <div v-if="d.evidence_cited?.length" class="decision-evidence">
              <span class="material-symbols-outlined" style="font-size:12px;color:#1A73E8">bookmark</span>
              {{ d.evidence_cited.join(' · ') }}
            </div>

            <div v-if="d.caveats?.length" class="decision-caveats">
              <span class="material-symbols-outlined" style="font-size:11px;color:#FBBC04">warning</span>
              {{ d.caveats.join(' · ') }}
            </div>
          </div>

          <!-- Next steps -->
          <div v-if="decisions.next_steps?.length" class="steps-section">
            <div class="steps-title">Next Steps</div>
            <div v-for="(step, i) in decisions.next_steps" :key="i" class="step-item">
              <span class="material-symbols-outlined" style="font-size:13px;color:#34A853">arrow_right</span>
              {{ step }}
            </div>
          </div>

          <!-- Unresolved -->
          <div v-if="decisions.unresolved_items?.length" class="unresolved-section">
            <div class="steps-title">Unresolved</div>
            <div v-for="(item, i) in decisions.unresolved_items" :key="i" class="step-item is-unresolved">
              <span class="material-symbols-outlined" style="font-size:13px;color:#FBBC04">schedule</span>
              {{ item }}
            </div>
          </div>

        </template>
      </template>

    </div>

    <!-- ── Footer actions ── -->
    <div v-if="isActive" class="panel-footer">

      <!-- After transcription: Capture Decisions -->
      <button
        v-if="isDone"
        class="action-btn btn-primary"
        @click="handleCaptureDecisions"
      >
        <span class="material-symbols-outlined" style="font-size:16px">analytics</span>
        Capture Decisions
      </button>

      <!-- After recommendation: Confirm Consensus -->
      <button
        v-else-if="isReady"
        class="action-btn btn-confirm"
        @click="handleConfirm"
      >
        <span class="material-symbols-outlined" style="font-size:16px">how_to_vote</span>
        Confirm Board Consensus
      </button>

      <!-- Confirmed -->
      <div v-else-if="isDiscussed" class="gate-confirmed">
        <span class="material-symbols-outlined" style="font-size:16px;color:#34A853">verified</span>
        Consensus confirmed
      </div>

      <!-- Processing: non-interactive -->
      <div v-else-if="isProcessing" class="gate-processing">
        <span class="mini-spinner"></span>
        Running RecommendationAgent…
      </div>

    </div>

  </div>
</template>

<style scoped>
.live-panel {
  width: 380px;
  background: #fff;
  border-left: 1px solid #DADCE0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  box-shadow: -2px 0 8px rgba(60,64,67,.08);
  overflow: hidden;
}

/* ── Header ── */
.panel-header {
  padding: 14px 18px;
  border-bottom: 1px solid #E8EAED;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.panel-title {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  display: flex;
  align-items: center;
  gap: 7px;
}

.panel-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Recording */
.recording-status {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #EA4335;
}

.pulse-dot {
  width: 7px; height: 7px;
  border-radius: 50%; background: #EA4335; flex-shrink: 0;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.8)} }

.elapsed {
  font-family: 'Roboto Mono', monospace;
  font-size: 12px;
  font-weight: 500;
}

/* Status labels */
.status-label {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; font-weight: 500; padding: 3px 8px;
  border-radius: 999px;
}

.label-done       { background: #F8F9FA; color: #5F6368; }
.label-processing { background: #D2E3FC; color: #174EA6; }
.label-ready      { background: #E6F4EA; color: #137333; }
.label-discussed  { background: #E6F4EA; color: #137333; }

.mini-spinner {
  width: 11px; height: 11px;
  border: 2px solid rgba(23,78,166,.2);
  border-top-color: #174EA6;
  border-radius: 50%;
  animation: spin .8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Buttons */
.start-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 13px; border-radius: 999px; border: none;
  background: #34A853; color: #fff; font-size: 12px; font-weight: 500;
  cursor: pointer; font-family: 'Roboto',sans-serif; transition: background 150ms;
}
.start-btn:hover { background: #2d9247; }

.stop-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 13px; border-radius: 999px; border: none;
  background: #FCE8E6; color: #C5221F; font-size: 12px; font-weight: 500;
  cursor: pointer; font-family: 'Roboto',sans-serif; transition: background 150ms;
}
.stop-btn:hover { background: #f5c6c2; }

/* ── Tabs ── */
.tab-bar {
  display: flex; border-bottom: 1px solid #E8EAED; flex-shrink: 0;
}

.tab-btn {
  flex: 1; padding: 9px 0; border: none; background: none; cursor: pointer;
  font-size: 12px; font-weight: 500; color: #5F6368;
  font-family: 'Roboto',sans-serif;
  display: flex; align-items: center; justify-content: center; gap: 5px;
  border-bottom: 2px solid transparent; transition: color 150ms, border-color 150ms;
}
.tab-btn.active { color: #1A73E8; border-bottom-color: #1A73E8; }

.tab-count {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%; background: #E8EAED;
  font-size: 10px; font-weight: 600;
}
.tab-count-green { background: #E6F4EA; color: #137333; }

/* ── Body ── */
.panel-body {
  flex: 1; overflow-y: auto; padding: 14px 16px;
  display: flex; flex-direction: column; gap: 0;
}

.empty-state {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 10px; color: #80868B; font-size: 13px;
  text-align: center; padding: 40px 12px; line-height: 1.5;
}

.empty-state.is-error { color: #C5221F; }

.retry-btn {
  margin-top: 6px; padding: 6px 16px; border-radius: 999px;
  border: 1px solid #DADCE0; background: #fff; color: #202124;
  font-size: 12px; cursor: pointer; font-family: 'Roboto',sans-serif;
}

/* Transcript lines */
.transcript-lines { display: flex; flex-direction: column; gap: 14px; }

.transcript-line { }

.line-meta {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 3px;
}

.speaker { font-size: 12px; font-weight: 600; color: #202124; }
.ts      { font-size: 11px; color: #9AA0A6; font-family: 'Roboto Mono', monospace; }

.line-text {
  font-size: 13px; color: #3C4043; line-height: 1.55;
}

/* Line entrance animation */
.line-in-enter-active {
  transition: opacity 300ms, transform 300ms;
}
.line-in-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

/* Typing indicator */
.typing-indicator {
  display: flex; align-items: center; gap: 4px;
  padding: 10px 0 2px;
}
.typing-indicator span {
  width: 6px; height: 6px; border-radius: 50%; background: #DADCE0;
  animation: typing-bounce 1.2s ease-in-out infinite;
}
.typing-indicator span:nth-child(2) { animation-delay: .2s; }
.typing-indicator span:nth-child(3) { animation-delay: .4s; }

@keyframes typing-bounce {
  0%,60%,100% { transform: translateY(0); }
  30%          { transform: translateY(-5px); background: #9AA0A6; }
}

/* Processing ring */
.processing-ring {
  width: 36px; height: 36px;
  border: 3px solid #D2E3FC;
  border-top-color: #1A73E8;
  border-radius: 50%;
  animation: spin .9s linear infinite;
}

/* ── Decision cards ── */
.direction-card {
  background: #EEF3FD; border-radius: 10px;
  padding: 12px 14px; margin-bottom: 14px;
}
.direction-label {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .05em; color: #174EA6; margin-bottom: 5px;
}
.direction-text { font-size: 13px; color: #202124; line-height: 1.5; }

.decision-card {
  border: 1px solid #E8EAED; border-radius: 10px;
  padding: 11px 13px; margin-bottom: 10px;
}
.decision-card.is-consensus { border-color: #CEEAD6; background: #F8FFF9; }

.decision-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 6px;
}
.decision-type-wrap {
  display: flex; align-items: center; gap: 5px;
}
.decision-type-icon { font-size: 14px; color: #5F6368; }
.decision-type {
  font-size: 11px; font-weight: 600; text-transform: capitalize;
  color: #5F6368; letter-spacing: .03em;
}

.consensus-badge {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 10px; font-weight: 600; padding: 2px 7px;
  border-radius: 999px; background: #E6F4EA; color: #137333;
}
.pending-badge {
  font-size: 10px; font-weight: 600; padding: 2px 7px;
  border-radius: 999px; background: #FEF7E0; color: #B06000;
}

.decision-summary { font-size: 13px; color: #202124; line-height: 1.5; margin-bottom: 5px; }

.decision-meta,
.decision-evidence,
.decision-caveats {
  display: flex; align-items: flex-start; gap: 4px;
  font-size: 11px; color: #5F6368; margin-top: 4px; line-height: 1.4;
}
.decision-evidence { color: #174EA6; }
.decision-caveats  { color: #B06000; }

/* Steps / unresolved */
.steps-section, .unresolved-section {
  margin-top: 12px;
}
.steps-title {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .05em; color: #5F6368; margin-bottom: 7px;
}
.step-item {
  display: flex; align-items: flex-start; gap: 4px;
  font-size: 12px; color: #3C4043; margin-bottom: 5px; line-height: 1.45;
}
.step-item.is-unresolved { color: #B06000; }

/* ── Footer ── */
.panel-footer {
  padding: 12px 16px;
  border-top: 1px solid #E8EAED;
  flex-shrink: 0;
}

.action-btn {
  width: 100%; display: flex; align-items: center; justify-content: center;
  gap: 7px; padding: 10px; border-radius: 10px; border: none;
  font-size: 13px; font-weight: 500; cursor: pointer;
  font-family: 'Roboto',sans-serif; transition: background 150ms;
}

.btn-primary {
  background: #1A73E8; color: #fff;
}
.btn-primary:hover { background: #1765CC; }

.btn-confirm {
  background: #34A853; color: #fff;
}
.btn-confirm:hover { background: #2d9247; }

.gate-confirmed {
  display: flex; align-items: center; justify-content: center;
  gap: 7px; font-size: 12px; color: #137333; font-weight: 500;
  padding: 8px;
}

.gate-processing {
  display: flex; align-items: center; justify-content: center;
  gap: 8px; font-size: 12px; color: #5F6368; padding: 8px;
}

/* Demo mode chip */
.demo-chip {
  font-size: 9px; font-weight: 700; text-transform: uppercase;
  padding: 2px 6px; border-radius: 999px;
  background: #FEF7E0; color: #B06000; letter-spacing: .04em;
  margin-left: 4px;
}

/* Audio recording waveform */
.audio-recording-state small { font-size: 11px; color: #9AA0A6; }

.audio-wave {
  display: flex; align-items: flex-end; gap: 3px; height: 28px;
}
.audio-wave span {
  width: 4px; border-radius: 2px; background: #EA4335;
  animation: wave-bar 1.1s ease-in-out infinite;
}
.audio-wave span:nth-child(1) { height: 10px; animation-delay: 0s; }
.audio-wave span:nth-child(2) { height: 22px; animation-delay: .15s; }
.audio-wave span:nth-child(3) { height: 16px; animation-delay: .3s; }
.audio-wave span:nth-child(4) { height: 24px; animation-delay: .45s; }
.audio-wave span:nth-child(5) { height: 12px; animation-delay: .6s; }

@keyframes wave-bar {
  0%,100% { transform: scaleY(1); opacity: .7; }
  50%      { transform: scaleY(1.6); opacity: 1; }
}
</style>
