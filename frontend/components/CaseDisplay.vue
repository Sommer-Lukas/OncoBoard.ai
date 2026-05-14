<script setup>
import { ref } from 'vue'

defineProps({
  caseData: { type: Object, required: true },
})

const tabs = [
  { key: 'summary',    label: 'Summary',    icon: 'description' },
  { key: 'radiology',  label: 'Radiology',  icon: 'image' },
  { key: 'pathology',  label: 'Pathology',  icon: 'biotech' },
  { key: 'guidelines', label: 'Guidelines', icon: 'clinical_notes' },
  { key: 'trials',     label: 'Trials',     icon: 'science' },
]

const activeTab = ref('summary')
</script>

<template>
  <div class="case-display">
    <!-- Patient identity strip -->
    <div class="case-header">
      <div class="case-name">{{ caseData.name }}</div>
      <div class="meta-row">
        <span class="case-id">{{ caseData.id }}</span>
        <span class="chip">{{ caseData.age }}y</span>
        <span class="chip">{{ caseData.stage }}</span>
        <span class="chip">{{ caseData.receptors }}</span>
      </div>
    </div>

    <!-- Specialty tabs -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <span class="material-symbols-outlined tab-icon">{{ tab.icon }}</span>
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab content -->
    <div class="tab-content">

      <template v-if="activeTab === 'summary'">
        <div class="content-card">
          <div class="field-label">Diagnosis</div>
          <div class="field-value">{{ caseData.diagnosis }}</div>
        </div>
        <div class="content-card">
          <div class="field-label">Presentation</div>
          <div class="field-value">{{ caseData.presentation }}</div>
        </div>
        <div class="content-card">
          <div class="field-label">Previous Treatment</div>
          <div class="field-value">{{ caseData.previousTreatment }}</div>
        </div>
      </template>

      <template v-else-if="activeTab === 'radiology'">
        <div class="specialty-header">
          <div class="specialty-badge radiology">
            <span class="material-symbols-outlined" style="font-size: 16px">image</span>
            RadiologyAgent · BI-RADS 4
          </div>
        </div>
        <div class="content-card">
          <div class="field-label">Imaging Findings</div>
          <div class="field-value">{{ caseData.radiology }}</div>
        </div>
        <div class="file-list">
          <div class="file-row">
            <span class="material-symbols-outlined file-icon">image</span>
            <div class="file-info">
              <div class="file-name">MRI_Breast_2024-04-18.dcm</div>
              <div class="file-meta">MRI · Apr 18, 2024</div>
            </div>
            <span class="material-symbols-outlined file-action">open_in_new</span>
          </div>
          <div class="file-row">
            <span class="material-symbols-outlined file-icon">image</span>
            <div class="file-info">
              <div class="file-name">Mammography_2024-04-10.dcm</div>
              <div class="file-meta">Mammography · Apr 10, 2024</div>
            </div>
            <span class="material-symbols-outlined file-action">open_in_new</span>
          </div>
          <div class="file-row missing">
            <span class="material-symbols-outlined file-icon">warning</span>
            <div class="file-info">
              <div class="file-name">CT_Chest_2024-04-15.dcm</div>
              <div class="file-meta">CT Chest · Missing</div>
            </div>
            <span class="file-missing-badge">Missing</span>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'pathology'">
        <div class="specialty-header">
          <div class="specialty-badge pathology">
            <span class="material-symbols-outlined" style="font-size: 16px">biotech</span>
            PathologyAgent · Grade 2 IDC
          </div>
        </div>
        <div class="content-card">
          <div class="field-label">Pathology Report</div>
          <div class="field-value">{{ caseData.pathology }}</div>
        </div>
        <div class="file-list">
          <div class="file-row">
            <span class="material-symbols-outlined file-icon">description</span>
            <div class="file-info">
              <div class="file-name">Pathology_Report_2024-04-20.pdf</div>
              <div class="file-meta">Surgical Pathology · Apr 20, 2024</div>
            </div>
            <span class="material-symbols-outlined file-action">open_in_new</span>
          </div>
          <div class="file-row">
            <span class="material-symbols-outlined file-icon">description</span>
            <div class="file-info">
              <div class="file-name">Genomic_Testing_2024-04-22.pdf</div>
              <div class="file-meta">Genomics · Apr 22, 2024</div>
            </div>
            <span class="material-symbols-outlined file-action">open_in_new</span>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'guidelines'">
        <div class="specialty-header">
          <div class="specialty-badge guidelines">
            <span class="material-symbols-outlined" style="font-size: 16px">clinical_notes</span>
            GuidelineAgent · NCCN Match
          </div>
        </div>
        <div class="content-card">
          <div class="field-label">NCCN Recommendation</div>
          <div class="field-value">{{ caseData.guidelines }}</div>
        </div>
        <div class="file-list">
          <div class="file-row">
            <span class="material-symbols-outlined file-icon">menu_book</span>
            <div class="file-info">
              <div class="file-name">NCCN_Breast_Cancer_v2024.pdf</div>
              <div class="file-meta">NCCN Guidelines · 2024</div>
            </div>
            <span class="material-symbols-outlined file-action">open_in_new</span>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'trials'">
        <div class="specialty-header">
          <div class="specialty-badge trials">
            <span class="material-symbols-outlined" style="font-size: 16px">science</span>
            TrialAgent · 1 match found
          </div>
        </div>
        <div class="content-card">
          <div class="field-label">Eligibility & Evidence</div>
          <div class="field-value">{{ caseData.trials }}</div>
        </div>
        <div class="file-list">
          <div class="file-row">
            <span class="material-symbols-outlined file-icon">science</span>
            <div class="file-info">
              <div class="file-name">NCT05234567 — Phase III</div>
              <div class="file-meta">ClinicalTrials.gov · Recruiting</div>
            </div>
            <span class="material-symbols-outlined file-action">open_in_new</span>
          </div>
          <div class="file-row">
            <span class="material-symbols-outlined file-icon">article</span>
            <div class="file-info">
              <div class="file-name">PMID 38201847</div>
              <div class="file-meta">PubMed · Supporting evidence</div>
            </div>
            <span class="material-symbols-outlined file-action">open_in_new</span>
          </div>
        </div>
      </template>

    </div>
  </div>
</template>

<style scoped>
.case-display {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Patient strip */
.case-header {
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #DADCE0;
  flex-shrink: 0;
}

.case-name {
  font-size: 18px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 6px;
}

.meta-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.case-id {
  font-family: 'Roboto Mono', monospace;
  font-size: 12px;
  color: #5F6368;
}

.chip {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: #F8F9FA;
  color: #202124;
}

/* Tab bar */
.tab-bar {
  display: flex;
  gap: 2px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #DADCE0;
  flex-shrink: 0;
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 500;
  color: #5F6368;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  font-family: 'Roboto', sans-serif;
  margin-bottom: -1px;
  transition: color 150ms;
  white-space: nowrap;
}

.tab:hover {
  color: #202124;
}

.tab.active {
  color: #1A73E8;
  border-bottom-color: #1A73E8;
}

.tab-icon {
  font-size: 16px;
}

/* Tab content area */
.tab-content {
  flex: 1;
  overflow: auto;
  padding: 20px 24px;
}

/* Specialty badge */
.specialty-header {
  margin-bottom: 16px;
}

.specialty-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.specialty-badge.radiology  { background: #D2E3FC; color: #174EA6; }
.specialty-badge.pathology  { background: #E6F4EA; color: #188038; }
.specialty-badge.guidelines { background: #FEF7E0; color: #B06000; }
.specialty-badge.trials     { background: #F3E8FD; color: #6B3FA0; }

/* Content cards */
.content-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 12px;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.1);
}

.field-label {
  font-size: 11px;
  font-weight: 500;
  color: #5F6368;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.field-value {
  font-size: 14px;
  color: #202124;
  line-height: 1.65;
}

/* File list */
.file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.08);
  cursor: pointer;
  transition: background 150ms;
}

.file-row:hover {
  background: #F8F9FA;
}

.file-row.missing {
  background: #FEF7E0;
  cursor: default;
}

.file-icon {
  font-size: 18px;
  color: #5F6368;
  flex-shrink: 0;
}

.file-row.missing .file-icon {
  color: #B06000;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 2px;
}

.file-meta {
  font-size: 11px;
  color: #5F6368;
}

.file-action {
  font-size: 16px;
  color: #80868B;
  flex-shrink: 0;
}

.file-missing-badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 999px;
  background: #FBBC04;
  color: #202124;
  flex-shrink: 0;
}
</style>
