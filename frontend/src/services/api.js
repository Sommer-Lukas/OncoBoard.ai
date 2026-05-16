/**
 * API service layer — all data fetching lives here.
 *
 * Every function returns a Promise. Today they resolve with mock data.
 * To wire FastAPI: replace the mock body with a real fetch, e.g.
 *
 *   export async function getPatients() {
 *     const res = await fetch(`${BASE_URL}/patients`)
 *     return res.json()
 *   }
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export { BASE_URL }

// ─── Mock data ────────────────────────────────────────────────────────────────

const PATIENTS = [
  {
    id: 'PT-2024-08471',
    name: 'Sarah Mitchell',
    age: '52',
    stage: 'Stage IIB',
    receptors: 'ER+/PR+/HER2-',
    diagnosis: 'Grade 2 invasive ductal carcinoma, left breast',
    boardStatus: 'active',
  },
  {
    id: 'PT-2024-08469',
    name: 'Maria Rodriguez',
    age: '48',
    stage: 'Stage IIIA',
    receptors: 'ER-/PR-/HER2-',
    diagnosis: 'Triple-negative invasive ductal carcinoma, right breast',
    boardStatus: 'pending',
  },
  {
    id: 'PT-2024-08455',
    name: 'Jennifer Lee',
    age: '61',
    stage: 'Stage I',
    receptors: 'ER+/PR+/HER2-',
    diagnosis: 'Invasive lobular carcinoma, left breast',
    boardStatus: 'pending',
  },
  {
    id: 'PT-2024-08442',
    name: 'Patricia Johnson',
    age: '67',
    stage: 'Stage IIA',
    receptors: 'ER+/PR-/HER2+',
    diagnosis: 'HER2-positive invasive ductal carcinoma, left breast',
    boardStatus: 'complete',
  },
]

const CASE_DATA = {
  'PT-2024-08471': {
    presentation: '2.1cm irregular mass at 10:00 position with suspicious microcalcifications. Palpable axillary lymphadenopathy.',
    previousTreatment: 'Lumpectomy with sentinel lymph node biopsy performed 2024-04-20. Margins clear. 1/3 sentinel nodes positive for metastatic disease.',
    radiology: 'Mammography shows BI-RADS 4 lesion with irregular margins and associated architectural distortion. MRI confirms single 2.1cm enhancing mass with no additional suspicious lesions. Axillary ultrasound demonstrates enlarged lymph node measuring 1.8cm with loss of fatty hilum.',
    pathology: 'Invasive ductal carcinoma, grade 2. Tumor size 2.1cm. ER positive (90%), PR positive (70%), HER2 IHC 1+ (negative). Ki-67 22%. Sentinel lymph node 1/3 positive, largest deposit 0.8cm with extranodal extension.',
    guidelines: 'NCCN: Node-positive hormone receptor-positive, HER2-negative disease with intermediate-high risk warrants adjuvant chemotherapy followed by endocrine therapy. Recommended: TC × 4 cycles → tamoxifen or aromatase inhibitor × 5-10 years.',
    trials: 'NCT05234567: Phase III, chemo + endocrine vs endocrine alone in intermediate-risk node-positive HR+/HER2- breast cancer. Patient meets eligibility (age 18-70, 1-3 positive nodes, ER ≥10%, HER2-). Currently enrolling.',
    dataGaps: [
      { message: 'CT chest from 2024-04-15 not found in system. Contact radiology to upload before meeting.' },
    ],
    boardHistory: 'Previous board (March 15, 2024) recommended lumpectomy with SLNB. Completed April 20, 2024.',
  },
  'PT-2024-08469': {
    presentation: '3.4cm palpable mass, right breast 2:00. Clinically palpable ipsilateral axillary nodes.',
    previousTreatment: 'Core needle biopsy 2024-05-02. No prior breast surgery.',
    radiology: 'MRI: 3.4cm irregular enhancing mass with satellite lesions. Three morphologically abnormal axillary lymph nodes, largest 2.3cm.',
    pathology: 'Triple-negative invasive ductal carcinoma, grade 3. Ki-67 78%. No HER2 amplification by FISH. BRCA1/2 pending.',
    guidelines: 'NCCN: Neoadjuvant chemotherapy (AC-T) preferred for Stage III TNBC. Pathologic complete response guides further management. Olaparib maintenance if BRCA-mutated.',
    trials: 'NCT04976335: Neoadjuvant immunotherapy + chemo for Stage II/III TNBC. Patient potentially eligible pending PD-L1 status.',
    dataGaps: [
      { message: 'BRCA1/2 germline testing result pending — expected May 15, 2026.' },
      { message: 'PD-L1 IHC not yet performed. Required for trial eligibility NCT04976335.' },
    ],
    boardHistory: 'First presentation to this board.',
  },
  'PT-2024-08455': {
    presentation: '0.8cm non-palpable lesion detected on screening mammography.',
    previousTreatment: 'Lumpectomy 2023-08-10. Margins clear. SLNB negative. Oncotype DX RS 14.',
    radiology: 'Follow-up mammography stable. No new suspicious lesions. Clip in situ.',
    pathology: 'Invasive lobular carcinoma, grade 1. 0.8cm. ER 95%, PR 85%, HER2 negative. Ki-67 8%. Oncotype DX RS 14 (low risk).',
    guidelines: 'NCCN: Low Oncotype DX score in node-negative HR+ disease supports endocrine therapy alone. Letrozole for postmenopausal patients × 5 years. Annual mammographic surveillance.',
    trials: 'No active trials match current profile. Low-risk profile does not favour additional systemic therapy.',
    dataGaps: [],
    boardHistory: 'Presented 2023-09-01. Decision: lumpectomy + radiation + endocrine therapy. Re-presented today for annual surveillance review.',
  },
  'PT-2024-08442': {
    presentation: '1.9cm palpable mass, left breast 9:00. No palpable adenopathy.',
    previousTreatment: 'Diagnostic workup in progress. No prior surgery.',
    radiology: 'BI-RADS 5: 1.9cm irregular mass with spiculated margins. No suspicious axillary nodes on ultrasound.',
    pathology: 'Invasive ductal carcinoma, grade 2. ER positive (80%), PR negative, HER2 IHC 3+ (positive). Ki-67 35%.',
    guidelines: 'NCCN: HER2-positive early breast cancer. Standard: neoadjuvant pertuzumab + trastuzumab + chemotherapy (TCHP) vs adjuvant approach depending on staging.',
    trials: 'NCT05112328: Neoadjuvant T-DM1 + pertuzumab for HER2+ early breast cancer. Screening in progress.',
    dataGaps: [
      { message: 'Staging CT chest/abdomen/pelvis pending — scheduled May 16, 2026.' },
    ],
    boardHistory: 'First presentation to this board.',
  },
}

const AGENTS = {
  'PT-2024-08471': [
    { name: 'CaseCompiler',    icon: 'folder_open',    status: 'complete', timestamp: 'Completed 2 min ago', output: 'All records retrieved. Flagged: Missing CT chest from 2024-04-15.' },
    { name: 'SummaryAgent',    icon: 'description',    status: 'complete', timestamp: 'Completed 1 min ago', output: '52yo female, Stage IIB invasive ductal carcinoma. ER+/PR+/HER2-. Considering adjuvant chemo vs endocrine therapy alone.' },
    { name: 'RadiologyAgent',  icon: 'image',          status: 'complete', timestamp: 'Completed 3 min ago', output: 'BI-RADS 4: 2.1cm irregular mass, left breast 10:00, suspicious microcalcifications. Enlarged axillary node 1.8cm.' },
    { name: 'PathologyAgent',  icon: 'biotech',        status: 'complete', timestamp: 'Completed 2 min ago', output: 'Grade 2 IDC. ER 90%, PR 70%, HER2 IHC 1+ (negative). Ki-67 22%. 1/3 sentinel nodes positive.' },
    { name: 'GuidelineAgent',  icon: 'clinical_notes', status: 'complete', timestamp: 'Completed 1 min ago', output: 'NCCN match: Node-positive HR+ breast cancer. Recommends chemo + endocrine therapy for intermediate-high risk.' },
    { name: 'TrialAgent',      icon: 'science',        status: 'running',  timestamp: 'Running…',            output: null },
    { name: 'HistoryCaseAgent',icon: 'history',        status: 'complete', timestamp: 'Completed 4 min ago', output: '3 analogous cases found. 2/3 received TC + tamoxifen. 5yr DFS 87%.' },
  ],
  'PT-2024-08469': [
    { name: 'CaseCompiler',    icon: 'folder_open',    status: 'complete', timestamp: 'Completed 5 min ago', output: 'Records retrieved. Flagged: BRCA result pending, PD-L1 not performed.' },
    { name: 'SummaryAgent',    icon: 'description',    status: 'complete', timestamp: 'Completed 4 min ago', output: '48yo female, Stage IIIA triple-negative IDC. Ki-67 78%. No prior treatment.' },
    { name: 'RadiologyAgent',  icon: 'image',          status: 'complete', timestamp: 'Completed 6 min ago', output: 'MRI: 3.4cm mass + satellite lesions. Three morphologically abnormal axillary nodes, largest 2.3cm.' },
    { name: 'PathologyAgent',  icon: 'biotech',        status: 'complete', timestamp: 'Completed 5 min ago', output: 'Grade 3 TNBC. Ki-67 78%. BRCA1/2 pending. PD-L1 not yet performed.' },
    { name: 'GuidelineAgent',  icon: 'clinical_notes', status: 'complete', timestamp: 'Completed 3 min ago', output: 'NCCN: Neoadjuvant AC-T preferred. Olaparib maintenance if BRCA-mutated.' },
    { name: 'TrialAgent',      icon: 'science',        status: 'complete', timestamp: 'Completed 4 min ago', output: 'NCT04976335 potentially eligible pending PD-L1 status. Trial enrolling.' },
    { name: 'HistoryCaseAgent',icon: 'history',        status: 'complete', timestamp: 'Completed 7 min ago', output: 'First presentation. No prior board history for this patient.' },
  ],
  'PT-2024-08455': [
    { name: 'CaseCompiler',    icon: 'folder_open',    status: 'complete', timestamp: 'Completed 1 min ago', output: 'All records present. No data gaps.' },
    { name: 'SummaryAgent',    icon: 'description',    status: 'complete', timestamp: 'Completed 1 min ago', output: '61yo female, Stage I ILC. Post-lumpectomy 2023. Oncotype DX RS 14. Currently on letrozole year 2.' },
    { name: 'RadiologyAgent',  icon: 'image',          status: 'complete', timestamp: 'Completed 2 min ago', output: 'Follow-up mammography stable. No new lesions. Clip in situ.' },
    { name: 'PathologyAgent',  icon: 'biotech',        status: 'complete', timestamp: 'Completed 1 min ago', output: 'Grade 1 ILC. ER 95%, PR 85%, HER2-. Ki-67 8%. Oncotype DX RS 14.' },
    { name: 'GuidelineAgent',  icon: 'clinical_notes', status: 'complete', timestamp: 'Completed 1 min ago', output: 'NCCN: Low RS supports endocrine therapy alone. Letrozole × 5 years. Annual surveillance.' },
    { name: 'TrialAgent',      icon: 'science',        status: 'complete', timestamp: 'Completed 2 min ago', output: 'No matching trials. Low-risk profile does not favour additional systemic therapy.' },
    { name: 'HistoryCaseAgent',icon: 'history',        status: 'complete', timestamp: 'Completed 1 min ago', output: 'Prior board Sep 2023: lumpectomy + radiation + endocrine therapy. Good response.' },
  ],
  'PT-2024-08442': [
    { name: 'CaseCompiler',    icon: 'folder_open',    status: 'complete', timestamp: 'Completed 3 min ago', output: 'Records retrieved. Flagged: Staging CT pending.' },
    { name: 'SummaryAgent',    icon: 'description',    status: 'complete', timestamp: 'Completed 2 min ago', output: '67yo female, Stage IIA HER2+ IDC. No prior treatment. Staging workup in progress.' },
    { name: 'RadiologyAgent',  icon: 'image',          status: 'complete', timestamp: 'Completed 3 min ago', output: 'BI-RADS 5: 1.9cm spiculated mass. No suspicious axillary nodes on ultrasound.' },
    { name: 'PathologyAgent',  icon: 'biotech',        status: 'complete', timestamp: 'Completed 2 min ago', output: 'Grade 2 IDC. ER 80%, PR-, HER2 IHC 3+ (positive). Ki-67 35%.' },
    { name: 'GuidelineAgent',  icon: 'clinical_notes', status: 'running',  timestamp: 'Running…',            output: null },
    { name: 'TrialAgent',      icon: 'science',        status: 'idle',     timestamp: null,                  output: null },
    { name: 'HistoryCaseAgent',icon: 'history',        status: 'complete', timestamp: 'Completed 4 min ago', output: 'First presentation to this board.' },
  ],
}

const POST_MEETING = {
  'PT-2024-08471': {
    completedDate: 'May 13, 2026 2:45 PM',
    recommendation: 'Adjuvant chemotherapy (TC × 4 cycles) followed by endocrine therapy (tamoxifen × 5-10 years) and radiation therapy (whole breast + regional nodes).',
    rationale: 'Node-positive HR+ breast cancer with extranodal extension and Ki-67 22%. Standard of care per NCCN. Patient declined trial enrollment.',
    actions: [
      { description: 'Schedule chemotherapy planning appointment', owner: 'Dr. Chen',        dueDate: 'May 15, 2026', status: 'pending' },
      { description: 'Order baseline labs (CBC, CMP, LFTs)',       owner: 'Dr. Chen',        dueDate: 'May 16, 2026', status: 'pending' },
      { description: 'Radiation oncology consultation',            owner: 'Dr. Patel',       dueDate: 'May 20, 2026', status: 'pending' },
      { description: 'Discuss ovarian suppression options',        owner: 'Dr. Chen',        dueDate: 'May 22, 2026', status: 'pending' },
      { description: 'Send tumor board note to primary care',      owner: 'Medical Records', dueDate: 'May 14, 2026', status: 'pending' },
    ],
    note: `TUMOR BOARD DISCUSSION
Patient: Sarah Mitchell (PT-2024-08471) — May 13, 2026

RECOMMENDATION:
TC chemotherapy × 4 cycles → tamoxifen × 5-10 years + whole breast radiation with regional nodal irradiation.

RATIONALE:
Node-positive, ER+/PR+/HER2- breast cancer with extranodal extension and Ki-67 22% indicates elevated recurrence risk. NCCN standard of care. Patient declined trial enrollment.`,
  },
  'PT-2024-08469': {
    completedDate: 'May 13, 2026 3:10 PM',
    recommendation: 'Neoadjuvant chemotherapy (AC-T regimen) followed by surgical reassessment. BRCA-guided maintenance therapy to follow.',
    rationale: 'Stage IIIA TNBC with bulky nodal disease. Neoadjuvant approach allows pCR assessment and may improve surgical outcomes. BRCA1/2 testing ordered.',
    actions: [
      { description: 'BRCA1/2 genetic testing referral',          owner: 'Dr. Kim',         dueDate: 'May 16, 2026', status: 'pending' },
      { description: 'Port placement for chemotherapy',            owner: 'Dr. Kim',         dueDate: 'May 17, 2026', status: 'pending' },
      { description: 'Baseline cardiac echo before anthracycline', owner: 'Dr. Chen',        dueDate: 'May 18, 2026', status: 'pending' },
      { description: 'Send tumor board note to primary care',      owner: 'Medical Records', dueDate: 'May 14, 2026', status: 'pending' },
    ],
    note: `TUMOR BOARD DISCUSSION
Patient: Maria Rodriguez (PT-2024-08469) — May 13, 2026

RECOMMENDATION:
Neoadjuvant AC-T chemotherapy. Reassess with MRI after 4 cycles. BRCA testing ordered. Surgical planning pending response.

RATIONALE:
Stage IIIA TNBC. Neoadjuvant preferred to assess pCR. Olaparib maintenance if BRCA-mutated.`,
  },
  'PT-2024-08455': {
    completedDate: 'May 13, 2026 3:35 PM',
    recommendation: 'Continue letrozole. Active surveillance with 6-month follow-up imaging. No change in systemic therapy.',
    rationale: 'Stable Stage I ER+/HER2- ILC on endocrine therapy. Oncotype DX RS 14 confirms low risk. No progression on imaging.',
    actions: [
      { description: 'Follow-up mammography in 6 months',         owner: 'Dr. Lee',         dueDate: 'Nov 13, 2026', status: 'pending' },
      { description: 'Annual bone density scan (DEXA)',            owner: 'Dr. Chen',        dueDate: 'Jun 1, 2026',  status: 'pending' },
      { description: 'Confirm letrozole adherence at next visit',  owner: 'Dr. Chen',        dueDate: 'Jun 15, 2026', status: 'pending' },
    ],
    note: `TUMOR BOARD DISCUSSION
Patient: Jennifer Lee (PT-2024-08455) — May 13, 2026

RECOMMENDATION:
Continue letrozole. Surveillance mammography every 6 months. No additional systemic therapy indicated.

RATIONALE:
Low Oncotype DX score (RS 14) in node-negative HR+ disease. Stable on endocrine therapy. No progression.`,
  },
  'PT-2024-08442': null, // not yet discussed
}

// ─── Field mapping ────────────────────────────────────────────────────────────

function fmtReceptor(status, pos, neg) {
  return status === 'Positive' ? pos : status === 'Negative' ? neg : null
}

function receptorString(c) {
  return [
    fmtReceptor(c.er_status,   'ER+', 'ER-'),
    fmtReceptor(c.pr_status,   'PR+', 'PR-'),
    fmtReceptor(c.her2_status, 'HER2+', 'HER2-'),
  ].filter(Boolean).join('/') || '—'
}

function mapApiCase(c) {
  return {
    id: c.case_id,
    name: c.case_id,
    age: c.age_at_diagnosis ?? '—',
    stage: c.ajcc_stage ?? '—',
    receptors: receptorString(c),
    diagnosis: [c.histological_type, c.molecular_subtype].filter(Boolean).join(' · ') || '—',
    boardStatus: 'pending',
    molecular_subtype: c.molecular_subtype,
  }
}

// Derive clinical narrative text from structured TCGA fields.
// These are the same fields the real agents will read from the DB.
// TCGA stores TNM values with their prefix already included (e.g. "T1c", "N0 (i-)").
// Pipe chars in anatomic subdivisions are raw DB notation — normalise to a slash.
function cleanLocation(raw) {
  return raw ? raw.replace(/\|/g, ' / ') : 'unspecified location'
}

function mapApiCaseFull(c) {
  const base = mapApiCase(c)

  const location = cleanLocation(c.anatomic_subdivision)

  // ── Presentation ──
  const tumourStatus = c.tumor_status === 'WITH TUMOR' ? 'Active disease.' : (c.tumor_status === 'TUMOR FREE' ? 'Tumour free.' : (c.tumor_status ?? ''))
  const tnm = [c.ajcc_t, c.ajcc_n, c.ajcc_m].filter(Boolean).join(' ')
  const presentation = [
    `${c.histological_type ?? 'Breast tumour'}, ${location}.`,
    c.ajcc_stage ? `${c.ajcc_stage}${tnm ? ' (' + tnm + ')' : ''}.` : '',
    tumourStatus,
    c.menopause_status ? `Menopause: ${c.menopause_status.split('(')[0].trim()}.` : '',
  ].filter(Boolean).join(' ')

  // ── Previous treatment ──
  const drugs = c.treatments?.drugs?.join(', ')
  const surgery = c.surgical_procedure ?? c.treatments?.surgery
  const nodes = c.lymph_nodes_examined != null ? `${c.lymph_nodes_examined} lymph node(s) examined.` : ''
  const margins = c.margin_status ? `Margins: ${c.margin_status}.` : ''
  const previousTreatment = [
    surgery ? `Surgery: ${surgery}.` : 'No prior surgical record.',
    drugs ? `Systemic therapy: ${drugs}.` : '',
    nodes,
    margins,
  ].filter(Boolean).join(' ') || 'No prior treatment recorded.'

  // ── Pathology ──
  const her2Detail = c.her2_ihc_score ? ` (IHC ${c.her2_ihc_score})` : ''
  const pathology = [
    `${c.histological_type ?? 'Breast carcinoma'}.`,
    `Receptor status: ER ${c.er_status ?? '?'}, PR ${c.pr_status ?? '?'}, HER2 ${c.her2_status ?? '?'}${her2Detail}.`,
    c.molecular_subtype ? `Molecular subtype: ${c.molecular_subtype}.` : '',
    'Genomic copy-number data available via the genomics panel.',
  ].filter(Boolean).join(' ')

  // ── Radiology — no agent-generated content; RadiologyAgent fills this in ──
  const radiology = null

  // ── Data gaps ──
  const dataGaps = []
  if (!c.molecular_subtype) dataGaps.push({ message: 'Molecular subtype unclassified — ER/PR/HER2 IHC data may be incomplete.' })
  if (!c.ajcc_stage || c.ajcc_stage === 'Stage X') dataGaps.push({ message: 'AJCC stage is unknown or unresolved — staging workup may be incomplete.' })
  if (!c.her2_ihc_score && c.her2_status === 'Positive') dataGaps.push({ message: 'HER2 IHC score not recorded — FISH confirmation recommended.' })

  return {
    ...base,
    presentation,
    previousTreatment,
    pathology,
    radiology,          // null until RadiologyAgent runs
    guidelines: null,   // null until GuidelineAgent runs
    trials: null,       // null until TrialAgent runs
    dataGaps,
    boardHistory: 'TCGA research case. No prior board session recorded in this system.',
  }
}

// ─── API functions ────────────────────────────────────────────────────────────

export async function getPatients({ limit = 4, subtype = null, hasData = true } = {}) {
  const params = new URLSearchParams({ limit })
  if (subtype) params.set('subtype', subtype)
  if (hasData) params.set('has_data', 'true')
  const res = await fetch(`${BASE_URL}/cases?${params}`)
  if (!res.ok) throw new Error(`GET /cases failed: ${res.status}`)
  const data = await res.json()
  return data.items.map(mapApiCase)
}

export async function getPatient(id) {
  const res = await fetch(`${BASE_URL}/cases/${encodeURIComponent(id)}`)
  if (!res.ok) throw new Error(`Case ${id} not found`)
  const c = await res.json()
  return mapApiCaseFull(c)
}

export async function getAgents(patientId) {
  return structuredClone(AGENTS[patientId] ?? [])
}

export async function getPostMeeting(patientId) {
  return structuredClone(POST_MEETING[patientId] ?? null)
}

export function imageUrl(path) {
  return `${BASE_URL}${path}`
}

export async function getPatientImages(id, type = 'mri') {
  const res = await fetch(`${BASE_URL}/cases/${encodeURIComponent(id)}/images?type=${type}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.images ?? []
}

export async function getCaseGenomics(id, genes) {
  const params = new URLSearchParams()
  if (genes?.length) params.set('genes', genes.join(','))
  const res = await fetch(`${BASE_URL}/cases/${encodeURIComponent(id)}/genomics?${params}`)
  if (!res.ok) throw new Error(`GET /cases/${id}/genomics failed: ${res.status}`)
  const data = await res.json()
  if (!data.has_data) throw new Error('No genomic data available for this case.')
  return data
}

/**
 * Stream the pre-meeting pipeline for a case via SSE.
 * Yields { type: 'agent'|'pipeline', payload: {...} } objects.
 * The caller can `for await` over this async generator.
 */
export async function* streamPipeline(caseId) {
  const response = await fetch(
    `${BASE_URL}/cases/${encodeURIComponent(caseId)}/pre-meeting/run`,
    { method: 'POST', headers: { Accept: 'text/event-stream' } },
  )
  if (!response.ok) {
    const body = await response.text().catch(() => '')
    throw new Error(`Pipeline request failed (${response.status})${body ? ': ' + body : ''}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventType = ''
  let eventData = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          eventData = line.slice(6).trim()
        } else if (line === '' && eventType && eventData) {
          try { yield { type: eventType, payload: JSON.parse(eventData) } } catch {}
          eventType = ''
          eventData = ''
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function saveNote(patientId, noteContent) {
  // TODO: PUT ${BASE_URL}/patients/${patientId}/note
  console.log(`[api] saveNote(${patientId})`, noteContent)
}

export async function updateActionStatus(patientId, actionIndex, status) {
  // TODO: PATCH ${BASE_URL}/patients/${patientId}/actions/${actionIndex}
  console.log(`[api] updateActionStatus(${patientId}, ${actionIndex}, ${status})`)
}
