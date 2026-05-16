import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { streamPipeline } from '../services/api.js'

// ── Agent metadata ────────────────────────────────────────────────────────────

const AGENT_CONFIG = [
  { name: 'CaseCompiler',     icon: 'folder_open'    },
  { name: 'RadiologyAgent',   icon: 'image'          },
  { name: 'PathologyAgent',   icon: 'biotech'        },
  { name: 'GuidelineAgent',   icon: 'clinical_notes' },
  { name: 'TrialAgent',       icon: 'science'        },
  { name: 'HistoryCaseAgent', icon: 'history'        },
  { name: 'SummaryAgent',     icon: 'description'    },
]

function makeIdleAgents() {
  return AGENT_CONFIG.map(a => ({ ...a, status: 'idle', timestamp: null, output: null }))
}

// ── Output summary extraction ─────────────────────────────────────────────────

function _trunc(str, max) {
  if (!str) return null
  return str.length <= max ? str : str.slice(0, max) + '…'
}

function extractSummary(name, data) {
  if (!data || !Object.keys(data).length) return null
  switch (name) {
    case 'CaseCompiler': {
      const n = data.data_gaps?.length ?? 0
      return n ? `${n} data gap(s) flagged.` : 'All records present. Ready for review.'
    }
    case 'SummaryAgent':
      return _trunc(data.narrative, 140)
    case 'RadiologyAgent':
      return _trunc(data.radiologist_impression, 140)
    case 'PathologyAgent':
      return _trunc(data.synoptic_summary, 140)
    case 'GuidelineAgent':
      return `${data.matched_guideline ?? 'NCCN'} — ${data.guideline_pathway ?? ''}`
    case 'TrialAgent': {
      const n = data.matched_trials?.length ?? 0
      const note = _trunc(data.agent_notes, 80)
      return n ? `${n} recruiting trial(s) matched.${note ? ' ' + note : ''}` : (note ?? 'No trials matched.')
    }
    case 'HistoryCaseAgent': {
      const n = data.analogous_cases?.length ?? 0
      return n ? `${n} analogous case(s) found.` : 'No analogous cases found.'
    }
    default:
      return null
  }
}

// ── Store ─────────────────────────────────────────────────────────────────────

export const useAgentsStore = defineStore('agents', () => {
  // { [caseId]: Agent[] }
  const agentsByCaseId = ref({})
  // { [caseId]: 'idle' | 'running' | 'complete' | 'error' }
  const pipelineStatus = ref({})

  function initCase(caseId) {
    if (!agentsByCaseId.value[caseId]) {
      agentsByCaseId.value[caseId] = makeIdleAgents()
      pipelineStatus.value[caseId] = 'idle'
    }
  }

  function getForPatient(caseId) {
    return agentsByCaseId.value[caseId] ?? []
  }

  function getPipelineStatus(caseId) {
    return pipelineStatus.value[caseId] ?? 'idle'
  }

  async function runPipeline(caseId) {
    // Reset all agents to idle before starting
    agentsByCaseId.value[caseId] = makeIdleAgents()
    pipelineStatus.value[caseId] = 'running'

    try {
      for await (const { type, payload } of streamPipeline(caseId)) {
        if (type === 'agent') {
          const agents = agentsByCaseId.value[caseId]
          const agent = agents?.find(a => a.name === payload.agent)
          if (!agent) continue

          if (payload.status === 'running') {
            agent.status = 'running'
            agent.timestamp = null
            agent.output = null
          } else if (payload.status === 'done') {
            agent.status = 'complete'
            agent.timestamp = 'Just now'
            agent.output = extractSummary(payload.agent, payload.data)
          } else if (payload.status === 'error') {
            agent.status = 'error'
            agent.timestamp = 'Failed'
            agent.output = payload.data?.error ?? 'An error occurred.'
          }
        } else if (type === 'pipeline') {
          if (payload.status === 'complete') {
            pipelineStatus.value[caseId] = 'complete'
          } else if (payload.status === 'error') {
            pipelineStatus.value[caseId] = 'error'
          }
        }
      }
    } catch (err) {
      pipelineStatus.value[caseId] = 'error'
      // Mark any still-running agents as errored
      const agents = agentsByCaseId.value[caseId] ?? []
      for (const a of agents) {
        if (a.status === 'running') {
          a.status = 'error'
          a.timestamp = 'Connection lost'
          a.output = err.message
        }
      }
    }
  }

  // How many agents are running across all cases — used by App.vue topbar chip
  const runningCount = computed(() =>
    Object.values(agentsByCaseId.value)
      .flat()
      .filter(a => a.status === 'running').length,
  )

  // Backward-compat alias so any other caller of loadAgents still works
  const loadAgents = initCase

  return {
    agentsByCaseId,
    pipelineStatus,
    initCase,
    loadAgents,
    getForPatient,
    getPipelineStatus,
    runPipeline,
    runningCount,
  }
})
