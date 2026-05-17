<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PatientSelector from '../components/PatientSelector.vue'
import CaseDisplay from '../components/CaseDisplay.vue'
import LiveTranscriptPanel from '../components/LiveTranscriptPanel.vue'
import { usePatientsStore } from '../src/stores/patients.js'
import { useAgentsStore } from '../src/stores/agents.js'
import { useMeetingStore } from '../src/stores/meeting.js'

const router = useRouter()
const store = usePatientsStore()
const agentsStore = useAgentsStore()
const meeting = useMeetingStore()

const caseData = ref(null)

onMounted(async () => {
  await store.loadPatients()
  await loadCase()
})

watch(() => store.activeId, loadCase)

async function loadCase() {
  if (!store.activeId) return
  caseData.value = await store.loadCaseData(store.activeId)
  agentsStore.initCase(store.activeId)
}

// Merge pre-meeting agent outputs into caseData
const enrichedCaseData = computed(() => {
  if (!caseData.value) return null
  const raw = agentsStore.getAgentRawData(store.activeId)
  const enriched = { ...caseData.value }

  if (raw.RadiologyAgent?.radiologist_impression) {
    enriched.radiology = raw.RadiologyAgent.radiologist_impression
    enriched.radiologyFull = raw.RadiologyAgent
  }
  if (raw.PathologyAgent?.synoptic_summary) {
    enriched.pathology = raw.PathologyAgent.synoptic_summary
    enriched.pathologyFull = raw.PathologyAgent
  }
  if (raw.GuidelineAgent) {
    const g = raw.GuidelineAgent
    enriched.guidelines = [
      `${g.matched_guideline} — ${g.guideline_pathway}`,
      g.recommendation_category ? `Recommendation category: ${g.recommendation_category} (${g.evidence_level})` : '',
      g.systemic_therapy_options?.length ? `Systemic therapy options: ${g.systemic_therapy_options.join(', ')}` : '',
      g.endocrine_therapy_options?.length ? `Endocrine options: ${g.endocrine_therapy_options.join(', ')}` : '',
      g.radiation_considerations ? `Radiation: ${g.radiation_considerations}` : '',
      g.surgery_considerations ? `Surgery: ${g.surgery_considerations}` : '',
      g.protocol_rationale ? `Rationale: ${g.protocol_rationale}` : '',
    ].filter(Boolean).join('\n')
    enriched.guidelineFull = g
  }
  if (raw.TrialAgent) {
    const t = raw.TrialAgent
    const trialLines = (t.matched_trials ?? []).map(trial =>
      `${trial.nct_id}${trial.phase ? ' (' + trial.phase + ')' : ''}: ${trial.title}\n  ${trial.eligibility_delta}`
    )
    const pubmedLines = (t.pubmed_references ?? []).slice(0, 3).map(r =>
      `PMID ${r.pmid}: ${r.title ?? 'N/A'}${r.source ? ' (' + r.source + ')' : ''}`
    )
    enriched.trials = [
      t.agent_notes,
      trialLines.length ? '\nMatched Trials:\n' + trialLines.join('\n\n') : 'No trials matched.',
      pubmedLines.length ? '\nPubMed References:\n' + pubmedLines.join('\n') : '',
    ].filter(Boolean).join('\n')
    enriched.trialFull = t
  }
  if (raw.SummaryAgent) {
    enriched.summaryNarrative = raw.SummaryAgent.narrative
    enriched.summaryKeyPoints = raw.SummaryAgent.key_points ?? []
  }
  return enriched
})

const pipelineStatus = computed(() => agentsStore.getPipelineStatus(store.activeId ?? ''))
const isRunning      = computed(() => pipelineStatus.value === 'running')
const hasAgentData   = computed(() => Object.keys(agentsStore.getAgentRawData(store.activeId ?? '')).length > 0)
const currentAgents  = computed(() => agentsStore.getForPatient(store.activeId ?? ''))
const verification   = computed(() => agentsStore.getVerification(store.activeId ?? ''))

// Meeting state for active case
const meetingState   = computed(() => meeting.getState(store.activeId ?? ''))
const isDiscussed    = computed(() => meeting.isDiscussed(store.activeId ?? ''))

const AGENT_SHORT = {
  CaseCompiler:     'Compiler',
  SummaryAgent:     'Summary',
  RadiologyAgent:   'Radiology',
  PathologyAgent:   'Pathology',
  GuidelineAgent:   'Guidelines',
  TrialAgent:       'Trials',
  HistoryCaseAgent: 'History',
}

function rerunPipeline() {
  if (!store.activeId || isRunning.value) return
  agentsStore.runPipeline(store.activeId)
}

function endMeeting() {
  // Confirm consensus if not already done, then go to post-meeting
  if (store.activeId && !isDiscussed.value && meetingState.value === 'ready') {
    meeting.confirmConsensus(store.activeId)
  }
  router.push('/post-meeting')
}
</script>

<template>
  <div class="meeting-shell">

    <!-- ── Topbar ── -->
    <div class="meeting-topbar">
      <div class="topbar-left">
        <button class="icon-btn" title="Back to dashboard" @click="router.push('/')">
          <span class="material-symbols-outlined" style="font-size:20px;color:#5F6368">arrow_back</span>
        </button>
        <span class="material-symbols-outlined brand-icon">ecg_heart</span>
        <span class="topbar-title">Meeting Room</span>

        <div class="live-chip">
          <span class="live-dot"></span>
          Live
        </div>

        <!-- Discussed badge for active case -->
        <Transition name="fade-in">
          <div v-if="isDiscussed" class="discussed-chip">
            <span class="material-symbols-outlined" style="font-size:13px">verified</span>
            Discussed
          </div>
        </Transition>
      </div>

      <div class="topbar-right">
        <button class="end-btn" @click="endMeeting">
          <span class="material-symbols-outlined" style="font-size:16px">meeting_room</span>
          End Meeting
        </button>
      </div>
    </div>

    <div class="columns">

      <!-- ── Patient sidebar ── -->
      <PatientSelector
        :patients="store.patients"
        :active-id="store.activeId"
        :discussed-ids="meeting.discussedCaseIds"
        @select="store.setActive($event)"
      />

      <!-- ── Main case area ── -->
      <div class="main-content">

        <!-- Pre-meeting agent strip -->
        <div v-if="enrichedCaseData" class="agent-strip">
          <div class="agent-strip-dots">
            <div
              v-for="agent in currentAgents"
              :key="agent.name"
              class="agent-dot-item"
              :title="`${agent.name}: ${agent.status}${agent.output ? ' — ' + agent.output : ''}`"
            >
              <span class="agent-dot" :class="agent.status"></span>
              <span class="agent-dot-label">{{ AGENT_SHORT[agent.name] ?? agent.name }}</span>
            </div>
          </div>
          <button
            class="rerun-btn"
            :class="pipelineStatus"
            :disabled="isRunning"
            @click="rerunPipeline"
          >
            <span v-if="isRunning" class="rerun-spinner" aria-hidden="true"></span>
            <span v-else class="material-symbols-outlined" style="font-size:15px">{{ hasAgentData ? 'refresh' : 'smart_toy' }}</span>
            <span v-if="isRunning">Running agents…</span>
            <span v-else-if="hasAgentData">Re-run Pre-Meeting</span>
            <span v-else>Run Pre-Meeting</span>
          </button>
        </div>

        <CaseDisplay v-if="enrichedCaseData" :case-data="enrichedCaseData" :verification="verification" />
        <div v-else class="loading-state">
          <span class="material-symbols-outlined" style="font-size:40px;color:#DADCE0">hourglass_empty</span>
          <div>Loading case data…</div>
        </div>

      </div>

      <!-- ── Transcript + Decisions panel ── -->
      <LiveTranscriptPanel v-if="store.activeId" :case-id="store.activeId" />

    </div>

  </div>
</template>

<style scoped>
.meeting-shell {
  display: flex; flex-direction: column;
  height: 100vh; overflow: hidden; background: #F8F9FA;
}

.meeting-topbar {
  height: 52px; background: #fff; border-bottom: 1px solid #DADCE0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; flex-shrink: 0; z-index: 10;
}

.topbar-left  { display: flex; align-items: center; gap: 12px; }
.topbar-right { display: flex; align-items: center; gap: 10px; }

.icon-btn {
  width: 36px; height: 36px; border-radius: 50%; border: none;
  background: transparent; cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: background 150ms;
}
.icon-btn:hover { background: #F8F9FA; }

.brand-icon    { font-size: 20px; color: #1A73E8; }
.topbar-title  { font-size: 15px; font-weight: 500; color: #202124; }

.live-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 10px; border-radius: 999px;
  background: #FCE8E6; color: #C5221F; font-size: 12px; font-weight: 500;
}
.live-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #EA4335;
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

.discussed-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 10px; border-radius: 999px;
  background: #E6F4EA; color: #137333; font-size: 12px; font-weight: 500;
}

.fade-in-enter-active { transition: opacity 300ms, transform 300ms; }
.fade-in-enter-from   { opacity: 0; transform: scale(.92); }

/* ── Agent status strip ── */
.agent-strip {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; height: 44px; flex-shrink: 0;
  background: #fff; border-bottom: 1px solid #DADCE0; gap: 12px;
}
.agent-strip-dots { display: flex; align-items: center; gap: 14px; overflow: hidden; }
.agent-dot-item   { display: flex; align-items: center; gap: 5px; flex-shrink: 0; cursor: default; }

.agent-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; transition: background 300ms;
}
.agent-dot.idle     { background: #DADCE0; }
.agent-dot.running  { background: #1A73E8; animation: dot-pulse 1.4s ease-in-out infinite; }
.agent-dot.complete { background: #34A853; }
.agent-dot.error    { background: #EA4335; }
.agent-dot-label    { font-size: 11px; color: #5F6368; font-weight: 500; white-space: nowrap; }

.rerun-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 999px; border: 1px solid #DADCE0;
  font-size: 12px; font-weight: 500; cursor: pointer; flex-shrink: 0;
  font-family: 'Roboto',sans-serif; transition: background 150ms;
  background: #fff; color: #202124;
}
.rerun-btn:hover:not(:disabled) { background: #F8F9FA; }
.rerun-btn.running  { background: #D2E3FC; color: #174EA6; border-color: #D2E3FC; cursor: not-allowed; }
.rerun-btn.complete { background: #E6F4EA; color: #137333; border-color: #E6F4EA; }
.rerun-btn.error    { background: #FCE8E6; color: #C5221F; border-color: #FCE8E6; }
.rerun-btn.idle     { background: #1A73E8; color: #fff; border-color: #1A73E8; }
.rerun-btn.idle:hover { background: #1765CC; }

.rerun-spinner {
  width: 13px; height: 13px;
  border: 2px solid rgba(23,78,166,.25); border-top-color: #174EA6;
  border-radius: 50%; animation: spin .8s linear infinite; flex-shrink: 0;
}
@keyframes spin     { to { transform: rotate(360deg); } }
@keyframes dot-pulse{ 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.4)} }

.end-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 16px; border-radius: 999px; border: none;
  background: #EA4335; color: #fff; font-size: 13px; font-weight: 500;
  cursor: pointer; font-family: 'Roboto',sans-serif; transition: background 150ms;
}
.end-btn:hover { background: #c5221f; }

.columns { flex: 1; display: flex; overflow: hidden; }

.main-content {
  flex: 1; overflow: hidden; display: flex;
  flex-direction: column; background: #F8F9FA;
}

.loading-state {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px; font-size: 14px; color: #80868B;
}
</style>
