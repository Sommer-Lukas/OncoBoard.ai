import { defineStore } from 'pinia'
import { ref } from 'vue'
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

  return { agentsByPatient, loading, loadAgents, getForPatient }
})
