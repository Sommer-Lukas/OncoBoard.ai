import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getPatients, getPatient, getPostMeeting } from '../services/api.js'

export const usePatientsStore = defineStore('patients', () => {
  const patients = ref([])
  const activeId = ref(null)

  // Caches so we don't re-fetch on every tab switch
  const caseCache = ref({})
  const postMeetingCache = ref({})

  const loading = ref(false)
  const error = ref(null)

  const activePatient = computed(() =>
    patients.value.find(p => p.id === activeId.value) ?? null
  )

  async function loadPatients() {
    loading.value = true
    error.value = null
    try {
      patients.value = await getPatients()
      if (!activeId.value && patients.value.length) {
        activeId.value = patients.value[0].id
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function loadCaseData(id) {
    if (caseCache.value[id]) return caseCache.value[id]
    const data = await getPatient(id)
    caseCache.value[id] = data
    return data
  }

  async function loadPostMeeting(id) {
    if (postMeetingCache.value[id] !== undefined) return postMeetingCache.value[id]
    const data = await getPostMeeting(id)
    postMeetingCache.value[id] = data
    return data
  }

  function setActive(id) {
    activeId.value = id
  }

  return {
    patients,
    activeId,
    activePatient,
    loading,
    error,
    loadPatients,
    loadCaseData,
    loadPostMeeting,
    setActive,
  }
})
