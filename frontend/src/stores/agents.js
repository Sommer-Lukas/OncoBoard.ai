import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { streamPipeline, streamPostMeetingPipeline } from '../services/api.js'

// ── Agent metadata ────────────────────────────────────────────────────────────

const POST_AGENT_CONFIG = [
  { name: 'NoteDraftAgent',      icon: '/agents/11_notedraftagent.png'     },
  { name: 'ActionDispatchAgent', icon: '/agents/12_actiondispatchagent.png' },
  { name: 'FollowUpAgent',       icon: '/agents/13_followupagent.png'      },
  { name: 'SchedulingAgent',     icon: '/agents/14_schedulingagent.png'    },
]

const AGENT_CONFIG = [
  { name: 'CaseCompiler',     icon: '/agents/01_casecompiler.png'     },
  { name: 'RadiologyAgent',   icon: '/agents/03_radiologyagent.png'   },
  { name: 'PathologyAgent',   icon: '/agents/04_pathologyagent.png'   },
  { name: 'GuidelineAgent',   icon: '/agents/05_guidelineagent.png'   },
  { name: 'TrialAgent',       icon: '/agents/06_trialagent.png'       },
  { name: 'HistoryCaseAgent', icon: '/agents/07_historycaseagent.png' },
  { name: 'SummaryAgent',     icon: '/agents/02_summaryagent.png'     },
]

function makeIdleAgents() {
  return AGENT_CONFIG.map(a => ({ ...a, status: 'idle', timestamp: null, output: null }))
}

function makeIdlePostAgents() {
  return POST_AGENT_CONFIG.map(a => ({ ...a, status: 'idle', timestamp: null, output: null }))
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

function _extractErrorDetail(msg) {
  if (!msg) return 'Pipeline request failed.'
  const jsonMatch = msg.match(/(\{.*\})$/)
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[1])
      if (parsed.detail) return parsed.detail
    } catch {}
  }
  return msg
}

function extractPostSummary(name, data) {
  if (!data || !Object.keys(data).length) return null
  switch (name) {
    case 'NoteDraftAgent':
      return _trunc(data.consensus_plan, 140)
    case 'ActionDispatchAgent': {
      const n = data.actions_created?.length ?? 0
      const s = _trunc(data.dispatch_summary, 80)
      return n ? `${n} action${n !== 1 ? 's' : ''} dispatched.${s ? ' ' + s : ''}` : (s ?? 'No actions dispatched.')
    }
    case 'FollowUpAgent': {
      const total = data.total_actions ?? 0
      const done  = data.completed_actions ?? 0
      const over  = data.overdue_actions?.length ?? 0
      const note  = _trunc(data.escalation_notes, 80)
      return `${total} action${total !== 1 ? 's' : ''}: ${done} complete${over ? ', ' + over + ' overdue' : ''}.${note ? ' ' + note : ''}`
    }
    case 'SchedulingAgent': {
      if (data.needs_representation) {
        return `Re-presentation required${data.suggested_timeframe ? ' in ' + data.suggested_timeframe : ''}.${data.rationale ? ' ' + _trunc(data.rationale, 80) : ''}`
      }
      return `No re-presentation required. ${_trunc(data.rationale, 100) ?? ''}`
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
  // { [caseId]: { [agentName]: rawData } } — full structured output per agent
  const rawDataByCaseId = ref({})

  function initCase(caseId) {
    if (!agentsByCaseId.value[caseId]) {
      agentsByCaseId.value[caseId] = makeIdleAgents()
      pipelineStatus.value[caseId] = 'idle'
    }
    if (!rawDataByCaseId.value[caseId]) {
      rawDataByCaseId.value[caseId] = {}
    }
  }

  function getForPatient(caseId) {
    return agentsByCaseId.value[caseId] ?? []
  }

  function getPipelineStatus(caseId) {
    return pipelineStatus.value[caseId] ?? 'idle'
  }

  function getAgentRawData(caseId) {
    return rawDataByCaseId.value[caseId] ?? {}
  }

  async function runPipeline(caseId) {
    // Reset all agents to idle before starting
    agentsByCaseId.value[caseId] = makeIdleAgents()
    rawDataByCaseId.value[caseId] = {}
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
            // Store full structured output so MeetingRoom can use it
            if (payload.data) {
              rawDataByCaseId.value[caseId][payload.agent] = payload.data
            }
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

  // ── Post-meeting pipeline ─────────────────────────────────────────────────

  const postAgentsByCaseId  = ref({})   // { [caseId]: Agent[] }
  const postPipelineStatus  = ref({})   // { [caseId]: 'idle'|'running'|'complete'|'error' }
  const postRawDataByCaseId = ref({})   // { [caseId]: { [agentName]: rawData } }
  const postPipelineError   = ref({})   // { [caseId]: string | null }

  function initPostCase(caseId) {
    if (!postAgentsByCaseId.value[caseId]) {
      postAgentsByCaseId.value[caseId] = makeIdlePostAgents()
      postPipelineStatus.value[caseId] = 'idle'
    }
    if (!postRawDataByCaseId.value[caseId]) {
      postRawDataByCaseId.value[caseId] = {}
    }
  }

  function getPostAgents(caseId) {
    return postAgentsByCaseId.value[caseId] ?? []
  }

  function getPostPipelineStatus(caseId) {
    return postPipelineStatus.value[caseId] ?? 'idle'
  }

  function getPostRawData(caseId) {
    return postRawDataByCaseId.value[caseId] ?? {}
  }

  function getPostPipelineError(caseId) {
    return postPipelineError.value[caseId] ?? null
  }

  async function runPostPipeline(caseId, sessionId) {
    postAgentsByCaseId.value[caseId] = makeIdlePostAgents()
    postRawDataByCaseId.value[caseId] = {}
    postPipelineStatus.value[caseId] = 'running'
    postPipelineError.value[caseId]  = null

    try {
      for await (const { type, payload } of streamPostMeetingPipeline(sessionId)) {
        if (type === 'agent') {
          const agentList = postAgentsByCaseId.value[caseId]
          const agent = agentList?.find(a => a.name === payload.agent)
          if (!agent) continue

          if (payload.status === 'running') {
            agent.status = 'running'
            agent.timestamp = null
            agent.output = null
          } else if (payload.status === 'done') {
            agent.status = 'complete'
            agent.timestamp = 'Just now'
            agent.output = extractPostSummary(payload.agent, payload.data)
            if (payload.data) {
              postRawDataByCaseId.value[caseId][payload.agent] = payload.data
            }
          } else if (payload.status === 'error') {
            agent.status = 'error'
            agent.timestamp = 'Failed'
            agent.output = payload.data?.error ?? 'An error occurred.'
          }
        } else if (type === 'pipeline') {
          if (payload.status === 'complete') {
            postPipelineStatus.value[caseId] = 'complete'
          } else if (payload.status === 'error') {
            postPipelineStatus.value[caseId] = 'error'
            postPipelineError.value[caseId] = payload.data?.error ?? 'Pipeline failed.'
          }
        }
      }
    } catch (err) {
      const message = _extractErrorDetail(err.message)
      postPipelineStatus.value[caseId] = 'error'
      postPipelineError.value[caseId]  = message
      // Mark every agent (including idle ones) as errored so the cards go red
      const agentList = postAgentsByCaseId.value[caseId] ?? []
      for (const a of agentList) {
        a.status    = 'error'
        a.timestamp = 'Failed'
        a.output    = message
      }
    }
  }

  const postRunningCount = computed(() =>
    Object.values(postAgentsByCaseId.value)
      .flat()
      .filter(a => a.status === 'running').length,
  )

  // Backward-compat alias so any other caller of loadAgents still works
  const loadAgents = initCase

  return {
    agentsByCaseId,
    pipelineStatus,
    rawDataByCaseId,
    initCase,
    loadAgents,
    getForPatient,
    getPipelineStatus,
    getAgentRawData,
    runPipeline,
    runningCount,
    postAgentsByCaseId,
    postPipelineStatus,
    postRawDataByCaseId,
    initPostCase,
    getPostAgents,
    getPostPipelineStatus,
    getPostPipelineError,
    getPostRawData,
    runPostPipeline,
    postRunningCount,
  }
})
