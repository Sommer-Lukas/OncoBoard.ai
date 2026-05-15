<script setup>
import { ref, watch, onMounted } from 'vue'
import { getPatientImages, getCaseGenomics, imageUrl } from '../src/services/api.js'
import ImageLightbox from './ImageLightbox.vue'

const props = defineProps({
  caseData: { type: Object, required: true },
})

const tabs = [
  { key: 'summary',    label: 'Summary',    icon: 'description' },
  { key: 'radiology',  label: 'Radiology',  icon: 'image' },
  { key: 'pathology',  label: 'Pathology',  icon: 'biotech' },
  { key: 'genomics',   label: 'Genomics',   icon: 'genetics' },
  { key: 'guidelines', label: 'Guidelines', icon: 'clinical_notes' },
  { key: 'trials',     label: 'Trials',     icon: 'science' },
]

const activeTab = ref('summary')

// Images
const mriImages = ref([])
const svsImages = ref([])
const imagesLoading = ref(false)

// Lightbox
const lbImages = ref([])
const lbIndex  = ref(null)

function openLightbox(images, idx) {
  lbImages.value = images
  lbIndex.value  = idx
}
function closeLightbox() { lbIndex.value = null }

// Genomics
const genomicsResult = ref(null)
const genomicsLoading = ref(false)
const genomicsError = ref(null)

const DEFAULT_GENES = ['TP53', 'BRCA1', 'BRCA2', 'ERBB2', 'ESR1', 'PIK3CA', 'MYC', 'CCND1', 'CDH1', 'PTEN']

async function loadData(id) {
  imagesLoading.value = true
  genomicsLoading.value = true
  genomicsError.value = null
  genomicsResult.value = null
  mriImages.value = []
  svsImages.value = []

  const [mri, svs] = await Promise.all([
    getPatientImages(id, 'mri'),
    getPatientImages(id, 'svs'),
  ])
  mriImages.value = mri
  svsImages.value = svs
  imagesLoading.value = false

  try {
    genomicsResult.value = await getCaseGenomics(id, DEFAULT_GENES)
  } catch (e) {
    genomicsError.value = e.message
  }
  genomicsLoading.value = false
}

onMounted(() => loadData(props.caseData.id))
watch(() => props.caseData.id, loadData)

function cnClass(v) {
  if (v == null) return 'cn-unknown'
  if (v > 3) return 'cn-gain'
  if (v < 1.5) return 'cn-loss'
  return 'cn-normal'
}

function cnLabel(v) {
  if (v == null) return '—'
  if (v > 3) return 'Gain'
  if (v < 1.5) return 'Loss'
  return 'Normal'
}
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

      <!-- Summary -->
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

      <!-- Radiology -->
      <template v-else-if="activeTab === 'radiology'">
        <div class="specialty-header">
          <div class="specialty-badge radiology">
            <span class="material-symbols-outlined" style="font-size: 16px">image</span>
            RadiologyAgent
          </div>
        </div>
        <div class="content-card">
          <div class="field-label">Imaging Findings</div>
          <div class="field-value">{{ caseData.radiology }}</div>
        </div>
        <div class="field-label section-gap">MRI Scans</div>
        <div v-if="imagesLoading" class="empty-state">Loading images…</div>
        <div v-else-if="!mriImages.length" class="empty-state">No MRI data for this case.</div>
        <div v-else class="image-grid">
          <div
            v-for="(path, idx) in mriImages"
            :key="path"
            class="image-cell"
            @click="openLightbox(mriImages, idx)"
          >
            <img :src="imageUrl(path)" :alt="path.split('/').pop()" loading="lazy" />
          </div>
        </div>
      </template>

      <!-- Pathology -->
      <template v-else-if="activeTab === 'pathology'">
        <div class="specialty-header">
          <div class="specialty-badge pathology">
            <span class="material-symbols-outlined" style="font-size: 16px">biotech</span>
            PathologyAgent
          </div>
        </div>
        <div class="content-card">
          <div class="field-label">Pathology Report</div>
          <div class="field-value">{{ caseData.pathology }}</div>
        </div>
        <div class="field-label section-gap">Pathology Slides (SVS)</div>
        <div v-if="imagesLoading" class="empty-state">Loading slides…</div>
        <div v-else-if="!svsImages.length" class="empty-state">No pathology slides for this case.</div>
        <div v-else class="image-grid tight">
          <div
            v-for="(path, idx) in svsImages"
            :key="path"
            class="image-cell"
            @click="openLightbox(svsImages, idx)"
          >
            <img :src="imageUrl(path)" :alt="path.split('/').pop()" loading="lazy" />
          </div>
        </div>
      </template>

      <!-- Genomics -->
      <template v-else-if="activeTab === 'genomics'">
        <div class="specialty-header">
          <div class="specialty-badge genomics">
            <span class="material-symbols-outlined" style="font-size: 16px">genetics</span>
            Copy Number Variation — diploid baseline 2
          </div>
        </div>
        <div v-if="genomicsLoading" class="empty-state">Loading genomics…</div>
        <div v-else-if="genomicsError" class="empty-state">{{ genomicsError }}</div>
        <table v-else-if="genomicsResult" class="cn-table">
          <thead>
            <tr><th>Gene</th><th>Copy Number</th><th>Status</th></tr>
          </thead>
          <tbody>
            <tr v-for="(v, gene) in genomicsResult.copy_numbers" :key="gene">
              <td class="gene-name">{{ gene }}</td>
              <td>{{ v != null ? v.toFixed(2) : '—' }}</td>
              <td><span class="cn-badge" :class="cnClass(v)">{{ cnLabel(v) }}</span></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state">No genomic data available.</div>
      </template>

      <!-- Guidelines -->
      <template v-else-if="activeTab === 'guidelines'">
        <div class="specialty-header">
          <div class="specialty-badge guidelines">
            <span class="material-symbols-outlined" style="font-size: 16px">clinical_notes</span>
            GuidelineAgent · NCCN
          </div>
        </div>
        <div class="content-card">
          <div class="field-label">NCCN Recommendation</div>
          <div class="field-value">{{ caseData.guidelines }}</div>
        </div>
      </template>

      <!-- Trials -->
      <template v-else-if="activeTab === 'trials'">
        <div class="specialty-header">
          <div class="specialty-badge trials">
            <span class="material-symbols-outlined" style="font-size: 16px">science</span>
            TrialAgent
          </div>
        </div>
        <div class="content-card">
          <div class="field-label">Eligibility & Evidence</div>
          <div class="field-value">{{ caseData.trials }}</div>
        </div>
      </template>

    </div>
  </div>

  <ImageLightbox
    v-if="lbIndex !== null"
    :images="lbImages"
    :index="lbIndex"
    @close="closeLightbox"
    @navigate="lbIndex = $event"
  />
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
  overflow-x: auto;
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

.tab:hover { color: #202124; }
.tab.active { color: #1A73E8; border-bottom-color: #1A73E8; }

.tab-icon { font-size: 16px; }

/* Tab content area */
.tab-content {
  flex: 1;
  overflow: auto;
  padding: 20px 24px;
}

/* Specialty badge */
.specialty-header { margin-bottom: 16px; }

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
.specialty-badge.pathology  { background: #CEEAD6; color: #0D652D; }
.specialty-badge.genomics   { background: #F3E8FD; color: #6B3FA0; }
.specialty-badge.guidelines { background: #FEF7E0; color: #B06000; }
.specialty-badge.trials     { background: #E8F0FE; color: #1967D2; }

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

.section-gap { margin-top: 8px; margin-bottom: 12px; }

/* Images */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
}
.image-grid.tight { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }

.image-cell {
  border-radius: 8px;
  overflow: hidden;
  background: #E8EAED;
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: opacity 150ms;
}
.image-cell:hover { opacity: 0.85; }
.image-cell img { width: 100%; height: 100%; object-fit: cover; display: block; }

/* Genomics table */
.cn-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.cn-table th {
  text-align: left; padding: 8px 12px;
  font-size: 11px; font-weight: 500; color: #5F6368;
  text-transform: uppercase; letter-spacing: 0.4px;
  border-bottom: 1px solid #E8EAED;
}
.cn-table td { padding: 10px 12px; border-bottom: 1px solid #F1F3F4; color: #202124; }
.gene-name { font-family: 'Roboto Mono', monospace; font-weight: 500; color: #202124; }
.cn-badge { padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 500; }
.cn-gain    { background: #FCE8E6; color: #A50E0E; }
.cn-loss    { background: #D2E3FC; color: #0D47A1; }
.cn-normal  { background: #CEEAD6; color: #0D652D; }
.cn-unknown { background: #E8EAED; color: #3C4043; }

.empty-state {
  padding: 40px 0;
  text-align: center;
  font-size: 14px;
  color: #80868B;
}
</style>
