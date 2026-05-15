import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getAgents } from '../services/api.js'

export const useAgentsStore = defineStore('agents', () => {
  // { [patientId]: Agent[] }
  const agentsByPatient = ref({})
  const loading = ref(false)

  async function loadAgents(patientId) {
    if (agentsByPatient.value[patientId]) return
    loading.value = true
    try {
      agentsByPatient.value[patientId] = await getAgents(patientId)
    } finally {
      loading.value = false
    }
  }

  function getForPatient(patientId) {
    return agentsByPatient.value[patientId] ?? []
  }

  const runningCount = computed(() =>
    Object.values(agentsByPatient.value).flat().filter(a => a.status === 'running').length
  )

  return { agentsByPatient, loading, loadAgents, getForPatient, runningCount }
})
