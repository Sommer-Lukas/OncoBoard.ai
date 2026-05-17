<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PatientHeader from '../components/PatientHeader.vue'
import AgentCard from '../components/AgentCard.vue'
import CaseOutcome from '../components/CaseOutcome.vue'
import ActionTrackerTable from '../components/ActionTrackerTable.vue'
import NoteDraft from '../components/NoteDraft.vue'
import { usePatientsStore } from '../src/stores/patients.js'
import { useAgentsStore } from '../src/stores/agents.js'
import { useMeetingStore } from '../src/stores/meeting.js'
import { saveNote } from '../src/services/api.js'

const router  = useRouter()
const store   = usePatientsStore()
const agents  = useAgentsStore()
const meeting = useMeetingStore()

const caseData = ref(null)

onMounted(async () => {
  await store.loadPatients()
  await loadActive()
})

watch(() => store.activeId, loadActive)

async function loadActive() {
  const id = store.activeId
  if (!id) return
  caseData.value = await store.loadCaseData(id)
  agents.initPostCase(id)
}

// ── Per-case computed state ──────────────────────────────────────────────────

const activeId      = computed(() => store.activeId ?? '')
const postAgents    = computed(() => agents.getPostAgents(activeId.value))
const pipelineStatus= computed(() => agents.getPostPipelineStatus(activeId.value))
const postRaw       = computed(() => agents.getPostRawData(activeId.value))

const completedCount = computed(() => postAgents.value.filter(a => a.status === 'complete').length)
const runningCount   = computed(() => postAgents.value.filter(a => a.status === 'running').length)
const runningAgent   = computed(() => postAgents.value.find(a => a.status === 'running'))
const progressPct    = computed(() =>
  postAgents.value.length ? (completedCount.value / postAgents.value.length) * 100 : 0
)

const isRunning = computed(() => pipelineStatus.value === 'running')
const hasRun    = computed(() => pipelineStatus.value !== 'idle')

// ── Gate / session state ─────────────────────────────────────────────────────

const isDiscussed = computed(() => meeting.isDiscussed(activeId.value))
const isDemoMode  = computed(() => meeting.getIsDemo(activeId.value))
const session     = computed(() => meeting.getSession(activeId.value))

const canRunPipeline = computed(() => isDiscussed.value)

const noSessionError = ref(false)

function startPipeline() {
  if (!canRunPipeline.value || isRunning.value) return
  if (!session.value?.session_id) {
    noSessionError.value = true
    return
  }
  noSessionError.value = false
  agents.runPostPipeline(activeId.value, session.value.session_id)
}

// ── Results derived from agent outputs ───────────────────────────────────────

const decisions = computed(() => meeting.getDecisions(activeId.value))

const outcomeRecommendation = computed(() => {
  if (decisions.value?.overall_treatment_direction) return decisions.value.overall_treatment_direction
  return postRaw.value.NoteDraftAgent?.consensus_plan ?? null
})

const outcomeRationale = computed(() => {
  if (decisions.value?.decisions?.length) {
    return decisions.value.decisions
      .map(d => d.summary)
      .filter(Boolean)
      .join(' · ')
  }
  return postRaw.value.NoteDraftAgent?.board_discussion ?? null
})

const completedDate = computed(() => {
  if (pipelineStatus.value === 'complete') {
    return new Date().toLocaleString('en-US', {
      month: 'long', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit',
    })
  }
  return null
})

const dispatchedActions = computed(() => {
  const created = postRaw.value.ActionDispatchAgent?.actions_created
  if (!created?.length) return []
  return created.map(a => ({
    description: a.description,
    owner: a.owner,
    dueDate: a.due_date,
    status: a.status === 'completed' ? 'complete' : 'pending',
  }))
})

const draftedNote = computed(() => postRaw.value.NoteDraftAgent?.drafted_note ?? null)

const followUpData = computed(() => postRaw.value.FollowUpAgent ?? null)
const schedulingData = computed(() => postRaw.value.SchedulingAgent ?? null)

const showResults = computed(() =>
  pipelineStatus.value === 'complete' &&
  (outcomeRecommendation.value || dispatchedActions.value.length || draftedNote.value)
)

async function handleSaveNote(content) {
  await saveNote(activeId.value, content)
}

// ── Sidebar helpers ──────────────────────────────────────────────────────────

function postStatus(patientId) {
  const ps = agents.getPostPipelineStatus(patientId)
  if (ps === 'complete') return 'complete'
  if (meeting.isDiscussed(patientId)) return 'ready'
  return 'pending'
}
</script>

<template>
  <div class="post-shell">

    <!-- Topbar -->
    <div class="post-topbar">
      <div class="topbar-left">
        <button class="icon-btn" @click="router.push('/')">
          <span class="material-symbols-outlined" style="font-size:20px;color:#5F6368">arrow_back</span>
        </button>
        <div class="topbar-title">Post-Meeting</div>
        <div v-if="agents.postRunningCount > 0" class="live-badge">
          <span class="live-dot" aria-hidden="true"></span>
          LIVE
        </div>
      </div>
      <div class="topbar-right">
        <div v-if="agents.postRunningCount > 0" class="ticker-inner">
          <span class="ticker-agent">{{ runningAgent?.name }}</span>
          <span class="ticker-sep" aria-hidden="true">·</span>
          <span class="ticker-detail">{{ store.activePatient?.name }}</span>
          <span class="ticker-cursor" aria-hidden="true"></span>
        </div>
      </div>
    </div>

    <div class="columns">

      <!-- Sidebar -->
      <div class="sidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">Board Cases</div>
          <div class="sidebar-sub">{{ store.patients.length }} patients</div>
        </div>
        <div class="patient-list">
          <div
            v-for="p in store.patients"
            :key="p.id"
            class="patient-item"
            :class="{ active: p.id === store.activeId }"
            @click="store.setActive(p.id)"
          >
            <div class="patient-name" :class="{ active: p.id === store.activeId }">
              <span class="status-dot" :class="postStatus(p.id)"></span>
              {{ p.name }}
            </div>
            <div class="patient-id">{{ p.id }}</div>
            <div class="status-chip" :class="postStatus(p.id)">
              {{ postStatus(p.id) === 'complete' ? 'Done' : postStatus(p.id) === 'ready' ? 'Ready' : 'Pending' }}
            </div>
          </div>
        </div>
      </div>

      <!-- Main -->
      <div class="main-content">
        <div v-if="store.loading" class="empty-state">
          <span class="material-symbols-outlined" style="font-size:40px;color:#DADCE0">hourglass_empty</span>
          <div>Loading case data…</div>
        </div>

        <template v-else-if="caseData">

          <!-- Patient header bar -->
          <div class="case-topbar">
            <PatientHeader
              :patient-id="caseData.id"
              :name="caseData.name"
              :age="caseData.age"
              :stage="caseData.stage"
              :receptors="caseData.receptors"
            />
          </div>

          <div class="container">

            <!-- Gate 2 status banner -->
            <div class="gate-banner" :class="isDiscussed ? 'gate-open' : 'gate-locked'">
              <span class="material-symbols-outlined gate-icon">
                {{ isDiscussed ? 'lock_open' : 'lock' }}
              </span>
              <div class="gate-text">
                <div class="gate-label">
                  {{ isDiscussed ? 'Gate 2 — Consensus Confirmed' : 'Gate 2 — Awaiting Consensus' }}
                </div>
                <div class="gate-sub">
                  <template v-if="isDiscussed">
                    Board consensus recorded. Post-meeting pipeline is unlocked.
                  </template>
                  <template v-else>
                    Confirm board consensus in the Meeting Room to unlock the post-meeting pipeline.
                  </template>
                </div>
              </div>
              <button v-if="!isDiscussed" class="gate-action-btn" @click="router.push('/meeting')">
                Go to Meeting Room
                <span class="material-symbols-outlined" style="font-size:14px">arrow_forward</span>
              </button>
            </div>

            <!-- Agent section -->
            <div class="agent-section-header">
              <div class="agent-section-title">
                Post-Meeting Pipeline
                <Transition name="live-badge-tr">
                  <span v-if="runningCount > 0" class="live-badge-inline">
                    <span class="live-dot-sm" aria-hidden="true"></span>
                    LIVE
                  </span>
                </Transition>
              </div>

              <div class="header-right">
                <Transition name="progress-fade">
                  <div v-if="hasRun" class="progress-row">
                    <span class="progress-text">{{ completedCount }}/{{ postAgents.length }}</span>
                    <div
                      class="progress-track"
                      role="progressbar"
                      :aria-valuenow="progressPct"
                      aria-valuemin="0"
                      aria-valuemax="100"
                    >
                      <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
                    </div>
                  </div>
                </Transition>

                <button
                  class="run-btn"
                  :class="[pipelineStatus, { disabled: !canRunPipeline }]"
                  :disabled="isRunning || !canRunPipeline"
                  @click="startPipeline"
                >
                  <span v-if="isRunning" class="run-spinner" aria-hidden="true"></span>
                  <span v-else-if="!hasRun" class="material-symbols-outlined" style="font-size:18px">play_arrow</span>
                  <span v-else class="material-symbols-outlined" style="font-size:18px">refresh</span>

                  <span v-if="isRunning">Running…</span>
                  <span v-else-if="pipelineStatus === 'complete'">Re-run Pipeline</span>
                  <span v-else-if="pipelineStatus === 'error'">Retry Pipeline</span>
                  <span v-else-if="!isDiscussed">Awaiting Consensus</span>
                  <span v-else>Run Post-Meeting Pipeline</span>
                </button>
              </div>
            </div>

            <!-- Idle hint -->
            <Transition name="idle-hint">
              <div v-if="!hasRun" class="idle-hint">
                <span class="material-symbols-outlined idle-icon">task_alt</span>
                <div>
                  <div class="idle-title">{{ isDiscussed ? 'Ready to run' : 'Awaiting consensus' }}</div>
                  <div class="idle-sub">
                    {{ isDiscussed
                      ? 'Run the pipeline to draft the tumor board note, dispatch actions, and schedule follow-up.'
                      : 'Complete the meeting room discussion and confirm consensus to unlock this pipeline.' }}
                  </div>
                </div>
              </div>
            </Transition>

            <!-- Session-missing error (edge case: discussed but session lost) -->
            <div v-if="noSessionError" class="session-error">
              <span class="material-symbols-outlined" style="font-size:16px;color:#C5221F;flex-shrink:0">error</span>
              Meeting session not found. Return to the Meeting Room and end the meeting again to create the session record.
              <button class="gate-action-btn" style="background:#FCE8E6;color:#C5221F" @click="router.push('/meeting')">
                Meeting Room
              </button>
            </div>

            <!-- 4-agent grid -->
            <div class="agent-grid">
              <AgentCard
                v-for="(agent, i) in postAgents"
                :key="agent.name"
                v-bind="agent"
                :style="{ '--i': i }"
              />
            </div>

            <!-- Results panels — shown after pipeline completes -->
            <Transition name="results-fade">
              <div v-if="showResults" class="results-section">

                <CaseOutcome
                  v-if="outcomeRecommendation"
                  :patient="{
                    id: caseData.id,
                    name: caseData.name,
                    completedDate: completedDate,
                  }"
                  :recommendation="outcomeRecommendation"
                  :rationale="outcomeRationale ?? ''"
                />

                <ActionTrackerTable
                  v-if="dispatchedActions.length"
                  :actions="dispatchedActions"
                />

                <!-- FollowUpAgent card -->
                <div v-if="followUpData" class="follow-up-card">
                  <div class="fu-header">
                    <img src="/agents/13_followupagent.png" alt="FollowUpAgent" class="fu-icon" />
                    <div class="fu-title">Follow-Up Status</div>
                    <div class="fu-counts">
                      <span class="count-pill total">{{ followUpData.total_actions }} total</span>
                      <span class="count-pill done">{{ followUpData.completed_actions }} complete</span>
                      <span v-if="followUpData.overdue_actions?.length" class="count-pill overdue">
                        {{ followUpData.overdue_actions.length }} overdue
                      </span>
                    </div>
                  </div>
                  <div v-if="followUpData.overdue_actions?.length" class="overdue-list">
                    <div
                      v-for="item in followUpData.overdue_actions"
                      :key="item.action_id"
                      class="overdue-item"
                    >
                      <span class="material-symbols-outlined" style="font-size:14px;color:#EA4335;flex-shrink:0">warning</span>
                      <span class="overdue-desc">{{ item.description }}</span>
                      <span class="overdue-owner">{{ item.owner }}</span>
                      <span class="overdue-days">{{ item.days_overdue }}d overdue</span>
                    </div>
                  </div>
                  <div class="escalation-note">{{ followUpData.escalation_notes }}</div>
                </div>

                <!-- SchedulingAgent card -->
                <div v-if="schedulingData" class="scheduling-card">
                  <div class="sc-header">
                    <img src="/agents/14_schedulingagent.png" alt="SchedulingAgent" class="fu-icon" />
                    <div class="sc-title">Board Scheduling</div>
                    <div
                      class="representation-pill"
                      :class="schedulingData.needs_representation ? 'needs-repr' : 'no-repr'"
                    >
                      <span class="material-symbols-outlined" style="font-size:14px">
                        {{ schedulingData.needs_representation ? 'event' : 'check_circle' }}
                      </span>
                      {{ schedulingData.needs_representation
                        ? `Re-present in ${schedulingData.suggested_timeframe ?? 'TBD'}`
                        : 'No re-presentation required' }}
                    </div>
                  </div>
                  <div class="sc-rationale">{{ schedulingData.rationale }}</div>
                  <div v-if="schedulingData.blocking_items?.length" class="blocking-list">
                    <div class="blocking-label">Blocking items</div>
                    <div
                      v-for="(item, idx) in schedulingData.blocking_items"
                      :key="idx"
                      class="blocking-item"
                    >
                      <span class="material-symbols-outlined" style="font-size:13px;color:#FBBC04;flex-shrink:0">info</span>
                      {{ item }}
                    </div>
                  </div>
                </div>

                <NoteDraft
                  v-if="draftedNote"
                  :note="draftedNote"
                  @save="handleSaveNote"
                />

              </div>
            </Transition>

          </div>
        </template>

        <div v-else class="empty-state">
          <span class="material-symbols-outlined" style="font-size:48px;color:#DADCE0">pending_actions</span>
          <div class="empty-title">No case selected</div>
          <div class="empty-sub">Select a patient from the sidebar to view post-meeting details.</div>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.post-shell {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
  background: #F8F9FA;
}

/* ── Topbar ── */
.post-topbar {
  background: #fff;
  border-bottom: 1px solid #DADCE0;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  gap: 16px;
}

.topbar-left  { display: flex; align-items: center; gap: 10px; }
.topbar-right { display: flex; align-items: center; gap: 10px; flex: 1; justify-content: flex-end; }

.icon-btn {
  width: 36px; height: 36px; border-radius: 50%; border: none;
  background: transparent; cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: background 150ms;
}
.icon-btn:hover { background: #F8F9FA; }

.topbar-title { font-size: 16px; font-weight: 500; color: #202124; }

.live-badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 9px; border-radius: 999px;
  background: rgba(234,67,53,0.1); color: #D93025;
  font-size: 11px; font-weight: 700; letter-spacing: 0.6px;
}
.live-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #EA4335;
  animation: live-dot-blink 1.2s ease-in-out infinite;
}

.ticker-inner {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px;
}
.ticker-agent  { font-weight: 500; color: #174EA6; }
.ticker-sep    { color: #DADCE0; }
.ticker-detail { color: #5F6368; }
.ticker-cursor {
  display: inline-block; width: 1.5px; height: 11px;
  background: #1A73E8; margin-left: 1px; vertical-align: middle;
  animation: cursor-blink 1.1s step-end infinite;
}

/* ── Columns ── */
.columns { flex: 1; display: flex; overflow: hidden; }

/* ── Sidebar ── */
.sidebar {
  width: 260px; background: #F8F9FA; border-right: 1px solid #DADCE0;
  display: flex; flex-direction: column; flex-shrink: 0; overflow: auto;
}

.sidebar-header { padding: 16px 20px; background: #fff; border-bottom: 1px solid #DADCE0; flex-shrink: 0; }
.sidebar-title  { font-size: 14px; font-weight: 500; color: #202124; margin-bottom: 2px; }
.sidebar-sub    { font-size: 12px; color: #5F6368; }

.patient-list { padding: 12px; display: flex; flex-direction: column; gap: 6px; }

.patient-item {
  padding: 12px 14px; border-radius: 8px; background: #fff;
  cursor: pointer; border: 1px solid transparent; transition: background 150ms;
}
.patient-item:hover  { background: #E8EAED; }
.patient-item.active { background: #D2E3FC; border-color: #1A73E8; }

.patient-name {
  font-size: 14px; font-weight: 500; color: #202124;
  display: flex; align-items: center; margin-bottom: 4px;
}
.patient-name.active { color: #174EA6; }

.status-dot {
  width: 7px; height: 7px; border-radius: 50%; margin-right: 8px; flex-shrink: 0;
  background: #DADCE0; transition: background 300ms;
}
.status-dot.pending  { background: #FBBC04; }
.status-dot.ready    { background: #1A73E8; }
.status-dot.complete { background: #34A853; }

.patient-id { font-family: 'Roboto Mono', monospace; font-size: 11px; color: #5F6368; margin-bottom: 6px; padding-left: 15px; }

.status-chip { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 500; margin-left: 15px; }
.status-chip.pending  { background: #FEF7E0; color: #B06000; }
.status-chip.ready    { background: #D2E3FC; color: #174EA6; }
.status-chip.complete { background: #E6F4EA; color: #188038; }

/* ── Main ── */
.main-content { flex: 1; overflow: auto; display: flex; flex-direction: column; }

.empty-state {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 12px; text-align: center; padding: 60px 0;
}
.empty-title { font-size: 16px; font-weight: 500; color: #5F6368; }
.empty-sub   { font-size: 14px; color: #80868B; max-width: 280px; }

.case-topbar {
  background: #fff; border-bottom: 1px solid #DADCE0;
  padding-right: 16px; flex-shrink: 0;
}

.container { max-width: 1280px; margin: 0 auto; padding: 20px 24px 40px; }

/* ── Gate banner ── */
.gate-banner {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 20px; border-radius: 12px;
  margin-bottom: 24px; border: 1.5px solid;
}

.gate-banner.gate-locked {
  background: #FEF7E0; border-color: #FBBC04;
}

.gate-banner.gate-open {
  background: #E6F4EA; border-color: #34A853;
}

.gate-icon {
  font-size: 22px; flex-shrink: 0;
}
.gate-banner.gate-locked .gate-icon { color: #B06000; }
.gate-banner.gate-open   .gate-icon { color: #188038; }

.gate-text { flex: 1; min-width: 0; }
.gate-label { font-size: 13px; font-weight: 600; color: #202124; margin-bottom: 2px; }
.gate-sub   { font-size: 12px; color: #5F6368; }

.gate-action-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 14px; border-radius: 999px;
  background: #FBBC04; color: #202124; border: none;
  font-size: 12px; font-weight: 500; cursor: pointer;
  font-family: 'Roboto', sans-serif; transition: background 150ms; white-space: nowrap;
}
.gate-action-btn:hover { background: #f7b400; }

/* ── Agent section header ── */
.agent-section-header {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 12px; margin-bottom: 16px;
}

.agent-section-title {
  font-size: 20px; font-weight: 500; color: #202124;
  display: flex; align-items: center; gap: 10px;
}

.live-badge-inline {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 9px; border-radius: 999px;
  background: rgba(234,67,53,0.1); color: #D93025;
  font-size: 11px; font-weight: 700; letter-spacing: 0.6px;
}
.live-dot-sm {
  width: 6px; height: 6px; border-radius: 50%; background: #EA4335;
  animation: live-dot-blink 1.2s ease-in-out infinite;
}

.header-right { display: flex; align-items: center; gap: 14px; }

/* Progress */
.progress-row { display: flex; align-items: center; gap: 8px; }
.progress-text { font-size: 12px; color: #5F6368; white-space: nowrap; font-family: 'Roboto Mono', monospace; }
.progress-track { width: 100px; height: 4px; background: #E8EAED; border-radius: 999px; overflow: hidden; }
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #1A73E8, #34A853);
  border-radius: 999px;
  transition: width 600ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* Run button */
.run-btn {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 8px 18px; border-radius: 999px; border: none;
  font-size: 14px; font-weight: 500; cursor: pointer;
  font-family: 'Roboto', sans-serif;
  transition: background 150ms, box-shadow 150ms, opacity 150ms;
  white-space: nowrap;
}

.run-btn.idle:not(.disabled) {
  background: #1A73E8; color: #fff;
  box-shadow: 0 1px 3px rgba(26,115,232,0.35);
}
.run-btn.idle:not(.disabled):hover { background: #1765CC; }

.run-btn.running {
  background: #D2E3FC; color: #174EA6; cursor: not-allowed; opacity: 0.85;
}

.run-btn.complete:not(.disabled) {
  background: #E6F4EA; color: #137333;
}
.run-btn.complete:not(.disabled):hover { background: #CEEAD6; }

.run-btn.error:not(.disabled) {
  background: #FCE8E6; color: #C5221F;
}
.run-btn.error:not(.disabled):hover { background: #F5C6C2; }

.run-btn.disabled, .run-btn:disabled:not(.running) {
  background: #F1F3F4; color: #9AA0A6; cursor: not-allowed;
}

.run-spinner {
  width: 16px; height: 16px;
  border: 2px solid rgba(23, 78, 166, 0.25); border-top-color: #174EA6;
  border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0;
}

/* Idle hint */
.idle-hint {
  display: flex; align-items: center; gap: 16px;
  background: #fff; border: 1.5px dashed #DADCE0; border-radius: 12px;
  padding: 20px 24px; margin-bottom: 20px;
}
.idle-icon  { font-size: 28px; color: #BDC1C6; flex-shrink: 0; }
.idle-title { font-size: 14px; font-weight: 500; color: #202124; margin-bottom: 3px; }
.idle-sub   { font-size: 13px; color: #5F6368; }

/* Agent grid — 2×2 */
.agent-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}

.agent-grid > * {
  animation: card-slide-in 280ms cubic-bezier(0, 0, 0.2, 1) both;
  animation-delay: calc(var(--i, 0) * 55ms);
}

/* Results section */
.results-section { display: flex; flex-direction: column; gap: 16px; }

/* FollowUp card */
.follow-up-card {
  background: #fff; border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 1px 3px rgba(60,64,67,0.08);
  border-left: 3px solid #1A73E8;
}

.fu-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 14px; flex-wrap: wrap;
}

.fu-icon { width: 28px; height: 28px; object-fit: contain; border-radius: 6px; flex-shrink: 0; }

.fu-title  { font-size: 15px; font-weight: 500; color: #202124; flex: 1; min-width: 0; }

.fu-counts { display: flex; gap: 6px; flex-wrap: wrap; }

.count-pill {
  padding: 2px 9px; border-radius: 999px; font-size: 11px; font-weight: 500;
}
.count-pill.total  { background: #F1F3F4; color: #3C4043; }
.count-pill.done   { background: #E6F4EA; color: #188038; }
.count-pill.overdue{ background: #FCE8E6; color: #C5221F; }

.overdue-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }

.overdue-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; background: #FFF8F7; border-radius: 8px;
  border: 1px solid rgba(234,67,53,0.15); font-size: 12px;
}
.overdue-desc  { flex: 1; color: #202124; }
.overdue-owner { color: #5F6368; white-space: nowrap; }
.overdue-days  { color: #EA4335; font-weight: 500; white-space: nowrap; font-family: 'Roboto Mono', monospace; font-size: 11px; }

.escalation-note {
  font-size: 13px; color: #202124; line-height: 1.6;
  padding-top: 8px; border-top: 1px solid #F1F3F4;
}

/* Scheduling card */
.scheduling-card {
  background: #fff; border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 1px 3px rgba(60,64,67,0.08);
  border-left: 3px solid #FBBC04;
}

.sc-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap;
}

.sc-title { font-size: 15px; font-weight: 500; color: #202124; flex: 1; min-width: 0; }

.representation-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 12px; border-radius: 999px;
  font-size: 12px; font-weight: 500;
}
.representation-pill.needs-repr { background: #FEF7E0; color: #B06000; }
.representation-pill.no-repr    { background: #E6F4EA; color: #188038; }

.sc-rationale {
  font-size: 13px; color: #202124; line-height: 1.6; margin-bottom: 12px;
}

.blocking-list { display: flex; flex-direction: column; gap: 5px; }
.blocking-label { font-size: 11px; font-weight: 600; color: #9AA0A6; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.blocking-item {
  display: flex; align-items: flex-start; gap: 7px;
  font-size: 12px; color: #3C4043; line-height: 1.5;
}

/* Session error */
.session-error {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 16px; background: #FCE8E6; border-radius: 8px;
  font-size: 13px; color: #C5221F; margin-bottom: 16px;
  border: 1px solid rgba(234,67,53,0.2);
}

/* ── Transitions ── */
.live-badge-tr-enter-active,
.live-badge-tr-leave-active { transition: opacity 250ms, transform 250ms; }
.live-badge-tr-enter-from,
.live-badge-tr-leave-to     { opacity: 0; transform: scale(0.85); }

.progress-fade-enter-active,
.progress-fade-leave-active { transition: opacity 250ms; }
.progress-fade-enter-from,
.progress-fade-leave-to     { opacity: 0; }

.idle-hint-enter-active,
.idle-hint-leave-active { transition: opacity 200ms, transform 200ms; }
.idle-hint-enter-from,
.idle-hint-leave-to     { opacity: 0; transform: translateY(-6px); }

.results-fade-enter-active { transition: opacity 350ms, transform 350ms; }
.results-fade-enter-from   { opacity: 0; transform: translateY(12px); }

/* ── Keyframes ── */
@keyframes card-slide-in {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes live-dot-blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.15; }
}
@keyframes cursor-blink {
  0%,  49% { opacity: 1; }
  50%, 100% { opacity: 0; }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
