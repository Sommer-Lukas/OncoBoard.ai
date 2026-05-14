<script setup>
import { ref } from 'vue'
import PatientHeader from '../components/PatientHeader.vue'
import AgentCard from '../components/AgentCard.vue'
import DataGapAlert from '../components/DataGapAlert.vue'
import PatientDatabase from '../components/PatientDatabase.vue'

const showDatabase = ref(false)
const databaseFilter = ref(null)

const patient = {
  id: 'PT-2024-08471',
  name: 'Sarah Mitchell',
  age: '52',
  stage: 'Stage IIB',
  receptors: 'ER+/PR+/HER2-',
}

const agents = [
  {
    name: 'CaseCompiler',
    icon: 'folder_open',
    status: 'complete',
    timestamp: 'Completed 2 min ago',
    output: 'All records retrieved. Flagged: Missing CT chest from 2024-04-15.',
  },
  {
    name: 'SummaryAgent',
    icon: 'description',
    status: 'complete',
    timestamp: 'Completed 1 min ago',
    output: '52yo female, Stage IIB invasive ductal carcinoma. Prior lumpectomy + sentinel node biopsy. ER+/PR+/HER2-. Considering adjuvant chemotherapy vs endocrine therapy alone.',
  },
  {
    name: 'RadiologyAgent',
    icon: 'image',
    status: 'complete',
    timestamp: 'Completed 3 min ago',
    output: 'BI-RADS 4: 2.1cm irregular mass, left breast 10:00, suspicious microcalcifications. Enlarged axillary node 1.8cm.',
  },
  {
    name: 'PathologyAgent',
    icon: 'biotech',
    status: 'complete',
    timestamp: 'Completed 2 min ago',
    output: 'Grade 2 invasive ductal carcinoma. ER 90%, PR 70%, HER2 IHC 1+ (negative). Ki-67 22%. 1/3 sentinel nodes positive.',
  },
  {
    name: 'GuidelineAgent',
    icon: 'clinical_notes',
    status: 'complete',
    timestamp: 'Completed 1 min ago',
    output: 'NCCN match: Node-positive hormone receptor+ breast cancer. Recommends chemotherapy + endocrine therapy for intermediate-high risk.',
  },
  {
    name: 'TrialAgent',
    icon: 'science',
    status: 'running',
    timestamp: 'Running...',
    output: null,
  },
  {
    name: 'HistoryCaseAgent',
    icon: 'history',
    status: 'complete',
    timestamp: 'Completed 4 min ago',
    output: 'Found 3 analogous cases: Similar stage/receptor status. 2/3 received TC regimen + tamoxifen. Good outcomes (5yr DFS 87%).',
  },
]

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
  <PatientHeader
    :patient-id="patient.id"
    :name="patient.name"
    :age="patient.age"
    :stage="patient.stage"
    :receptors="patient.receptors"
  />

  <div class="container">
    <DataGapAlert
      message="CT chest from 2024-04-15 not found in system. Contact radiology to upload before meeting."
      :show-upload-button="true"
      @upload="openDatabase(null)"
    />

    <div class="board-history">
      <div class="board-history-label">Board History</div>
      <div class="board-history-text">
        Previous board (March 15, 2024) recommended lumpectomy with SLNB. Completed April 20, 2024.
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

  <PatientDatabase
    v-if="showDatabase"
    :patient="{ id: patient.id, name: patient.name }"
    :filter-agent="databaseFilter"
    @close="closeDatabase"
  />
</template>

<style scoped>
.container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px;
}

.board-history {
  background: #F8F9FA;
  padding: 16px 20px;
  border-radius: 12px;
  margin-bottom: 24px;
  border-left: 4px solid #1A73E8;
}

.board-history-label {
  font-size: 13px;
  font-weight: 500;
  color: #5F6368;
  margin-bottom: 8px;
}

.board-history-text {
  font-size: 14px;
  color: #202124;
  line-height: 1.5;
}

.history-link {
  background: none;
  border: none;
  color: #1A73E8;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  padding: 0;
  margin-left: 4px;
  font-family: 'Roboto', sans-serif;
  text-decoration: underline;
}

.section-title {
  font-size: 20px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 16px;
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}
</style>
