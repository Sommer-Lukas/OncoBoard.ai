<script setup>
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePatientsStore } from '../src/stores/patients.js'
import { useAgentsStore } from '../src/stores/agents.js'

const router = useRouter()
const store = usePatientsStore()
const agentsStore = useAgentsStore()

onMounted(async () => {
  await store.loadPatients()
  await Promise.all(store.patients.map(p => agentsStore.loadAgents(p.id)))
})

const today = new Intl.DateTimeFormat('en-US', {
  weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
}).format(new Date())

const phases = [
  { key: 'pre',     label: 'Pre-Meeting',  icon: 'checklist', route: '/pre-meeting',  status: 'complete', statusLabel: 'Ready'       },
  { key: 'meeting', label: 'Meeting Room', icon: 'groups',    route: '/meeting',       status: 'active',   statusLabel: 'In Progress' },
  { key: 'post',    label: 'Post-Meeting', icon: 'task_alt',  route: '/post-meeting',  status: 'pending',  statusLabel: 'Pending'     },
]

const SUBTYPES = [
  { label: 'All',             value: null },
  { label: 'Luminal A',       value: 'Luminal A' },
  { label: 'Luminal B',       value: 'Luminal B' },
  { label: 'HER2-enriched',   value: 'HER2-enriched' },
  { label: 'Triple Negative', value: 'Triple Negative' },
]

function setSubtype(value) {
  store.subtypeFilter = value
  store.activeId = null
  store.loadPatients()
}

function agentsFor(id)    { return agentsStore.getForPatient(id) }
function completedFor(id) { return agentsFor(id).filter(a => a.status === 'complete').length }
function runningFor(id)   { return agentsFor(id).filter(a => a.status === 'running').length }
function runningAgent(id) { return agentsFor(id).find(a => a.status === 'running') }

function go(patientId, route) {
  store.setActive(patientId)
  router.push(route)
}

// First running agent across all cases — drives the ticker
const liveAgent = computed(() => {
  for (const p of store.patients) {
    const agent = runningAgent(p.id)
    if (agent) return { agent: agent.name, patient: p.name }
  }
  return null
})
</script>

<template>
  <div class="dashboard">

    <!-- ── Header ── -->
    <header class="session-header">
      <div class="header-inner">

        <div class="header-left">
          <h1 class="session-title">Tumor Board</h1>
          <p class="session-date">{{ today }}</p>
          <div class="session-meta">
            <span v-if="agentsStore.runningCount > 0" class="meta-dot"></span>
            <span class="meta-text">
              {{ store.patients.length }} cases
              &nbsp;·&nbsp;
              {{ agentsStore.runningCount > 0
                  ? agentsStore.runningCount + ' agent' + (agentsStore.runningCount !== 1 ? 's' : '') + ' running'
                  : 'All agents ready' }}
            </span>
          </div>
        </div>

        <!-- Phase flow -->
        <nav class="phase-flow" aria-label="Board workflow">
          <template v-for="(phase, i) in phases" :key="phase.key">
            <button class="phase-stop" :class="phase.status" @click="router.push(phase.route)">
              <div class="phase-dot-wrap">
                <div v-if="phase.status === 'active'" class="phase-pulse-ring" aria-hidden="true"></div>
                <div class="phase-dot">
                  <span class="material-symbols-outlined" style="font-size:17px">{{ phase.icon }}</span>
                </div>
              </div>
              <div class="phase-label-group">
                <span class="phase-name">{{ phase.label }}</span>
                <span class="phase-status">{{ phase.statusLabel }}</span>
              </div>
            </button>
            <div
              v-if="i < phases.length - 1"
              class="phase-track"
              :class="phase.status"
              aria-hidden="true"
            ></div>
          </template>
        </nav>

      </div>

      <!-- Live activity ticker — only when agents are running -->
      <Transition name="ticker-fade">
        <div v-if="liveAgent" class="activity-ticker">
          <div class="ticker-inner">
            <span class="ticker-live">Live</span>
            <span class="ticker-agent">{{ liveAgent.agent }}</span>
            <span class="ticker-sep" aria-hidden="true">·</span>
            <span class="ticker-detail">Processing case for {{ liveAgent.patient }}</span>
            <span class="ticker-cursor" aria-hidden="true"></span>
          </div>
        </div>
      </Transition>
    </header>

    <!-- ── Body ── -->
    <div class="body">
      <div class="body-inner">

        <div class="filter-bar">
          <button
            v-for="s in SUBTYPES"
            :key="s.label"
            class="subtype-chip"
            :class="{ active: store.subtypeFilter === s.value }"
            @click="setSubtype(s.value)"
          >{{ s.label }}</button>
          <span class="filter-count">{{ store.patients.length }} cases</span>
        </div>

        <div v-if="store.loading" class="empty-state">Loading cases…</div>
        <div v-else-if="store.error" class="empty-state is-error">{{ store.error }}</div>

        <div v-else class="case-list">
          <div
            v-for="patient in store.patients"
            :key="patient.id"
            class="case-card"
            :class="`is-${patient.boardStatus}`"
            @click="go(patient.id, '/pre-meeting')"
          >
            <div class="case-body">

              <div class="case-row">
                <div class="case-avatar">
                  <span class="material-symbols-outlined" style="font-size:18px">person</span>
                </div>
                <div class="case-identity">
                  <span class="case-name">{{ patient.name }}</span>
                  <span class="case-id">{{ patient.id }}</span>
                </div>
                <div class="case-chips">
                  <span class="chip">{{ patient.age }}y</span>
                  <span class="chip">{{ patient.stage }}</span>
                  <span class="chip is-mono">{{ patient.receptors }}</span>
                </div>
                <span class="status-pill" :class="`is-${patient.boardStatus}`">{{ patient.boardStatus }}</span>
              </div>

              <p class="case-dx">{{ patient.diagnosis }}</p>

              <div class="agent-strip" v-if="agentsFor(patient.id).length">
                <div class="agent-nodes">
                  <div
                    v-for="agent in agentsFor(patient.id)"
                    :key="agent.name"
                    class="a-node"
                    :class="`is-${agent.status}`"
                    :title="`${agent.name} — ${agent.status}`"
                  >
                    <div v-if="agent.status === 'running'" class="a-ring" aria-hidden="true"></div>
                    <span class="material-symbols-outlined" style="font-size:11px;position:relative;z-index:1">{{ agent.icon }}</span>
                  </div>
                </div>
                <span class="agent-readout">
                  {{ completedFor(patient.id) }}/{{ agentsFor(patient.id).length }} ready
                  <template v-if="runningFor(patient.id) > 0">
                    &thinsp;·&thinsp;<span class="readout-live">{{ runningAgent(patient.id)?.name }} running</span>
                  </template>
                </span>
              </div>
            </div>

            <!-- Vertical action rail -->
            <div class="case-rail">
              <button class="rail-btn" @click.stop="go(patient.id, '/pre-meeting')">
                <span class="material-symbols-outlined" style="font-size:14px">checklist</span>
                Pre-Meeting
              </button>
              <button class="rail-btn" @click.stop="go(patient.id, '/post-meeting')">
                <span class="material-symbols-outlined" style="font-size:14px">task_alt</span>
                Post-Meeting
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>

  </div>
</template>

<style scoped>
/* ── Shell ── */
.dashboard {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 56px);
  background: #F8F9FA;
}

/* ── Session header ── */
.session-header {
  background: #fff;
  border-bottom: 1px solid #DADCE0;
  flex-shrink: 0;
}

.header-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 28px 32px 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 40px;
  flex-wrap: wrap;
}

.session-title {
  font-size: 26px;
  font-weight: 400;
  color: #202124;
  letter-spacing: -0.4px;
  margin: 0 0 4px;
  line-height: 1.2;
}

.session-date {
  font-size: 12px;
  color: #9AA0A6;
  margin: 0 0 10px;
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.meta-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #1A73E8;
  flex-shrink: 0;
  animation: dot-pulse 1.6s ease-in-out infinite;
}

.meta-text { color: #5F6368; }

/* Phase flow */
.phase-flow {
  display: flex;
  align-items: center;
  padding: 0;
  background: none;
  border: none;
}

.phase-stop {
  display: flex;
  align-items: center;
  gap: 10px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 12px;
  font-family: 'Roboto', sans-serif;
  transition: background 120ms;
}
.phase-stop:hover { background: #F8F9FA; }

.phase-dot-wrap {
  position: relative;
  width: 40px; height: 40px;
  flex-shrink: 0;
}

.phase-pulse-ring {
  position: absolute;
  inset: -6px;
  border: 2px solid rgba(26,115,232,0.28);
  border-radius: 50%;
  animation: phase-ring-expand 2s ease-out infinite;
  pointer-events: none;
}

.phase-dot {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid #DADCE0;
  display: flex; align-items: center; justify-content: center;
  color: #DADCE0;
  transition: background 200ms, border-color 200ms, color 200ms;
}

.phase-stop.pending .phase-dot { border-style: dashed; }

.phase-stop.complete .phase-dot {
  border-color: #34A853;
  background: #E6F4EA;
  color: #34A853;
}

.phase-stop.active .phase-dot {
  border-color: #1A73E8;
  background: #D2E3FC;
  color: #1A73E8;
}

.phase-label-group {
  display: flex;
  flex-direction: column;
  text-align: left;
  gap: 2px;
}

.phase-name {
  font-size: 13px;
  font-weight: 500;
  color: #202124;
}

.phase-status {
  font-size: 11px;
  color: #9AA0A6;
}
.phase-stop.complete .phase-status { color: #34A853; }
.phase-stop.active   .phase-status { color: #1A73E8; }

.phase-track {
  height: 2px;
  width: 48px;
  border-radius: 1px;
  flex-shrink: 0;
  margin: 0 2px;
  transition: background 400ms;
}
.phase-track.complete { background: #34A853; }
.phase-track.active   { background: linear-gradient(90deg, #1A73E8, #E8EAED); }
.phase-track.pending  { background: #E8EAED; }

/* Activity ticker */
.activity-ticker {
  background: rgba(26,115,232,0.035);
  border-top: 1px solid rgba(26,115,232,0.1);
  padding: 7px 0;
}

.ticker-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 32px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.ticker-live {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: #1A73E8;
  background: rgba(26,115,232,0.1);
  padding: 2px 7px;
  border-radius: 999px;
  flex-shrink: 0;
}

.ticker-agent {
  font-weight: 500;
  color: #174EA6;
  flex-shrink: 0;
}

.ticker-sep { color: #DADCE0; }

.ticker-detail { color: #5F6368; }

.ticker-cursor {
  display: inline-block;
  width: 1.5px;
  height: 11px;
  background: #1A73E8;
  margin-left: 1px;
  vertical-align: middle;
  animation: cursor-blink 1.1s step-end infinite;
}

.ticker-fade-enter-active,
.ticker-fade-leave-active {
  transition: opacity 200ms, transform 200ms;
}
.ticker-fade-enter-from,
.ticker-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ── Body ── */
.body { flex: 1; overflow-y: auto; }

.body-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 20px 32px 40px;
}

/* Filter bar */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.subtype-chip {
  padding: 5px 14px; border-radius: 999px;
  font-size: 13px; font-weight: 500;
  border: 1px solid #DADCE0; background: #fff; color: #5F6368;
  cursor: pointer; font-family: 'Roboto', sans-serif; transition: all 120ms;
}
.subtype-chip:hover  { background: #F8F9FA; border-color: #BDC1C6; }
.subtype-chip.active { background: #D2E3FC; border-color: #1A73E8; color: #174EA6; }
.filter-count { margin-left: auto; font-size: 12px; color: #9AA0A6; }

.empty-state { font-size: 14px; color: #5F6368; padding: 24px 0; }
.empty-state.is-error { color: #D93025; }

/* ── Case list ── */
.case-list { display: flex; flex-direction: column; gap: 8px; }

.case-card {
  background: #fff;
  border-radius: 12px;
  /* thin border on all sides, thicker accent on left */
  border: 1px solid #EBEBEB;
  border-left-width: 3px;
  border-left-color: #DADCE0;
  box-shadow: 0 1px 2px rgba(60,64,67,0.07);
  display: flex;
  align-items: stretch;
  overflow: hidden;
  cursor: pointer;
  transition: box-shadow 130ms;
}
.case-card:hover {
  box-shadow: 0 2px 6px rgba(60,64,67,0.1), 0 4px 16px rgba(60,64,67,0.06);
}

.case-card.is-active   { border-left-color: #1A73E8; }
.case-card.is-complete { border-left-color: #34A853; }
.case-card.is-pending  { border-left-color: #FBBC04; }

.case-body { flex: 1; padding: 18px 20px; min-width: 0; }

.case-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.case-avatar {
  width: 34px; height: 34px;
  border-radius: 8px;
  background: #D2E3FC; color: #1A73E8;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}

.case-identity { flex: 1; min-width: 0; }
.case-name { font-size: 15px; font-weight: 500; color: #202124; display: block; }
.case-id   { font-family: 'Roboto Mono', monospace; font-size: 11px; color: #9AA0A6; display: block; margin-top: 1px; }

.case-chips { display: flex; gap: 5px; flex-wrap: wrap; }
.chip       { padding: 2px 9px; border-radius: 999px; font-size: 11px; background: #F1F3F4; color: #3C4043; }
.chip.is-mono { font-family: 'Roboto Mono', monospace; font-size: 10px; }

.status-pill {
  padding: 3px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 500; text-transform: capitalize; flex-shrink: 0;
}
.status-pill.is-active   { background: #D2E3FC; color: #174EA6; }
.status-pill.is-pending  { background: #FEF7E0; color: #B06000; }
.status-pill.is-complete { background: #E6F4EA; color: #188038; }

.case-dx {
  font-size: 13px; color: #5F6368;
  margin: 0 0 14px 46px;
  line-height: 1.5;
}

/* Inline agent status */
.agent-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: 46px;
}

.agent-nodes { display: flex; gap: 4px; }

.a-node {
  position: relative;
  width: 24px; height: 24px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.a-node.is-complete { background: #E6F4EA; color: #34A853; }
.a-node.is-running  { background: #D2E3FC; color: #1A73E8; }
.a-node.is-idle     { background: #F1F3F4; color: #C4C7CC; }
.a-node.is-error    { background: #FCE8E6; color: #EA4335; }

.a-ring {
  position: absolute;
  inset: -3px;
  border: 1.5px solid rgba(26,115,232,0.4);
  border-radius: 50%;
  animation: ring-expand 1.8s ease-out infinite;
  pointer-events: none;
}

.agent-readout { font-size: 11px; color: #9AA0A6; }
.readout-live  { color: #174EA6; font-weight: 500; }

/* Action rail */
.case-rail {
  display: flex;
  flex-direction: column;
  border-left: 1px solid #F1F3F4;
  flex-shrink: 0;
  min-width: 132px;
}

.rail-btn {
  flex: 1;
  display: flex; align-items: center; gap: 7px;
  padding: 0 18px;
  border: none; background: transparent;
  cursor: pointer;
  font-size: 12px; font-weight: 500; color: #5F6368;
  font-family: 'Roboto', sans-serif;
  transition: background 120ms, color 120ms;
  border-bottom: 1px solid #F1F3F4;
  white-space: nowrap;
}
.rail-btn:last-child { border-bottom: none; }
.rail-btn:hover { background: #F8F9FA; color: #1A73E8; }

/* ── Keyframes ── */
@keyframes dot-pulse {
  0%, 100% { transform: scale(1);   opacity: 1;   }
  50%       { transform: scale(1.5); opacity: 0.5; }
}

@keyframes phase-ring-expand {
  0%   { transform: scale(0.85); opacity: 0.7; }
  100% { transform: scale(1.5);  opacity: 0;   }
}

@keyframes ring-expand {
  0%   { transform: scale(1);   opacity: 0.6; }
  100% { transform: scale(1.9); opacity: 0;   }
}

@keyframes cursor-blink {
  0%,  49% { opacity: 1; }
  50%, 100% { opacity: 0; }
}
</style>
