<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import PatientSelector from '../components/PatientSelector.vue'
import CaseDisplay from '../components/CaseDisplay.vue'
import LiveTranscriptPanel from '../components/LiveTranscriptPanel.vue'

const router = useRouter()

const patients = [
  { id: 'PT-2024-08471', name: 'Sarah Mitchell', status: 'active' },
  { id: 'PT-2024-08469', name: 'Maria Rodriguez', status: 'pending' },
  { id: 'PT-2024-08455', name: 'Jennifer Lee', status: 'pending' },
  { id: 'PT-2024-08442', name: 'Patricia Johnson', status: 'complete' },
]

const activePatientId = ref('PT-2024-08471')

const caseData = {
  id: 'PT-2024-08471',
  name: 'Sarah Mitchell',
  age: '52',
  stage: 'Stage IIB',
  receptors: 'ER+/PR+/HER2-',
  diagnosis: 'Grade 2 invasive ductal carcinoma, left breast',
  presentation: '2.1cm irregular mass at 10:00 position with suspicious microcalcifications. Palpable axillary lymphadenopathy.',
  previousTreatment: 'Lumpectomy with sentinel lymph node biopsy performed 2024-04-20. Margins clear. 1/3 sentinel nodes positive for metastatic disease.',
  radiology: 'Mammography shows BI-RADS 4 lesion with irregular margins and associated architectural distortion. MRI confirms single 2.1cm enhancing mass with no additional suspicious lesions. Axillary ultrasound demonstrates enlarged lymph node measuring 1.8cm with loss of fatty hilum.',
  pathology: 'Invasive ductal carcinoma, grade 2 (tubule formation 2, nuclear pleomorphism 2, mitotic count 2). Tumor size 2.1cm. ER positive (90% strong nuclear staining), PR positive (70% moderate-strong nuclear staining), HER2 IHC 1+ (negative). Ki-67 proliferation index 22%. Lymphovascular invasion not identified. Sentinel lymph node 1/3 positive, largest deposit 0.8cm with extranodal extension.',
  guidelines: 'Per NCCN Guidelines for Breast Cancer, node-positive hormone receptor-positive, HER2-negative disease with intermediate-high risk features warrants consideration of adjuvant chemotherapy followed by endocrine therapy. Oncotype DX recurrence score could provide additional prognostic information but may not change management given node-positive status. Recommended regimen: TC (docetaxel + cyclophosphamide) × 4 cycles followed by tamoxifen or aromatase inhibitor for 5-10 years. Consider ovarian suppression if premenopausal.',
  trials: 'NCT05234567: Phase III trial comparing standard chemotherapy + endocrine therapy vs. endocrine therapy alone in intermediate-risk, node-positive HR+/HER2- breast cancer. Patient meets eligibility criteria (age 18-70, 1-3 positive nodes, ER+ ≥10%, HER2-). Currently enrolling at affiliated institution.',
}
</script>

<template>
  <div class="meeting-shell">

    <!-- Top bar -->
    <div class="meeting-topbar">
      <div class="topbar-left">
        <button class="icon-btn" title="Back to dashboard" @click="router.push('/')">
          <span class="material-symbols-outlined" style="font-size: 20px; color: #5F6368">arrow_back</span>
        </button>
        <span class="material-symbols-outlined brand-icon">ecg_heart</span>
        <span class="topbar-title">Meeting Room</span>
        <div class="live-chip">
          <span class="live-dot"></span>
          Live
        </div>
      </div>
      <div class="topbar-right">
        <button class="end-btn" @click="router.push('/post-meeting')">
          <span class="material-symbols-outlined" style="font-size: 16px">meeting_room</span>
          End Meeting
        </button>
      </div>
    </div>

    <!-- Three-column layout -->
    <div class="columns">
      <PatientSelector
        :patients="patients"
        :active-id="activePatientId"
        @select="activePatientId = $event"
      />
      <div class="main-content">
        <CaseDisplay :case-data="caseData" />
      </div>
      <LiveTranscriptPanel />
    </div>

  </div>
</template>

<style scoped>
.meeting-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: #F8F9FA;
}

/* Top bar */
.meeting-topbar {
  height: 52px;
  background: #fff;
  border-bottom: 1px solid #DADCE0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
  z-index: 10;
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

.icon-btn:hover {
  background: #F8F9FA;
}

.brand-icon {
  font-size: 20px;
  color: #1A73E8;
}

.topbar-title {
  font-size: 15px;
  font-weight: 500;
  color: #202124;
}

.live-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  background: #FCE8E6;
  color: #C5221F;
  font-size: 12px;
  font-weight: 500;
}

.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #EA4335;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.end-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border-radius: 999px;
  border: none;
  background: #EA4335;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: 'Roboto', sans-serif;
  transition: background 150ms;
}

.end-btn:hover {
  background: #c5221f;
}

/* Columns */
.columns {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.main-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #F8F9FA;
}
</style>
