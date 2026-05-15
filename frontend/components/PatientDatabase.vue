<script setup>
import { ref, onMounted } from 'vue'
import { getPatient, getPatientImages, getCaseGenomics, imageUrl } from '../src/services/api.js'
import ImageLightbox from './ImageLightbox.vue'

const props = defineProps({
  patient: { type: Object, required: true },
})

defineEmits(['close'])

const activeTab = ref('clinical')
const tabs = [
  { key: 'clinical',  label: 'Clinical',          icon: 'person' },
  { key: 'genomics',  label: 'Genomics',           icon: 'biotech' },
  { key: 'mri',       label: 'MRI Scans',          icon: 'image' },
  { key: 'slides',    label: 'Pathology Slides',   icon: 'biotech' },
]

// ── Clinical ──
const caseData = ref(null)

// ── Genomics ──
const geneInput = ref('TP53, BRCA1, BRCA2, ERBB2, ESR1, PIK3CA, MYC, CCND1')
const genomicsResult = ref(null)
const genomicsLoading = ref(false)
const genomicsError = ref(null)

// ── Images ──
const mriImages = ref([])
const svsImages = ref([])
const mriLoading = ref(false)
const svsLoading = ref(false)

// ── Lightbox ──
const lbImages = ref([])
const lbIndex  = ref(null)

function openLightbox(images, idx) {
  lbImages.value = images
  lbIndex.value  = idx
}
function closeLightbox() { lbIndex.value = null }

onMounted(async () => {
  caseData.value = await getPatient(props.patient.id).catch(() => null)
  mriLoading.value = true
  svsLoading.value = true
  const [mri, svs] = await Promise.all([
    getPatientImages(props.patient.id, 'mri'),
    getPatientImages(props.patient.id, 'svs'),
  ])
  mriImages.value = mri
  svsImages.value = svs
  mriLoading.value = false
  svsLoading.value = false
})

async function fetchGenomics() {
  const genes = geneInput.value.split(',').map(g => g.trim()).filter(Boolean)
  if (!genes.length) return
  genomicsLoading.value = true
  genomicsError.value = null
  genomicsResult.value = null
  genomicsResult.value = await getCaseGenomics(props.patient.id, genes).catch(e => {
    genomicsError.value = 'No genomic data available for this case.'
    return null
  })
  genomicsLoading.value = false
}

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
  <div class="overlay" @click="$emit('close')">
    <div class="modal" @click.stop>

      <div class="modal-header">
        <div>
          <div class="modal-title">Patient Data</div>
          <div class="modal-subtitle">{{ patient.id }}</div>
        </div>
        <button class="close-btn" @click="$emit('close')">
          <span class="material-symbols-outlined" style="font-size: 20px; color: #5F6368">close</span>
        </button>
      </div>

      <div class="tab-bar">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <span class="material-symbols-outlined" style="font-size: 16px">{{ tab.icon }}</span>
          {{ tab.label }}
        </button>
      </div>

      <div class="modal-body">

        <!-- ── Clinical ── -->
        <template v-if="activeTab === 'clinical'">
          <div v-if="!caseData" class="empty-state">Loading…</div>
          <div v-else class="field-grid">
            <div class="field-row"><span class="field-label">Case ID</span><span class="field-value mono">{{ caseData.id }}</span></div>
            <div class="field-row"><span class="field-label">Age at Diagnosis</span><span class="field-value">{{ caseData.age ?? '—' }}</span></div>
            <div class="field-row"><span class="field-label">Stage</span><span class="field-value">{{ caseData.stage ?? '—' }}</span></div>
            <div class="field-row"><span class="field-label">Receptor Status</span><span class="field-value">{{ caseData.receptors }}</span></div>
            <div class="field-row"><span class="field-label">Molecular Subtype</span><span class="field-value">{{ caseData.molecular_subtype ?? '—' }}</span></div>
            <div class="field-row"><span class="field-label">Histological Type</span><span class="field-value">{{ caseData.diagnosis }}</span></div>
            <div class="field-row"><span class="field-label">Presentation</span><span class="field-value">{{ caseData.presentation }}</span></div>
            <div class="field-row"><span class="field-label">Treatment History</span><span class="field-value">{{ caseData.previousTreatment }}</span></div>
            <div class="field-row"><span class="field-label">Pathology Summary</span><span class="field-value">{{ caseData.pathology }}</span></div>
            <div class="field-row"><span class="field-label">NCCN Guideline</span><span class="field-value">{{ caseData.guidelines }}</span></div>
            <template v-if="caseData.dataGaps?.length">
              <div class="field-row">
                <span class="field-label">Data Gaps</span>
                <span class="field-value">
                  <span v-for="(g, i) in caseData.dataGaps" :key="i" class="gap-badge">{{ g.message }}</span>
                </span>
              </div>
            </template>
          </div>
        </template>

        <!-- ── Genomics ── -->
        <template v-else-if="activeTab === 'genomics'">
          <div class="genomics-search">
            <input
              v-model="geneInput"
              class="gene-input"
              placeholder="TP53, BRCA1, ERBB2, …"
              @keydown.enter="fetchGenomics"
            />
            <button class="fetch-btn" :disabled="genomicsLoading" @click="fetchGenomics">
              {{ genomicsLoading ? 'Loading…' : 'Fetch' }}
            </button>
          </div>
          <p class="genomics-hint">Copy number values — diploid baseline is 2. Gain &gt; 3, Loss &lt; 1.5.</p>

          <div v-if="genomicsError" class="empty-state">{{ genomicsError }}</div>

          <table v-else-if="genomicsResult" class="cn-table">
            <thead><tr><th>Gene</th><th>Copy Number</th><th>Status</th></tr></thead>
            <tbody>
              <tr v-for="(v, gene) in genomicsResult.copy_numbers" :key="gene">
                <td class="gene-name">{{ gene }}</td>
                <td>{{ v != null ? v.toFixed(2) : '—' }}</td>
                <td><span class="cn-badge" :class="cnClass(v)">{{ cnLabel(v) }}</span></td>
              </tr>
            </tbody>
          </table>

          <div v-else class="empty-state">Enter gene symbols above and click Fetch.</div>
        </template>

        <!-- ── MRI ── -->
        <template v-else-if="activeTab === 'mri'">
          <div v-if="mriLoading" class="empty-state">Loading images…</div>
          <div v-else-if="!mriImages.length" class="empty-state">No MRI data available for this case.</div>
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

        <!-- ── Slides ── -->
        <template v-else-if="activeTab === 'slides'">
          <div v-if="svsLoading" class="empty-state">Loading slides…</div>
          <div v-else-if="!svsImages.length" class="empty-state">No pathology slides available for this case.</div>
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

      </div>
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
.overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; padding: 24px;
}

.modal {
  background: #fff; border-radius: 16px; width: 100%; max-width: 960px;
  max-height: 90vh; box-shadow: 0 8px 16px rgba(60,64,67,0.15);
  display: flex; flex-direction: column; overflow: hidden;
}

.modal-header {
  padding: 20px 24px; border-bottom: 1px solid #E8EAED;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}
.modal-title   { font-size: 18px; font-weight: 500; color: #202124; }
.modal-subtitle { font-size: 12px; color: #5F6368; font-family: 'Roboto Mono', monospace; margin-top: 2px; }

.close-btn {
  width: 36px; height: 36px; border-radius: 50%; border: none;
  background: #F8F9FA; cursor: pointer; display: flex; align-items: center; justify-content: center;
}
.close-btn:hover { background: #E8EAED; }

.tab-bar {
  display: flex; border-bottom: 1px solid #E8EAED; padding: 0 24px;
  flex-shrink: 0; overflow-x: auto;
}
.tab {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 16px; font-size: 13px; font-weight: 500; color: #5F6368;
  background: transparent; border: none; border-bottom: 2px solid transparent;
  cursor: pointer; margin-bottom: -1px; font-family: 'Roboto', sans-serif;
  white-space: nowrap; transition: color 150ms;
}
.tab:hover { color: #202124; }
.tab.active { color: #1A73E8; border-bottom-color: #1A73E8; }

.modal-body { flex: 1; overflow: auto; padding: 20px 24px; }

/* Clinical */
.field-grid { display: flex; flex-direction: column; gap: 0; }
.field-row {
  display: grid; grid-template-columns: 180px 1fr;
  gap: 12px; padding: 10px 0; border-bottom: 1px solid #F1F3F4;
  font-size: 14px; align-items: baseline;
}
.field-label { font-size: 12px; font-weight: 500; color: #5F6368; text-transform: uppercase; letter-spacing: 0.4px; }
.field-value { color: #202124; line-height: 1.6; }
.field-value.mono { font-family: 'Roboto Mono', monospace; font-size: 12px; }
.gap-badge {
  display: block; font-size: 12px; color: #B06000;
  background: #FEF7E0; padding: 4px 10px; border-radius: 6px; margin-bottom: 4px;
}

/* Genomics */
.genomics-search { display: flex; gap: 8px; margin-bottom: 8px; }
.gene-input {
  flex: 1; padding: 8px 12px; border: 1px solid #DADCE0; border-radius: 8px;
  font-size: 13px; font-family: 'Roboto Mono', monospace; outline: none;
}
.gene-input:focus { border-color: #1A73E8; }
.fetch-btn {
  padding: 8px 20px; background: #1A73E8; color: #fff; border: none;
  border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer;
  font-family: 'Roboto', sans-serif;
}
.fetch-btn:hover { background: #1557b0; }
.fetch-btn:disabled { background: #DADCE0; color: #80868B; cursor: default; }
.genomics-hint { font-size: 12px; color: #80868B; margin: 0 0 16px; }

.cn-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.cn-table th { text-align: left; padding: 8px 12px; font-size: 11px; font-weight: 500; color: #5F6368; text-transform: uppercase; letter-spacing: 0.4px; border-bottom: 1px solid #E8EAED; }
.cn-table td { padding: 10px 12px; border-bottom: 1px solid #F1F3F4; color: #202124; }
.gene-name { font-family: 'Roboto Mono', monospace; font-weight: 500; color: #202124; }
.cn-badge { padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 500; }
.cn-gain    { background: #FCE8E6; color: #A50E0E; }
.cn-loss    { background: #D2E3FC; color: #0D47A1; }
.cn-normal  { background: #CEEAD6; color: #0D652D; }
.cn-unknown { background: #E8EAED; color: #3C4043; }

/* Images */
.image-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
}
.image-grid.tight { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
.image-cell {
  border-radius: 8px; overflow: hidden; background: #F1F3F4;
  aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: opacity 150ms;
}
.image-cell:hover { opacity: 0.85; }
.image-cell img { width: 100%; height: 100%; object-fit: cover; display: block; }

.empty-state {
  padding: 48px 0; text-align: center; font-size: 14px; color: #80868B;
}
</style>
