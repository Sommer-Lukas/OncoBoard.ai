<script setup>
import { ref, watch, onMounted } from 'vue'
import PatientHeader from '../components/PatientHeader.vue'
import AgentCard from '../components/AgentCard.vue'
import DataGapAlert from '../components/DataGapAlert.vue'
import PatientDatabase from '../components/PatientDatabase.vue'
import { usePatientsStore } from '../src/stores/patients.js'
import { useAgentsStore } from '../src/stores/agents.js'

const patientsStore = usePatientsStore()
const agentsStore = useAgentsStore()

const showDatabase = ref(false)
const databaseFilter = ref(null)
const caseData = ref(null)
const agents = ref([])

onMounted(async () => {
  await patientsStore.loadPatients()
  await loadActive()
})

watch(() => patientsStore.activeId, loadActive)

async function loadActive() {
  const id = patientsStore.activeId
  if (!id) return
  caseData.value = await patientsStore.loadCaseData(id)
  await agentsStore.loadAgents(id)
  agents.value = agentsStore.getForPatient(id)
}

function openDatabase(agentName = null) {
  databaseFilter.value = agentName
  showDatabase.value = true
}

function closeDatabase() {
  showDatabase.value = false
  databaseFilter.value = null
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
            <span class="status-dot" :class="p.boardStatus"></span>
            {{ p.name }}
          </div>
          <div class="patient-id">{{ p.id }}</div>
        </div>
      </div>
    </div>

    <!-- Main area -->
    <div class="main-content">
      <template v-if="caseData">
        <div style="display:flex; align-items:center; justify-content:space-between; border-bottom: 1px solid #DADCE0; background:#fff; padding-right:16px; flex-shrink:0;">
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

          <div class="section-title">Agent Progress</div>
          <div class="agent-grid">
            <AgentCard
              v-for="agent in agents"
              :key="agent.name"
              v-bind="agent"
              :on-database-click="agent.status === 'complete' ? openDatabase : null"
              @database-click="openDatabase"
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
</template>

<style scoped>
.pre-shell {
  display: flex;
  height: calc(100vh - 56px);
  overflow: hidden;
  background: #F8F9FA;
}

/* Sidebar */
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
.patient-item:hover { background: #E8EAED; }
.patient-item.active { background: #D2E3FC; border-color: #1A73E8; }

.patient-name {
  font-size: 14px; font-weight: 500; color: #202124;
  display: flex; align-items: center; margin-bottom: 4px;
}
.patient-name.active { color: #174EA6; }

.status-dot {
  width: 7px; height: 7px; border-radius: 50%; margin-right: 8px; flex-shrink: 0;
}
.status-dot.active   { background: #34A853; }
.status-dot.pending  { background: #FBBC04; }
.status-dot.complete { background: #5F6368; }

.patient-id { font-family: 'Roboto Mono', monospace; font-size: 11px; color: #5F6368; }

/* Main */
.main-content { flex: 1; overflow: auto; display: flex; flex-direction: column; }

.loading-state {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 12px; font-size: 14px; color: #80868B;
}

.container { max-width: 1280px; margin: 0 auto; padding: 24px; }

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

.section-title { font-size: 20px; font-weight: 500; color: #202124; margin-bottom: 16px; }

.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}
</style>
