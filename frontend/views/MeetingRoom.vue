<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import PatientSelector from '../components/PatientSelector.vue'
import CaseDisplay from '../components/CaseDisplay.vue'
import LiveTranscriptPanel from '../components/LiveTranscriptPanel.vue'
import { usePatientsStore } from '../src/stores/patients.js'

const router = useRouter()
const store = usePatientsStore()

const caseData = ref(null)

onMounted(async () => {
  await store.loadPatients()
  await loadCase()
})

watch(() => store.activeId, loadCase)

async function loadCase() {
  if (!store.activeId) return
  caseData.value = await store.loadCaseData(store.activeId)
}
</script>

<template>
  <div class="meeting-shell">

    <div class="meeting-topbar">
      <div class="topbar-left">
        <button class="icon-btn" title="Back to dashboard" @click="router.push('/')">
          <span class="material-symbols-outlined" style="font-size: 20px; color: #5F6368">arrow_back</span>
        </button>
        <span class="material-symbols-outlined brand-icon">ecg_heart</span>
        <span class="topbar-title">Meeting Room</span>
        <div class="live-chip">
          <span class="live-dot"></span>
          Live
        </div>
      </div>
      <div class="topbar-right">
        <button class="end-btn" @click="router.push('/post-meeting')">
          <span class="material-symbols-outlined" style="font-size: 16px">meeting_room</span>
          End Meeting
        </button>
      </div>
    </div>

    <div class="columns">
      <PatientSelector
        :patients="store.patients"
        :active-id="store.activeId"
        @select="store.setActive($event)"
      />
      <div class="main-content">
        <CaseDisplay v-if="caseData" :case-data="caseData" />
        <div v-else class="loading-state">
          <span class="material-symbols-outlined" style="font-size: 40px; color: #DADCE0">hourglass_empty</span>
          <div>Loading case data…</div>
        </div>
      </div>
      <LiveTranscriptPanel />
    </div>

  </div>
</template>

<style scoped>
.meeting-shell {
  display: flex; flex-direction: column;
  height: 100vh; overflow: hidden; background: #F8F9FA;
}

.meeting-topbar {
  height: 52px; background: #fff; border-bottom: 1px solid #DADCE0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; flex-shrink: 0; z-index: 10;
}

.topbar-left  { display: flex; align-items: center; gap: 12px; }
.topbar-right { display: flex; align-items: center; gap: 10px; }

.icon-btn {
  width: 36px; height: 36px; border-radius: 50%; border: none;
  background: transparent; cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: background 150ms;
}
.icon-btn:hover { background: #F8F9FA; }

.brand-icon    { font-size: 20px; color: #1A73E8; }
.topbar-title  { font-size: 15px; font-weight: 500; color: #202124; }

.live-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 10px; border-radius: 999px;
  background: #FCE8E6; color: #C5221F; font-size: 12px; font-weight: 500;
}
.live-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #EA4335;
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.3; } }

.end-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 16px; border-radius: 999px; border: none;
  background: #EA4335; color: #fff; font-size: 13px; font-weight: 500;
  cursor: pointer; font-family: 'Roboto', sans-serif; transition: background 150ms;
}
.end-btn:hover { background: #c5221f; }

.columns { flex: 1; display: flex; overflow: hidden; }

.main-content {
  flex: 1; overflow: hidden; display: flex;
  flex-direction: column; background: #F8F9FA;
}

.loading-state {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px; font-size: 14px; color: #80868B;
}
</style>
