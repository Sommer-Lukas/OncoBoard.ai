<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  name:            { type: String,   required: true },
  icon:            { type: String,   required: true },
  status:          { type: String,   default: 'idle' },
  timestamp:       { type: String,   default: null },
  output:          { type: String,   default: null },
  rawData:         { type: Object,   default: null },
  verified:        { type: Boolean,  default: false },
  verifiedBy:      { type: String,   default: null },
  verifiedTs:      { type: String,   default: null },
  onDatabaseClick: { type: Function, default: null },
})

const emit = defineEmits(['database-click', 'verify', 'unverify'])

const modalOpen = ref(false)

const statusConfig = {
  complete: { bg: '#E6F4EA', color: '#188038', icon: 'check_circle', label: 'Complete' },
  running:  { bg: 'rgba(26,115,232,0.1)', color: '#174EA6', icon: '',              label: 'Running'  },
  error:    { bg: '#FCE8E6', color: '#C5221F', icon: 'error',         label: 'Error'    },
  idle:     { bg: '#F8F9FA', color: '#9AA0A6', icon: '',              label: 'Idle'     },
}

const config = computed(() => statusConfig[props.status] ?? statusConfig.idle)

const matchedTrials = computed(() =>
  Array.isArray(props.rawData?.matched_trials) ? props.rawData.matched_trials : []
)

const pubmedRefs = computed(() =>
  Array.isArray(props.rawData?.pubmed_references) ? props.rawData.pubmed_references : []
)

// Status badge helper for CaseCompiler
function gapSeverityStyle(severity) {
  if (!severity) return { bg: '#F8F9FA', color: '#5F6368' }
  const s = severity.toLowerCase()
  if (s === 'critical') return { bg: '#FCE8E6', color: '#C5221F' }
  if (s === 'warning')  return { bg: '#FEF7E0', color: '#B06000' }
  return { bg: '#F8F9FA', color: '#5F6368' }
}

function handleCardClick() {
  if (props.status === 'complete') modalOpen.value = true
}

function handleDatabaseClick(e) {
  e.stopPropagation()
  emit('database-click', props.name)
}

function handleVerifyClick(e) {
  e.stopPropagation()
  if (props.verified) emit('unverify', props.name)
  else emit('verify', props.name)
}

function handleModalVerify() {
  if (props.verified) emit('unverify', props.name)
  else emit('verify', props.name)
}
</script>

<template>
  <div class="agent-card" :class="status" @click="handleCardClick">

    <!-- Scan highlight -->
    <div v-if="status === 'running'" class="scan-bar" aria-hidden="true"></div>

    <!-- Database shortcut -->
    <button
      v-if="onDatabaseClick && status === 'complete'"
      class="db-btn"
      :title="`View ${name} data in database`"
      @click="handleDatabaseClick"
    >
      <span class="material-symbols-outlined" style="font-size: 18px; color: #5F6368">database</span>
    </button>

    <div class="card-header" :class="{ clickable: status === 'complete' }">
      <!-- Icon with sonar rings when running -->
      <div class="icon-wrapper">
        <div v-if="status === 'running'" class="pulse-ring ring-1" aria-hidden="true"></div>
        <div v-if="status === 'running'" class="pulse-ring ring-2" aria-hidden="true"></div>
        <div class="icon-box" :class="status">
          <img :src="icon" :alt="name" class="icon-img" />
        </div>
      </div>

      <div class="card-content">
        <div class="card-title">{{ name }}</div>

        <div class="status-chip" :style="{ background: config.bg, color: config.color }">
          <span v-if="config.icon" class="material-symbols-outlined" style="font-size: 14px">{{ config.icon }}</span>
          <template v-if="status === 'running'">
            <span>Analyzing</span>
            <span class="dot-anim" aria-hidden="true">
              <span class="dot d1">.</span><span class="dot d2">.</span><span class="dot d3">.</span>
            </span>
          </template>
          <span v-else style="text-transform: capitalize">{{ config.label }}</span>
        </div>

        <div v-if="timestamp" class="timestamp">{{ timestamp }}</div>
      </div>

      <!-- Verify button (complete only) -->
      <button
        v-if="status === 'complete'"
        class="verify-btn"
        :class="{ verified }"
        :title="verified ? `Verified by ${verifiedBy} at ${verifiedTs} — click to undo` : 'Mark as verified'"
        @click="handleVerifyClick"
      >
        <span class="material-symbols-outlined" style="font-size: 15px">
          {{ verified ? 'verified' : 'check_small' }}
        </span>
        <span>{{ verified ? `Verified` : 'Verify' }}</span>
      </button>

      <!-- Expand chevron -->
      <span
        v-if="status === 'complete'"
        class="material-symbols-outlined expand-chevron"
        aria-hidden="true"
      >open_in_full</span>
    </div>

    <!-- Truncated summary -->
    <div v-if="status === 'complete' && output" class="summary-box">{{ output }}</div>
  </div>

  <!-- Full-output modal -->
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="modalOpen" class="modal-backdrop" @click.self="modalOpen = false">
        <div class="modal-panel">
          <div class="modal-header">
            <div class="modal-title-row">
              <img :src="icon" :alt="name" class="modal-icon" />
              <span class="modal-title">{{ name }}</span>
              <div class="modal-status-chip" :style="{ background: config.bg, color: config.color }">
                <span class="material-symbols-outlined" style="font-size: 14px">{{ config.icon }}</span>
                {{ config.label }}
              </div>
            </div>
            <div class="modal-actions">
              <button
                class="modal-verify-btn"
                :class="{ verified }"
                @click="handleModalVerify"
              >
                <span class="material-symbols-outlined" style="font-size: 16px">
                  {{ verified ? 'verified' : 'check_small' }}
                </span>
                {{ verified ? `Verified by ${verifiedBy}` : 'Mark as Verified' }}
              </button>
              <button class="modal-close-btn" @click="modalOpen = false">
                <span class="material-symbols-outlined" style="font-size: 20px">close</span>
              </button>
            </div>
          </div>

          <div class="modal-body">

            <!-- ── CaseCompiler ── -->
            <template v-if="name === 'CaseCompiler' && rawData">
              <div class="readable-section">
                <div class="rs-label">Case Overview</div>
                <div class="kv-grid">
                  <template v-for="(v, k) in rawData.clinical" :key="k">
                    <span class="kv-key">{{ k.replace(/_/g, ' ') }}</span>
                    <span class="kv-val">{{ v ?? '—' }}</span>
                  </template>
                </div>
              </div>
              <div v-if="rawData.genomics" class="readable-section">
                <div class="rs-label">Genomics</div>
                <div class="kv-grid">
                  <template v-for="(v, k) in rawData.genomics" :key="k">
                    <span class="kv-key">{{ k.replace(/_/g, ' ') }}</span>
                    <span class="kv-val">{{ v ?? '—' }}</span>
                  </template>
                </div>
              </div>
              <div class="readable-section">
                <div class="rs-label">Record Summary</div>
                <div class="kv-grid">
                  <span class="kv-key">Files attached</span>
                  <span class="kv-val">{{ rawData.file_count }}</span>
                  <span class="kv-key">Ready for review</span>
                  <span class="kv-val">{{ rawData.ready_for_review ? 'Yes' : 'No' }}</span>
                </div>
              </div>
              <div v-if="rawData.data_gaps?.length" class="readable-section">
                <div class="rs-label">Data Gaps</div>
                <div class="gap-list">
                  <div v-for="(gap, i) in rawData.data_gaps" :key="i" class="gap-item">
                    <span class="gap-badge"
                      :style="{ background: gapSeverityStyle(gap.severity).bg, color: gapSeverityStyle(gap.severity).color }">
                      {{ gap.severity ?? 'info' }}
                    </span>
                    <span class="gap-msg">{{ gap.message ?? gap }}</span>
                  </div>
                </div>
              </div>
            </template>

            <!-- ── SummaryAgent ── -->
            <template v-else-if="name === 'SummaryAgent' && rawData">
              <div class="readable-section">
                <div class="rs-label">Clinical Narrative</div>
                <p class="narrative-text">{{ rawData.narrative }}</p>
              </div>
              <div v-if="rawData.key_points?.length" class="readable-section">
                <div class="rs-label">Key Points</div>
                <ul class="bullet-list">
                  <li v-for="(pt, i) in rawData.key_points" :key="i">{{ pt }}</li>
                </ul>
              </div>
              <div v-if="rawData.data_gaps_flagged?.length" class="readable-section">
                <div class="rs-label">Gaps Flagged</div>
                <ul class="bullet-list warn">
                  <li v-for="(g, i) in rawData.data_gaps_flagged" :key="i">{{ g }}</li>
                </ul>
              </div>
            </template>

            <!-- ── RadiologyAgent ── -->
            <template v-else-if="name === 'RadiologyAgent' && rawData">
              <div class="readable-section">
                <div class="rs-label">Radiologist Impression</div>
                <p class="narrative-text">{{ rawData.radiologist_impression }}</p>
              </div>
              <div class="readable-section">
                <div class="rs-label">BI-RADS Classification</div>
                <div class="kv-grid">
                  <span class="kv-key">Overall category</span>
                  <span class="kv-val highlight">{{ rawData.overall_birads_category }}</span>
                  <span class="kv-key">Breast density</span>
                  <span class="kv-val">{{ rawData.breast_density }}</span>
                  <span class="kv-key">Modalities reviewed</span>
                  <span class="kv-val">{{ rawData.imaging_modalities_reviewed?.join(', ') ?? '—' }}</span>
                </div>
              </div>
              <div v-if="rawData.mass_findings?.length" class="readable-section">
                <div class="rs-label">Mass Findings</div>
                <ul class="bullet-list">
                  <li v-for="(f, i) in rawData.mass_findings" :key="i">{{ f }}</li>
                </ul>
              </div>
              <div v-if="rawData.calcification_findings?.length" class="readable-section">
                <div class="rs-label">Calcification Findings</div>
                <ul class="bullet-list">
                  <li v-for="(f, i) in rawData.calcification_findings" :key="i">{{ f }}</li>
                </ul>
              </div>
              <div v-if="rawData.associated_features?.length" class="readable-section">
                <div class="rs-label">Associated Features</div>
                <ul class="bullet-list">
                  <li v-for="(f, i) in rawData.associated_features" :key="i">{{ f }}</li>
                </ul>
              </div>
              <div v-if="rawData.comparison_with_prior" class="readable-section">
                <div class="rs-label">Comparison with Prior</div>
                <p class="narrative-text">{{ rawData.comparison_with_prior }}</p>
              </div>
              <div v-if="rawData.data_gaps?.length" class="readable-section">
                <div class="rs-label">Data Gaps</div>
                <ul class="bullet-list warn">
                  <li v-for="(g, i) in rawData.data_gaps" :key="i">{{ g }}</li>
                </ul>
              </div>
            </template>

            <!-- ── PathologyAgent ── -->
            <template v-else-if="name === 'PathologyAgent' && rawData">
              <div class="readable-section">
                <div class="rs-label">Synoptic Summary</div>
                <p class="narrative-text">{{ rawData.synoptic_summary }}</p>
              </div>
              <div v-if="rawData.ihc_profile && Object.keys(rawData.ihc_profile).length" class="readable-section">
                <div class="rs-label">IHC Profile</div>
                <div class="kv-grid">
                  <template v-for="(v, k) in rawData.ihc_profile" :key="k">
                    <span class="kv-key">{{ k }}</span>
                    <span class="kv-val">{{ v }}</span>
                  </template>
                </div>
              </div>
              <div class="readable-section">
                <div class="rs-label">Molecular Subtype</div>
                <p class="narrative-text">{{ rawData.molecular_subtype_interpretation }}</p>
              </div>
              <div v-if="rawData.driver_alterations?.length" class="readable-section">
                <div class="rs-label">Driver Alterations</div>
                <ul class="bullet-list">
                  <li v-for="(a, i) in rawData.driver_alterations" :key="i">{{ a }}</li>
                </ul>
              </div>
              <div v-if="rawData.prognostic_markers?.length" class="readable-section">
                <div class="rs-label">Prognostic Markers</div>
                <ul class="bullet-list">
                  <li v-for="(m, i) in rawData.prognostic_markers" :key="i">{{ m }}</li>
                </ul>
              </div>
              <div v-if="rawData.pathologist_comment" class="readable-section">
                <div class="rs-label">Pathologist Comment</div>
                <p class="narrative-text muted">{{ rawData.pathologist_comment }}</p>
              </div>
              <div v-if="rawData.data_gaps?.length" class="readable-section">
                <div class="rs-label">Data Gaps</div>
                <ul class="bullet-list warn">
                  <li v-for="(g, i) in rawData.data_gaps" :key="i">{{ g }}</li>
                </ul>
              </div>
            </template>

            <!-- ── GuidelineAgent ── -->
            <template v-else-if="name === 'GuidelineAgent' && rawData">
              <div class="readable-section">
                <div class="rs-label">Matched Guideline</div>
                <div class="kv-grid">
                  <span class="kv-key">Guideline</span>
                  <span class="kv-val highlight">{{ rawData.matched_guideline }}</span>
                  <span class="kv-key">Pathway</span>
                  <span class="kv-val">{{ rawData.guideline_pathway }}</span>
                  <span class="kv-key">Category</span>
                  <span class="kv-val">{{ rawData.recommendation_category }}</span>
                  <span class="kv-key">Evidence level</span>
                  <span class="kv-val">{{ rawData.evidence_level }}</span>
                </div>
              </div>
              <div v-if="rawData.systemic_therapy_options?.length" class="readable-section">
                <div class="rs-label">Systemic Therapy Options</div>
                <ul class="bullet-list">
                  <li v-for="(o, i) in rawData.systemic_therapy_options" :key="i">{{ o }}</li>
                </ul>
              </div>
              <div v-if="rawData.endocrine_therapy_options?.length" class="readable-section">
                <div class="rs-label">Endocrine Therapy Options</div>
                <ul class="bullet-list">
                  <li v-for="(o, i) in rawData.endocrine_therapy_options" :key="i">{{ o }}</li>
                </ul>
              </div>
              <div v-if="rawData.radiation_considerations" class="readable-section">
                <div class="rs-label">Radiation Considerations</div>
                <p class="narrative-text">{{ rawData.radiation_considerations }}</p>
              </div>
              <div v-if="rawData.surgery_considerations" class="readable-section">
                <div class="rs-label">Surgery Considerations</div>
                <p class="narrative-text">{{ rawData.surgery_considerations }}</p>
              </div>
              <div class="readable-section">
                <div class="rs-label">Protocol Rationale</div>
                <p class="narrative-text">{{ rawData.protocol_rationale }}</p>
              </div>
              <div v-if="rawData.data_gaps?.length" class="readable-section">
                <div class="rs-label">Data Gaps</div>
                <ul class="bullet-list warn">
                  <li v-for="(g, i) in rawData.data_gaps" :key="i">{{ g }}</li>
                </ul>
              </div>
            </template>

            <!-- ── TrialAgent ── -->
            <template v-else-if="name === 'TrialAgent' && rawData">
              <div class="readable-section">
                <div class="rs-label">Search Criteria</div>
                <div class="kv-grid">
                  <template v-for="(v, k) in rawData.search_criteria" :key="k">
                    <span class="kv-key">{{ k.replace(/_/g, ' ') }}</span>
                    <span class="kv-val">{{ v ?? '—' }}</span>
                  </template>
                  <span class="kv-key">Trials retrieved</span>
                  <span class="kv-val">{{ rawData.trials_retrieved }}</span>
                </div>
              </div>
              <div v-if="matchedTrials.length" class="readable-section">
                <div class="rs-label">Matched Trials</div>
                <div v-for="trial in matchedTrials" :key="trial.nct_id" class="trial-card">
                  <div class="trial-card-top">
                    <a :href="`https://clinicaltrials.gov/study/${trial.nct_id}`" target="_blank" rel="noopener noreferrer" class="trial-nct-link">
                      {{ trial.nct_id }}
                      <span class="material-symbols-outlined" style="font-size:12px;vertical-align:middle">open_in_new</span>
                    </a>
                    <span v-if="trial.phase" class="trial-link-phase">{{ trial.phase }}</span>
                    <span class="trial-status-badge">{{ trial.overall_status }}</span>
                  </div>
                  <div class="trial-title">{{ trial.title }}</div>
                  <div v-if="trial.eligibility_delta" class="trial-eligibility">
                    <span class="material-symbols-outlined" style="font-size:13px;color:#1A73E8">difference</span>
                    {{ trial.eligibility_delta }}
                  </div>
                  <div v-if="trial.brief_summary" class="trial-summary-text">{{ trial.brief_summary }}</div>
                </div>
              </div>
              <div v-if="pubmedRefs.length" class="readable-section">
                <div class="rs-label">PubMed References</div>
                <div v-for="ref in pubmedRefs" :key="ref.pmid" class="pubmed-card">
                  <a :href="`https://pubmed.ncbi.nlm.nih.gov/${ref.pmid}/`" target="_blank" rel="noopener noreferrer" class="pubmed-pmid-link">
                    PMID {{ ref.pmid }}
                    <span class="material-symbols-outlined" style="font-size:12px;vertical-align:middle">open_in_new</span>
                  </a>
                  <span v-if="ref.source" class="pubmed-source">{{ ref.source }}</span>
                  <div v-if="ref.title" class="pubmed-title">{{ ref.title }}</div>
                </div>
              </div>
              <div v-if="rawData.agent_notes" class="readable-section">
                <div class="rs-label">Agent Notes</div>
                <p class="narrative-text muted">{{ rawData.agent_notes }}</p>
              </div>
            </template>

            <!-- ── HistoryCaseAgent ── -->
            <template v-else-if="name === 'HistoryCaseAgent' && rawData">
              <div class="readable-section">
                <div class="rs-label">Search Basis</div>
                <p class="narrative-text">{{ rawData.search_basis }}</p>
              </div>
              <div v-if="rawData.analogous_cases?.length" class="readable-section">
                <div class="rs-label">Analogous Cases</div>
                <div v-for="c in rawData.analogous_cases" :key="c.case_id" class="history-card">
                  <div class="history-card-id">{{ c.case_id }}</div>
                  <div class="kv-grid compact">
                    <span class="kv-key">Receptor match</span>
                    <span class="kv-val">{{ c.receptor_match }}</span>
                    <span class="kv-key">Stage match</span>
                    <span class="kv-val">{{ c.stage_match }}</span>
                    <span v-if="c.treatment_summary" class="kv-key">Treatment</span>
                    <span v-if="c.treatment_summary" class="kv-val">{{ c.treatment_summary }}</span>
                    <span v-if="c.outcome_note" class="kv-key">Outcome</span>
                    <span v-if="c.outcome_note" class="kv-val">{{ c.outcome_note }}</span>
                  </div>
                  <p class="history-rationale">{{ c.similarity_rationale }}</p>
                </div>
              </div>
              <div v-else class="readable-section">
                <p class="narrative-text muted">No analogous cases found in the database.</p>
              </div>
              <div v-if="rawData.agent_notes" class="readable-section">
                <div class="rs-label">Agent Notes</div>
                <p class="narrative-text muted">{{ rawData.agent_notes }}</p>
              </div>
            </template>

            <!-- ── Fallback: raw JSON ── -->
            <template v-else>
              <pre class="output-pre">{{ rawData ? JSON.stringify(rawData, null, 2) : (output ?? 'No output available.') }}</pre>
            </template>

          </div>

          <div v-if="verified" class="modal-verified-banner">
            <span class="material-symbols-outlined" style="font-size: 15px">verified</span>
            Verified by {{ verifiedBy }} at {{ verifiedTs }}
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ── Base card ── */
.agent-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px 18px;
  position: relative;
  border: 1.5px solid transparent;
  transition: box-shadow 200ms, border-color 200ms, background 200ms, opacity 200ms;
  cursor: default;
}

.agent-card:not(.running):not(.idle) {
  box-shadow: 0 1px 2px rgba(60,64,67,0.08);
}

.agent-card.running {
  border-color: rgba(26,115,232,0.32);
  background: #FAFCFF;
  box-shadow:
    0 0 0 3px rgba(26,115,232,0.06),
    0 2px 10px rgba(26,115,232,0.12);
}

.agent-card.complete {
  cursor: pointer;
}
.agent-card.complete:hover {
  box-shadow: 0 1px 3px rgba(60,64,67,0.12), 0 4px 8px rgba(60,64,67,0.08);
  border-color: rgba(52,168,83,0.18);
}

.agent-card.idle { opacity: 0.6; }

.agent-card.error { border-color: rgba(234,67,53,0.28); }

/* ── Scan bar ── */
.scan-bar {
  position: absolute; inset: 0; border-radius: 9px;
  pointer-events: none; overflow: hidden; z-index: 0;
}
.scan-bar::after {
  content: '';
  position: absolute; top: 0; width: 90px; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(26,115,232,0.08), transparent);
  animation: scan-sweep 3s ease-in-out infinite;
}

/* ── Sonar rings ── */
.icon-wrapper {
  position: relative; width: 52px; height: 52px; flex-shrink: 0;
}
.pulse-ring {
  position: absolute; inset: -5px;
  border: 1.5px solid rgba(26,115,232,0.45);
  border-radius: 14px;
  animation: ring-expand 2.2s ease-out infinite;
  pointer-events: none;
}
.ring-2 { animation-delay: 1.1s; }

/* ── Icon box ── */
.icon-box {
  position: absolute; inset: 0; border-radius: 12px; background: #F8F9FA;
  display: flex; align-items: center; justify-content: center;
  z-index: 1; transition: background 200ms;
}
.icon-box.running  { background: rgba(26,115,232,0.1); }
.icon-box.complete { background: #E6F4EA; }
.icon-box.error    { background: #FCE8E6; }

.icon-img { width: 34px; height: 34px; object-fit: contain; transition: opacity 200ms; }
.icon-box.idle    .icon-img { opacity: 0.4; }
.icon-box.running .icon-img { animation: icon-breathe 2s ease-in-out infinite; }

/* ── Card header ── */
.card-header {
  display: flex; align-items: center; gap: 14px;
  position: relative; z-index: 1;
}
.card-header.clickable { cursor: pointer; }

.card-content { flex: 1; min-width: 0; }

.card-title {
  font-size: 14px; font-weight: 500; color: #202124;
  margin-bottom: 5px; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; transition: color 200ms;
}
.agent-card.running .card-title { color: #174EA6; }

.status-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 999px;
  font-size: 11px; font-weight: 500; line-height: 1.4;
}

.dot-anim { display: inline-flex; gap: 1px; margin-left: 1px; }
.dot { display: inline-block; animation: dot-fade 1.4s ease-in-out infinite; font-weight: 700; }
.d1 { animation-delay: 0s; }
.d2 { animation-delay: 0.22s; }
.d3 { animation-delay: 0.44s; }

.timestamp { font-size: 10px; color: #9AA0A6; margin-top: 3px; font-family: 'Roboto Mono', monospace; }

/* ── Verify button (on card) ── */
.verify-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 999px;
  border: 1.5px solid #DADCE0;
  background: #fff; color: #5F6368;
  font-size: 11px; font-weight: 500; cursor: pointer;
  font-family: 'Roboto', sans-serif;
  transition: all 150ms; white-space: nowrap; flex-shrink: 0;
}
.verify-btn:hover { background: #F8F9FA; border-color: #BDC1C6; }
.verify-btn.verified {
  background: #E6F4EA; border-color: #34A853; color: #137333;
}

/* ── Expand icon ── */
.expand-chevron {
  font-size: 16px; color: #BDC1C6; flex-shrink: 0; margin-top: 2px;
}

/* ── DB button ── */
.db-btn {
  position: absolute; top: 8px; right: 8px;
  width: 26px; height: 26px; border-radius: 50%; border: none;
  background: #F8F9FA; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 150ms; z-index: 2;
}
.db-btn:hover { background: #E8EAED; }

/* ── Summary box ── */
.summary-box {
  margin-top: 10px;
  padding: 8px 12px;
  background: #F8F9FA; border-radius: 7px;
  font-size: 12px; color: #5F6368; line-height: 1.5;
  border-left: 3px solid #34A853;
  position: relative; z-index: 1;
}

/* ── Modal backdrop ── */
.modal-backdrop {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(32,33,36,0.5);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}

/* ── Modal panel ── */
.modal-panel {
  background: #fff; border-radius: 16px;
  width: 100%; max-width: 720px;
  max-height: 80vh;
  display: flex; flex-direction: column;
  box-shadow: 0 8px 32px rgba(32,33,36,0.22);
  overflow: hidden;
}

.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid #DADCE0; flex-shrink: 0;
}

.modal-title-row {
  display: flex; align-items: center; gap: 10px;
}

.modal-icon { width: 28px; height: 28px; object-fit: contain; }

.modal-title {
  font-size: 15px; font-weight: 500; color: #202124;
}

.modal-status-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 999px;
  font-size: 11px; font-weight: 500;
}

.modal-actions {
  display: flex; align-items: center; gap: 8px;
}

.modal-verify-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 14px; border-radius: 999px;
  border: 1.5px solid #DADCE0;
  background: #fff; color: #5F6368;
  font-size: 13px; font-weight: 500; cursor: pointer;
  font-family: 'Roboto', sans-serif; transition: all 150ms;
}
.modal-verify-btn:hover { background: #F8F9FA; }
.modal-verify-btn.verified {
  background: #E6F4EA; border-color: #34A853; color: #137333;
}

.modal-close-btn {
  width: 32px; height: 32px; border-radius: 50%; border: none;
  background: #F8F9FA; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 150ms; color: #5F6368;
}
.modal-close-btn:hover { background: #E8EAED; }

.modal-body {
  flex: 1; overflow-y: auto; padding: 20px;
}

.trial-links-section {
  margin-bottom: 16px;
  padding: 12px 14px;
  background: #E8F0FE;
  border-radius: 10px;
  border: 1px solid #C5D9F7;
}

.trial-links-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; color: #174EA6; margin-bottom: 10px;
}

.trial-links-list {
  display: flex; flex-wrap: wrap; gap: 8px;
}

.trial-link-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: 999px;
  background: #fff; border: 1.5px solid #C5D9F7;
  color: #1967D2; text-decoration: none;
  font-size: 12px; font-weight: 500;
  transition: background 150ms, border-color 150ms, box-shadow 150ms;
}
.trial-link-pill:hover {
  background: #D2E3FC; border-color: #1A73E8;
  box-shadow: 0 1px 4px rgba(26,115,232,.2);
}

.trial-link-id {
  font-family: 'Roboto Mono', monospace;
}

.trial-link-phase {
  font-size: 10px; font-weight: 600;
  background: #D2E3FC; color: #174EA6;
  padding: 1px 6px; border-radius: 999px;
}

.pubmed-links-section {
  background: #E6F4EA;
  border-color: #CEEAD6;
}

.pubmed-links-section .trial-links-label { color: #137333; }

.pubmed-pill {
  color: #137333;
  border-color: #CEEAD6;
}
.pubmed-pill:hover {
  background: #CEEAD6;
  border-color: #34A853;
  box-shadow: 0 1px 4px rgba(52,168,83,.2);
}
.pubmed-pill .trial-link-phase {
  background: #CEEAD6;
  color: #0D652D;
}

.output-pre {
  margin: 0;
  font-family: 'Roboto Mono', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: #202124;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── Readable agent output ── */
.readable-section {
  margin-bottom: 20px;
}
.readable-section:last-child { margin-bottom: 0; }

.rs-label {
  font-size: 10px; font-weight: 700; letter-spacing: 0.07em;
  text-transform: uppercase; color: #80868B;
  margin-bottom: 8px;
}

.narrative-text {
  margin: 0; font-size: 14px; color: #202124; line-height: 1.65;
}
.narrative-text.muted { color: #5F6368; }

.kv-grid {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 5px 16px;
  font-size: 13px;
}
.kv-grid.compact { gap: 3px 12px; font-size: 12.5px; }

.kv-key {
  color: #5F6368; white-space: nowrap;
  text-transform: capitalize;
}
.kv-val { color: #202124; word-break: break-word; }
.kv-val.highlight { font-weight: 600; color: #174EA6; }

.bullet-list {
  margin: 0; padding-left: 18px;
  display: flex; flex-direction: column; gap: 4px;
  font-size: 13.5px; color: #202124; line-height: 1.5;
}
.bullet-list.warn { color: #B06000; }
.bullet-list.warn li::marker { color: #F29900; }

.gap-list { display: flex; flex-direction: column; gap: 6px; }
.gap-item { display: flex; align-items: flex-start; gap: 8px; }
.gap-badge {
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  padding: 1px 7px; border-radius: 999px; flex-shrink: 0;
  letter-spacing: 0.05em; margin-top: 1px;
}
.gap-msg { font-size: 13px; color: #202124; line-height: 1.5; }

/* ── Trial cards ── */
.trial-card {
  background: #F8FBFF; border: 1px solid #C5D9F7; border-radius: 10px;
  padding: 12px 14px; margin-bottom: 10px;
}
.trial-card:last-child { margin-bottom: 0; }

.trial-card-top {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-bottom: 5px;
}
.trial-nct-link {
  font-family: 'Roboto Mono', monospace; font-size: 13px; font-weight: 600;
  color: #1967D2; text-decoration: none;
}
.trial-nct-link:hover { text-decoration: underline; }

.trial-status-badge {
  font-size: 10px; font-weight: 600; text-transform: uppercase;
  padding: 1px 7px; border-radius: 999px; letter-spacing: 0.05em;
  background: #E6F4EA; color: #137333;
}
.trial-title { font-size: 13px; color: #202124; margin-bottom: 6px; line-height: 1.45; }
.trial-eligibility {
  display: flex; align-items: flex-start; gap: 5px;
  font-size: 12px; color: #174EA6; margin-bottom: 5px; line-height: 1.45;
}
.trial-summary-text { font-size: 12px; color: #5F6368; line-height: 1.5; }

/* ── PubMed cards ── */
.pubmed-card {
  background: #F2FBF4; border: 1px solid #CEEAD6; border-radius: 10px;
  padding: 10px 14px; margin-bottom: 8px;
  display: flex; flex-direction: column; gap: 3px;
}
.pubmed-card:last-child { margin-bottom: 0; }
.pubmed-pmid-link {
  font-family: 'Roboto Mono', monospace; font-size: 12.5px; font-weight: 600;
  color: #137333; text-decoration: none;
}
.pubmed-pmid-link:hover { text-decoration: underline; }
.pubmed-source { font-size: 11px; color: #5F6368; }
.pubmed-title  { font-size: 12.5px; color: #202124; line-height: 1.45; }

/* ── History case cards ── */
.history-card {
  background: #F8F9FA; border: 1px solid #E8EAED; border-radius: 10px;
  padding: 12px 14px; margin-bottom: 10px;
}
.history-card:last-child { margin-bottom: 0; }
.history-card-id {
  font-family: 'Roboto Mono', monospace; font-size: 12px; font-weight: 600;
  color: #5F6368; margin-bottom: 8px;
}
.history-rationale {
  margin: 8px 0 0; font-size: 12.5px; color: #5F6368;
  line-height: 1.5; font-style: italic;
}

.modal-verified-banner {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 20px;
  background: #E6F4EA; color: #137333;
  font-size: 12px; font-weight: 500;
  border-top: 1px solid #CEEAD6; flex-shrink: 0;
}

/* ── Modal transition ── */
.modal-fade-enter-active,
.modal-fade-leave-active { transition: opacity 200ms, transform 200ms; }
.modal-fade-enter-from,
.modal-fade-leave-to { opacity: 0; transform: scale(0.97); }

/* ── Keyframes ── */
@keyframes scan-sweep {
  0%   { left: -90px; }
  65%  { left: calc(100% + 90px); }
  100% { left: calc(100% + 90px); }
}
@keyframes ring-expand {
  0%   { transform: scale(1);   opacity: 0.7; }
  100% { transform: scale(1.6); opacity: 0;   }
}
@keyframes icon-breathe {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.5; }
}
@keyframes dot-fade {
  0%, 60%, 100% { opacity: 0.25; }
  30%           { opacity: 1; }
}
</style>
