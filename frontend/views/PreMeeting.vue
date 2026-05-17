<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import PatientHeader from '../components/PatientHeader.vue'
import AgentCard from '../components/AgentCard.vue'
import DataGapAlert from '../components/DataGapAlert.vue'
import PatientDatabase from '../components/PatientDatabase.vue'
import ClinicalChatPanel from '../components/ClinicalChatPanel.vue'
import { usePatientsStore } from '../src/stores/patients.js'
import { useAgentsStore } from '../src/stores/agents.js'

const patientsStore = usePatientsStore()
const agentsStore   = useAgentsStore()

const showDatabase  = ref(false)
const databaseFilter = ref(null)
const caseData      = ref(null)

// Reactive slice of the store — auto-updates as SSE events arrive
const agents = computed(() => agentsStore.getForPatient(patientsStore.activeId ?? ''))
const pipelineStatus = computed(() => agentsStore.getPipelineStatus(patientsStore.activeId ?? ''))
const rawData = computed(() => agentsStore.getAgentRawData(patientsStore.activeId ?? ''))
const verification = computed(() => agentsStore.getVerification(patientsStore.activeId ?? ''))

const completedCount = computed(() => agents.value.filter(a => a.status === 'complete').length)
const runningCount   = computed(() => agents.value.filter(a => a.status === 'running').length)
const progressPct    = computed(() =>
  agents.value.length ? (completedCount.value / agents.value.length) * 100 : 0
)

const isRunning = computed(() => pipelineStatus.value === 'running')
const hasRun    = computed(() => pipelineStatus.value !== 'idle')

onMounted(async () => {
  await patientsStore.loadPatients()
  await loadActive()
})

watch(() => patientsStore.activeId, loadActive)

async function loadActive() {
  const id = patientsStore.activeId
  if (!id) return
  caseData.value = await patientsStore.loadCaseData(id)
  agentsStore.initCase(id)
}

function startPipeline() {
  if (isRunning.value) return
  agentsStore.runPipeline(patientsStore.activeId)
}

function openDatabase(agentName = null) {
  databaseFilter.value = agentName
  showDatabase.value = true
}
function closeDatabase() {
  showDatabase.value = false
  databaseFilter.value = null
}

function handleVerify(agentName) {
  agentsStore.verifyAgent(patientsStore.activeId, agentName)
}
function handleUnverify(agentName) {
  agentsStore.unverifyAgent(patientsStore.activeId, agentName)
}
</script>

<template>
  <div class="pre-shell">

    <!-- Patient sidebar -->
    <div class="sidebar">
      <div class="sidebar-header">
        <div class="sidebar-title">Board Cases</div>
        <div class="sidebar-sub">{{ patientsStore.patients.length }} patients</div>
      </div>
      <div class="patient-list">
        <div
          v-for="p in patientsStore.patients"
          :key="p.id"
          class="patient-item"
          :class="{ active: p.id === patientsStore.activeId }"
          @click="patientsStore.setActive(p.id)"
        >
          <div class="patient-name" :class="{ active: p.id === patientsStore.activeId }">
            <span
              class="status-dot"
              :class="agentsStore.getPipelineStatus(p.id)"
            ></span>
            {{ p.name }}
          </div>
          <div class="patient-id">{{ p.id }}</div>
        </div>
      </div>
    </div>

    <!-- Main area -->
    <div class="main-content">
      <template v-if="caseData">
        <div class="case-topbar">
          <PatientHeader
            :patient-id="caseData.id"
            :name="caseData.name"
            :age="caseData.age"
            :stage="caseData.stage"
            :receptors="caseData.receptors"
          />
          <button class="view-data-btn" @click="openDatabase()">
            <span class="material-symbols-outlined" style="font-size:16px">table_view</span>
            View Data
          </button>
        </div>

        <div class="container">
          <template v-if="caseData.dataGaps?.length">
            <DataGapAlert
              v-for="(gap, idx) in caseData.dataGaps"
              :key="idx"
              :message="gap.message"
              :show-upload-button="true"
              @upload="openDatabase(null)"
            />
          </template>

          <div v-if="caseData.boardHistory" class="board-history">
            <div class="board-history-label">Board History</div>
            <div class="board-history-text">
              {{ caseData.boardHistory }}
              <button class="history-link" @click="openDatabase(null)">View full history</button>
            </div>
          </div>

          <!-- Agent section header with run button -->
          <div class="agent-section-header">
            <div class="agent-section-title">
              Agent Orchestration
              <Transition name="live-badge">
                <span v-if="runningCount > 0" class="live-badge">
                  <span class="live-dot" aria-hidden="true"></span>
                  LIVE
                </span>
              </Transition>
            </div>

            <div class="header-right">
              <Transition name="progress-fade">
                <div v-if="hasRun" class="progress-row">
                  <span class="progress-text">{{ completedCount }}/{{ agents.length }}</span>
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

              <!-- Run / Re-run button -->
              <button
                class="run-btn"
                :class="pipelineStatus"
                :disabled="isRunning"
                @click="startPipeline"
              >
                <!-- Spinner when running -->
                <span v-if="isRunning" class="run-spinner" aria-hidden="true"></span>
                <span v-else-if="!hasRun" class="material-symbols-outlined" style="font-size:18px">play_arrow</span>
                <span v-else class="material-symbols-outlined" style="font-size:18px">refresh</span>

                <span v-if="isRunning">Running…</span>
                <span v-else-if="pipelineStatus === 'complete'">Re-run Pipeline</span>
                <span v-else-if="pipelineStatus === 'error'">Retry Pipeline</span>
                <span v-else>Run Pre-Meeting Pipeline</span>
              </button>
            </div>
          </div>

          <!-- Idle prompt when pipeline hasn't run yet -->
          <Transition name="idle-hint">
            <div v-if="!hasRun" class="idle-hint">
              <span class="material-symbols-outlined idle-icon">smart_toy</span>
              <div>
                <div class="idle-title">Ready to run</div>
                <div class="idle-sub">Click "Run Pre-Meeting Pipeline" to start all 7 agents in parallel.</div>
              </div>
            </div>
          </Transition>

          <div class="agent-grid">
            <AgentCard
              v-for="(agent, i) in agents"
              :key="agent.name"
              v-bind="agent"
              :style="{ '--i': i }"
              :raw-data="rawData[agent.name] ?? null"
              :verified="!!verification[agent.name]?.verified"
              :verified-by="verification[agent.name]?.verifiedBy ?? null"
              :verified-ts="verification[agent.name]?.ts ?? null"
              :on-database-click="agent.status === 'complete' ? openDatabase : null"
              @database-click="openDatabase"
              @verify="handleVerify"
              @unverify="handleUnverify"
            />
          </div>
        </div>
      </template>

      <div v-else class="loading-state">
        <span class="material-symbols-outlined" style="font-size: 40px; color: #DADCE0">hourglass_empty</span>
        <div>Loading case data…</div>
      </div>
    </div>

  </div>

  <PatientDatabase
    v-if="showDatabase && caseData"
    :patient="{ id: caseData.id, name: caseData.name }"
    @close="closeDatabase"
  />

  <ClinicalChatPanel
    :case-id="patientsStore.activeId"
    :case-name="caseData?.name"
    phase="pre"
  />
</template>

<style scoped>
.pre-shell {
  display: flex;
  height: calc(100vh - 56px);
  overflow: hidden;
  background: #F8F9FA;
}

/* ── Sidebar ── */
.sidebar {
  width: 260px;
  background: #F8F9FA;
  border-right: 1px solid #DADCE0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: auto;
}

.sidebar-header {
  padding: 16px 20px;
  background: #fff;
  border-bottom: 1px solid #DADCE0;
  flex-shrink: 0;
}

.sidebar-title { font-size: 14px; font-weight: 500; color: #202124; margin-bottom: 2px; }
.sidebar-sub   { font-size: 12px; color: #5F6368; }

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
  background: #DADCE0;
  transition: background 300ms;
}
.status-dot.idle     { background: #DADCE0; }
.status-dot.running  { background: #1A73E8; animation: dot-pulse 1.4s ease-in-out infinite; }
.status-dot.complete { background: #34A853; }
.status-dot.error    { background: #EA4335; }

.patient-id { font-family: 'Roboto Mono', monospace; font-size: 11px; color: #5F6368; }

/* ── Main ── */
.main-content { flex: 1; overflow: auto; display: flex; flex-direction: column; }

.loading-state {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 12px; font-size: 14px; color: #80868B;
}

.case-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #DADCE0;
  background: #fff;
  padding-right: 16px;
  flex-shrink: 0;
}

.container { max-width: 1280px; margin: 0 auto; padding: 20px 24px; }

.board-history {
  background: #F8F9FA; padding: 16px 20px; border-radius: 12px;
  margin-bottom: 24px; border-left: 4px solid #1A73E8;
}
.board-history-label { font-size: 13px; font-weight: 500; color: #5F6368; margin-bottom: 8px; }
.board-history-text  { font-size: 14px; color: #202124; line-height: 1.5; }
.history-link {
  background: none; border: none; color: #1A73E8; cursor: pointer;
  font-size: 14px; font-weight: 500; padding: 0; margin-left: 4px;
  font-family: 'Roboto', sans-serif; text-decoration: underline;
}

.view-data-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 16px; border-radius: 999px; border: 1px solid #DADCE0;
  font-size: 13px; font-weight: 500; cursor: pointer;
  background: #fff; color: #202124; font-family: 'Roboto', sans-serif;
  white-space: nowrap; transition: background 150ms;
}
.view-data-btn:hover { background: #F8F9FA; }

/* ── Agent section header ── */
.agent-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.agent-section-title {
  font-size: 20px; font-weight: 500; color: #202124;
  display: flex; align-items: center; gap: 10px;
}

.header-right {
  display: flex; align-items: center; gap: 14px;
}

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

/* ── Progress ── */
.progress-row {
  display: flex; align-items: center; gap: 8px;
}
.progress-text {
  font-size: 12px; color: #5F6368; white-space: nowrap;
  font-family: 'Roboto Mono', monospace;
}
.progress-track {
  width: 100px; height: 4px; background: #E8EAED; border-radius: 999px; overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #1A73E8, #34A853);
  border-radius: 999px;
  transition: width 600ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Run button ── */
.run-btn {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 8px 18px; border-radius: 999px; border: none;
  font-size: 14px; font-weight: 500; cursor: pointer;
  font-family: 'Roboto', sans-serif;
  transition: background 150ms, box-shadow 150ms, opacity 150ms;
  white-space: nowrap;
}

/* Idle — filled primary */
.run-btn.idle {
  background: #1A73E8; color: #fff;
  box-shadow: 0 1px 3px rgba(26,115,232,0.35);
}
.run-btn.idle:hover { background: #1765CC; }

/* Running — tonal, disabled */
.run-btn.running {
  background: #D2E3FC; color: #174EA6; cursor: not-allowed; opacity: 0.85;
}

/* Complete — tonal */
.run-btn.complete {
  background: #E6F4EA; color: #137333;
}
.run-btn.complete:hover { background: #CEEAD6; }

/* Error — tonal red */
.run-btn.error {
  background: #FCE8E6; color: #C5221F;
}
.run-btn.error:hover { background: #F5C6C2; }

/* Spinner ring */
.run-spinner {
  width: 16px; height: 16px;
  border: 2px solid rgba(23, 78, 166, 0.25);
  border-top-color: #174EA6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

/* ── Idle hint ── */
.idle-hint {
  display: flex; align-items: center; gap: 16px;
  background: #fff; border: 1.5px dashed #DADCE0; border-radius: 12px;
  padding: 20px 24px; margin-bottom: 20px;
}
.idle-icon { font-size: 28px; color: #BDC1C6; flex-shrink: 0; }
.idle-title { font-size: 14px; font-weight: 500; color: #202124; margin-bottom: 3px; }
.idle-sub   { font-size: 13px; color: #5F6368; }

/* ── Agent grid ── */
.agent-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}

.agent-grid > *:last-child {
  grid-column: 1 / -1;
}

.agent-grid > * {
  animation: card-slide-in 280ms cubic-bezier(0, 0, 0.2, 1) both;
  animation-delay: calc(var(--i, 0) * 55ms);
}

/* ── Transitions ── */
.live-badge-enter-active,
.live-badge-leave-active { transition: opacity 250ms, transform 250ms; }
.live-badge-enter-from,
.live-badge-leave-to     { opacity: 0; transform: scale(0.85); }

.progress-fade-enter-active,
.progress-fade-leave-active { transition: opacity 250ms; }
.progress-fade-enter-from,
.progress-fade-leave-to     { opacity: 0; }

.idle-hint-enter-active,
.idle-hint-leave-active { transition: opacity 200ms, transform 200ms; }
.idle-hint-enter-from,
.idle-hint-leave-to     { opacity: 0; transform: translateY(-6px); }

/* ── Keyframes ── */
@keyframes card-slide-in {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0);    }
}
@keyframes live-dot-blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.15; }
}
@keyframes dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.5; transform: scale(1.4); }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
