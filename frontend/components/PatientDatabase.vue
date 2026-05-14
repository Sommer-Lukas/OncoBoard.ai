<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  patient: { type: Object, required: true },
  filterAgent: { type: String, default: null },
})

defineEmits(['close'])

const activeTab = ref('records')

const allFiles = [
  { name: 'CT_Chest_2024-04-15.dcm', date: '2024-04-15', type: 'Imaging', agent: 'RadiologyAgent' },
  { name: 'MRI_Breast_2024-04-18.dcm', date: '2024-04-18', type: 'Imaging', agent: 'RadiologyAgent' },
  { name: 'Pathology_Report_2024-04-20.pdf', date: '2024-04-20', type: 'Pathology', agent: 'PathologyAgent' },
  { name: 'Genomic_Testing_2024-04-22.pdf', date: '2024-04-22', type: 'Genomics', agent: 'PathologyAgent' },
  { name: 'Lab_Results_2024-05-01.pdf', date: '2024-05-01', type: 'Labs', agent: 'CaseCompiler' },
  { name: 'NCCN_Guidelines_v2024.pdf', date: '2024-01-15', type: 'Reference', agent: 'GuidelineAgent' },
  { name: 'Trial_NCT05234567.pdf', date: '2024-05-10', type: 'Clinical Trial', agent: 'TrialAgent' },
  { name: 'Previous_Case_Summary.pdf', date: '2024-03-15', type: 'Board Notes', agent: 'HistoryCaseAgent' },
]

const displayedFiles = computed(() =>
  props.filterAgent ? allFiles.filter(f => f.agent === props.filterAgent) : allFiles
)

function fileIcon(type) {
  if (type === 'Imaging') return 'image'
  if (type === 'Pathology') return 'biotech'
  return 'description'
}
</script>

<template>
  <div class="overlay" @click="$emit('close')">
    <div class="modal" @click.stop>
      <div class="modal-header">
        <div>
          <div class="modal-title">
            Patient Database: {{ patient.name }}
            <span v-if="filterAgent" class="filter-label">• {{ filterAgent }}</span>
          </div>
          <div class="modal-subtitle">
            {{ patient.id }}
            <template v-if="filterAgent">
              • Showing {{ displayedFiles.length }} {{ filterAgent }} file{{ displayedFiles.length !== 1 ? 's' : '' }}
            </template>
          </div>
        </div>
        <button class="close-btn" @click="$emit('close')">
          <span class="material-symbols-outlined" style="font-size: 20px; color: #5F6368">close</span>
        </button>
      </div>

      <div class="tabs">
        <button
          v-for="tab in ['records', 'history', 'upload']"
          :key="tab"
          class="tab"
          :class="{ active: activeTab === tab }"
          @click="activeTab = tab"
        >
          {{ tab === 'records' ? 'Medical Records' : tab === 'history' ? 'Board History' : 'Upload Files' }}
        </button>
      </div>

      <div class="modal-body">
        <!-- Records Tab -->
        <template v-if="activeTab === 'records'">
          <div class="file-list">
            <div v-for="(file, idx) in displayedFiles" :key="idx" class="file-item">
              <div class="file-icon">
                <span class="material-symbols-outlined" style="font-size: 18px; color: #5F6368">{{ fileIcon(file.type) }}</span>
              </div>
              <div class="file-info">
                <div class="file-name">{{ file.name }}</div>
                <div class="file-meta">{{ file.type }} • Uploaded {{ file.date }}</div>
              </div>
              <button class="icon-btn">
                <span class="material-symbols-outlined" style="font-size: 18px; color: #5F6368">download</span>
              </button>
            </div>
          </div>
        </template>

        <!-- History Tab -->
        <template v-else-if="activeTab === 'history'">
          <div class="history-entry">
            <div class="history-label">Previous Tumor Board • March 15, 2024</div>
            <div><strong>Decision:</strong> Lumpectomy with sentinel lymph node biopsy recommended.</div>
            <div><strong>Outcome:</strong> Procedure completed April 20, 2024. Pathology confirmed IDC with 1/3 nodes positive.</div>
          </div>
          <div class="history-entry current">
            <div class="history-label current-label">Current Board • Scheduled May 13, 2026</div>
            <div><strong>Discussion Focus:</strong> Adjuvant therapy planning post-surgery. Chemotherapy vs endocrine therapy decision.</div>
          </div>
        </template>

        <!-- Upload Tab -->
        <template v-else-if="activeTab === 'upload'">
          <div class="upload-zone">
            <span class="material-symbols-outlined" style="font-size: 48px; color: #5F6368; margin-bottom: 12px; display: block">upload_file</span>
            <div class="upload-title">Drop files here or click to browse</div>
            <div class="upload-hint">Accepted: PDF, DICOM, JPEG, PNG (max 50MB)</div>
          </div>
          <div class="upload-note">
            All uploads are automatically linked to patient {{ patient.id }} and timestamped.
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

.modal {
  background: #fff;
  border-radius: 16px;
  width: 100%;
  max-width: 900px;
  max-height: 90vh;
  box-shadow: 0 8px 16px rgba(60, 64, 67, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  padding: 24px;
  border-bottom: 1px solid #E8EAED;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-title {
  font-size: 20px;
  font-weight: 500;
  color: #202124;
}

.filter-label {
  font-size: 14px;
  font-weight: 400;
  color: #5F6368;
  margin-left: 12px;
}

.modal-subtitle {
  font-size: 13px;
  color: #5F6368;
  margin-top: 4px;
}

.close-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: #F8F9FA;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: #E8EAED;
}

.tabs {
  display: flex;
  border-bottom: 1px solid #E8EAED;
  padding: 0 24px;
}

.tab {
  padding: 12px 20px;
  font-size: 14px;
  font-weight: 500;
  color: #5F6368;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  margin-bottom: -1px;
  font-family: 'Roboto', sans-serif;
}

.tab.active {
  color: #1A73E8;
  border-bottom-color: #1A73E8;
}

.modal-body {
  flex: 1;
  overflow: auto;
  padding: 24px;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #F8F9FA;
  border-radius: 8px;
}

.file-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: #E8EAED;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 2px;
}

.file-meta {
  font-size: 12px;
  color: #5F6368;
}

.icon-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: #F8F9FA;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-btn:hover {
  background: #E8EAED;
}

.history-entry {
  margin-bottom: 20px;
  padding: 16px;
  background: #F8F9FA;
  border-radius: 8px;
  font-size: 14px;
  color: #202124;
  line-height: 1.6;
}

.history-entry.current {
  background: #E6F4EA;
  border-left: 4px solid #34A853;
}

.history-label {
  font-size: 13px;
  font-weight: 500;
  color: #5F6368;
  margin-bottom: 8px;
}

.current-label {
  color: #188038;
}

.upload-zone {
  border: 2px dashed #DADCE0;
  border-radius: 12px;
  padding: 32px;
  text-align: center;
  margin-bottom: 24px;
  cursor: pointer;
  transition: all 150ms;
}

.upload-zone:hover {
  border-color: #1A73E8;
  background: #F8F9FA;
}

.upload-title {
  font-size: 15px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 4px;
}

.upload-hint {
  font-size: 13px;
  color: #5F6368;
}

.upload-note {
  font-size: 13px;
  color: #5F6368;
}
</style>
