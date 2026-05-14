<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import CaseOutcome from '../components/CaseOutcome.vue'
import ActionTrackerTable from '../components/ActionTrackerTable.vue'
import NoteDraft from '../components/NoteDraft.vue'

const router = useRouter()

const activeId = ref('PT-2024-08471')

const patients = [
  { id: 'PT-2024-08471', name: 'Sarah Mitchell',   status: 'complete' },
  { id: 'PT-2024-08469', name: 'Maria Rodriguez',  status: 'complete' },
  { id: 'PT-2024-08455', name: 'Jennifer Lee',     status: 'complete' },
  { id: 'PT-2024-08442', name: 'Patricia Johnson', status: 'pending'  },
]

const statusColor = { complete: '#34A853', pending: '#FBBC04' }

const caseRecords = {
  'PT-2024-08471': {
    patient: { id: 'PT-2024-08471', name: 'Sarah Mitchell', completedDate: 'May 13, 2026 2:45 PM' },
    recommendation: 'Adjuvant chemotherapy (TC × 4 cycles) followed by endocrine therapy (tamoxifen × 5-10 years) and radiation therapy (whole breast + regional nodes).',
    rationale: 'Node-positive, hormone receptor-positive breast cancer with extranodal extension and intermediate-high Ki-67 (22%) indicates elevated recurrence risk. Standard of care per NCCN guidelines. Patient declined trial enrollment.',
    actions: [
      { description: 'Schedule chemotherapy planning appointment', owner: 'Dr. Chen',         dueDate: 'May 15, 2026', status: 'pending' },
      { description: 'Order baseline labs (CBC, CMP, LFTs)',       owner: 'Dr. Chen',         dueDate: 'May 16, 2026', status: 'pending' },
      { description: 'Radiation oncology consultation',            owner: 'Dr. Patel',        dueDate: 'May 20, 2026', status: 'pending' },
      { description: 'Discuss ovarian suppression options',        owner: 'Dr. Chen',         dueDate: 'May 22, 2026', status: 'pending' },
      { description: 'Send tumor board note to primary care',      owner: 'Medical Records',  dueDate: 'May 14, 2026', status: 'pending' },
    ],
    note: `TUMOR BOARD DISCUSSION
Patient: Sarah Mitchell (PT-2024-08471)
Date: May 13, 2026
Board Members: Dr. Chen (Medical Oncology), Dr. Patel (Radiation Oncology), Dr. Kim (Surgical Oncology), Dr. Rodriguez (Pathology), Dr. Lee (Radiology)

CLINICAL SUMMARY:
52-year-old female with Stage IIB invasive ductal carcinoma. ER+/PR+/HER2-. Post lumpectomy + SLNB. Grade 2, 2.1cm, margins clear, 1/3 nodes positive with extranodal extension. Ki-67 22%.

RECOMMENDATION:
TC chemotherapy × 4 cycles → tamoxifen × 5-10 years + whole breast radiation with regional nodal irradiation.`,
  },

  'PT-2024-08469': {
    patient: { id: 'PT-2024-08469', name: 'Maria Rodriguez', completedDate: 'May 13, 2026 3:10 PM' },
    recommendation: 'Neoadjuvant chemotherapy (AC-T regimen) followed by surgical reassessment. HER2-directed therapy not indicated.',
    rationale: 'Stage IIIA triple-negative breast cancer with bulky nodal disease. Neoadjuvant approach allows assessment of pathologic complete response and may improve surgical outcomes. BRCA1/2 testing ordered.',
    actions: [
      { description: 'BRCA1/2 genetic testing referral',                owner: 'Dr. Kim',     dueDate: 'May 16, 2026', status: 'pending' },
      { description: 'Port placement for chemotherapy',                  owner: 'Dr. Kim',     dueDate: 'May 17, 2026', status: 'pending' },
      { description: 'Baseline cardiac echo before anthracycline',       owner: 'Dr. Chen',   dueDate: 'May 18, 2026', status: 'pending' },
      { description: 'Send tumor board note to primary care',            owner: 'Medical Records', dueDate: 'May 14, 2026', status: 'pending' },
    ],
    note: `TUMOR BOARD DISCUSSION
Patient: Maria Rodriguez (PT-2024-08469)
Date: May 13, 2026
Board Members: Dr. Chen, Dr. Patel, Dr. Kim, Dr. Rodriguez, Dr. Lee

CLINICAL SUMMARY:
48-year-old female with Stage IIIA triple-negative invasive ductal carcinoma. ER-/PR-/HER2-. Biopsy-proven axillary nodal involvement. Ki-67 78%.

RECOMMENDATION:
Neoadjuvant AC-T chemotherapy. Reassess with MRI after 4 cycles. BRCA testing ordered. Surgical planning pending chemotherapy response.`,
  },

  'PT-2024-08455': {
    patient: { id: 'PT-2024-08455', name: 'Jennifer Lee', completedDate: 'May 13, 2026 3:35 PM' },
    recommendation: 'Active surveillance with 6-month follow-up imaging. Endocrine therapy (letrozole) to continue. No change in systemic therapy at this time.',
    rationale: 'Stable Stage I ER+/HER2- breast cancer on endocrine therapy. Low Oncotype DX recurrence score (RS 14) confirmed low risk. Imaging shows no progression. Board consensus for continued surveillance.',
    actions: [
      { description: 'Follow-up mammography in 6 months',          owner: 'Dr. Lee',          dueDate: 'Nov 13, 2026', status: 'pending' },
      { description: 'Bone density scan (DEXA) — annual',          owner: 'Dr. Chen',         dueDate: 'Jun 1, 2026',  status: 'pending' },
      { description: 'Confirm letrozole adherence at next visit',   owner: 'Dr. Chen',         dueDate: 'Jun 15, 2026', status: 'pending' },
    ],
    note: `TUMOR BOARD DISCUSSION
Patient: Jennifer Lee (PT-2024-08455)
Date: May 13, 2026
Board Members: Dr. Chen, Dr. Patel, Dr. Kim, Dr. Rodriguez, Dr. Lee

CLINICAL SUMMARY:
61-year-old female with Stage I ER+/PR+/HER2- invasive lobular carcinoma. Post lumpectomy 2023. Oncotype DX RS 14 (low risk). Currently on letrozole year 2.

RECOMMENDATION:
Continue letrozole. Surveillance imaging every 6 months. No additional systemic therapy indicated at this time.`,
  },

  'PT-2024-08442': {
    patient: { id: 'PT-2024-08442', name: 'Patricia Johnson', completedDate: null },
    recommendation: null,
    rationale: null,
    actions: [],
    note: '',
  },
}

const activeRecord = computed(() => caseRecords[activeId.value])
</script>

<template>
  <div class="post-shell">

    <!-- Top bar -->
    <div class="post-topbar">
      <div class="topbar-left">
        <button class="icon-btn" @click="router.push('/')">
          <span class="material-symbols-outlined" style="font-size: 20px; color: #5F6368">arrow_back</span>
        </button>
        <div class="topbar-title">Post-Meeting Summary</div>
        <div class="patient-count">{{ patients.filter(p => p.status === 'complete').length }}/{{ patients.length }} completed</div>
      </div>
      <button class="export-btn">
        <span class="material-symbols-outlined" style="font-size: 18px">download</span>
        Export All Notes
      </button>
    </div>

    <!-- Two-column layout -->
    <div class="columns">

      <!-- Patient sidebar -->
      <div class="sidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">Board Cases</div>
          <div class="sidebar-sub">{{ patients.length }} patients</div>
        </div>
        <div class="patient-list">
          <div
            v-for="p in patients"
            :key="p.id"
            class="patient-item"
            :class="{ active: p.id === activeId }"
            @click="activeId = p.id"
          >
            <div class="patient-name" :class="{ active: p.id === activeId }">
              <span class="status-dot" :style="{ background: statusColor[p.status] }"></span>
              {{ p.name }}
            </div>
            <div class="patient-id">{{ p.id }}</div>
            <div
              class="patient-status-chip"
              :class="p.status"
            >
              {{ p.status === 'complete' ? 'Done' : 'Pending' }}
            </div>
          </div>
        </div>
      </div>

      <!-- Main content -->
      <div class="main-content">

        <!-- Pending state -->
        <div v-if="!activeRecord.recommendation" class="pending-state">
          <span class="material-symbols-outlined" style="font-size: 48px; color: #DADCE0">pending</span>
          <div class="pending-title">Not yet discussed</div>
          <div class="pending-sub">{{ activeRecord.patient.name }} has not been reviewed by the board yet.</div>
        </div>

        <!-- Completed case -->
        <template v-else>
          <CaseOutcome
            :patient="activeRecord.patient"
            :recommendation="activeRecord.recommendation"
            :rationale="activeRecord.rationale"
          />
          <ActionTrackerTable :actions="activeRecord.actions" />
          <NoteDraft :note="activeRecord.note" @save="(v) => console.log('Note saved', v)" />
        </template>

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

/* Top bar */
.post-topbar {
  background: #fff;
  border-bottom: 1px solid #DADCE0;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 150ms;
}

.icon-btn:hover { background: #F8F9FA; }

.topbar-title {
  font-size: 16px;
  font-weight: 500;
  color: #202124;
}

.patient-count {
  font-size: 12px;
  color: #5F6368;
  background: #F8F9FA;
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 500;
}

.export-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 18px;
  border-radius: 999px;
  border: none;
  background: #1A73E8;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  font-family: 'Roboto', sans-serif;
  transition: background 150ms;
}

.export-btn:hover { background: #1557b0; }

/* Columns */
.columns {
  flex: 1;
  display: flex;
  overflow: hidden;
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

.sidebar-title {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 2px;
}

.sidebar-sub {
  font-size: 12px;
  color: #5F6368;
}

.patient-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.patient-item {
  padding: 12px 14px;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 150ms;
}

.patient-item:hover { background: #E8EAED; }

.patient-item.active {
  background: #D2E3FC;
  border-color: #1A73E8;
}

.patient-name {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.patient-name.active { color: #174EA6; }

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 8px;
  flex-shrink: 0;
}

.patient-id {
  font-family: 'Roboto Mono', monospace;
  font-size: 11px;
  color: #5F6368;
  margin-bottom: 6px;
  padding-left: 15px;
}

.patient-status-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  margin-left: 15px;
}

.patient-status-chip.complete { background: #E6F4EA; color: #188038; }
.patient-status-chip.pending  { background: #FEF7E0; color: #B06000; }

/* Main content */
.main-content {
  flex: 1;
  overflow: auto;
  padding: 24px;
}

/* Pending state */
.pending-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  padding: 60px 0;
}

.pending-title {
  font-size: 16px;
  font-weight: 500;
  color: #5F6368;
}

.pending-sub {
  font-size: 14px;
  color: #80868B;
  max-width: 280px;
}
</style>
