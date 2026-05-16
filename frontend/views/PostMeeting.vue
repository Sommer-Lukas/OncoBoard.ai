<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import CaseOutcome from '../components/CaseOutcome.vue'
import ActionTrackerTable from '../components/ActionTrackerTable.vue'
import NoteDraft from '../components/NoteDraft.vue'
import { usePatientsStore } from '../src/stores/patients.js'
import { useMeetingStore } from '../src/stores/meeting.js'
import { saveNote } from '../src/services/api.js'

const router = useRouter()
const store = usePatientsStore()
const meeting = useMeetingStore()

const postData = ref(null)

onMounted(async () => {
  await store.loadPatients()
  await loadPost()
})

watch(() => store.activeId, loadPost)

async function loadPost() {
  if (!store.activeId) return
  postData.value = await store.loadPostMeeting(store.activeId)
}

async function handleSaveNote(content) {
  await saveNote(store.activeId, content)
}

const statusColor = { complete: '#34A853', pending: '#FBBC04' }

function patientPostStatus(id) {
  if (meeting.isDiscussed(id)) return 'complete'
  return store.patients.find(p => p.id === id)?.boardStatus === 'complete' ? 'complete' : 'pending'
}
</script>

<template>
  <div class="post-shell">

    <div class="post-topbar">
      <div class="topbar-left">
        <button class="icon-btn" @click="router.push('/')">
          <span class="material-symbols-outlined" style="font-size: 20px; color: #5F6368">arrow_back</span>
        </button>
        <div class="topbar-title">Post-Meeting Summary</div>
        <div class="count-badge">
          {{ store.patients.filter(p => patientPostStatus(p.id) === 'complete').length }}/{{ store.patients.length }} completed
        </div>
      </div>
      <button class="export-btn">
        <span class="material-symbols-outlined" style="font-size: 18px">download</span>
        Export All Notes
      </button>
    </div>

    <div class="columns">

      <!-- Sidebar -->
      <div class="sidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">Board Cases</div>
          <div class="sidebar-sub">{{ store.patients.length }} patients</div>
        </div>
        <div class="patient-list">
          <div
            v-for="p in store.patients"
            :key="p.id"
            class="patient-item"
            :class="{ active: p.id === store.activeId }"
            @click="store.setActive(p.id)"
          >
            <div class="patient-name" :class="{ active: p.id === store.activeId }">
              <span class="status-dot" :style="{ background: statusColor[patientPostStatus(p.id)] }"></span>
              {{ p.name }}
            </div>
            <div class="patient-id">{{ p.id }}</div>
            <div class="status-chip" :class="patientPostStatus(p.id)">
              {{ patientPostStatus(p.id) === 'complete' ? 'Done' : 'Pending' }}
            </div>
          </div>
        </div>
      </div>

      <!-- Content -->
      <div class="main-content">
        <div v-if="store.loading" class="empty-state">
          <span class="material-symbols-outlined" style="font-size: 40px; color: #DADCE0">hourglass_empty</span>
          <div>Loading…</div>
        </div>

        <div v-else-if="!postData" class="empty-state">
          <span class="material-symbols-outlined" style="font-size: 48px; color: #DADCE0">pending_actions</span>
          <div class="empty-title">Awaiting board review</div>
          <div class="empty-sub">
            {{ store.activePatient?.name || 'This case' }} has not been through the meeting room yet.<br>
            Discuss the case and confirm consensus to generate the post-meeting summary.
          </div>
        </div>

        <template v-else>
          <CaseOutcome
            :patient="{ id: store.activeId, name: store.activePatient?.name, completedDate: postData.completedDate }"
            :recommendation="postData.recommendation"
            :rationale="postData.rationale"
          />
          <ActionTrackerTable :actions="postData.actions" />
          <NoteDraft :note="postData.note" @save="handleSaveNote" />
        </template>
      </div>

    </div>
  </div>
</template>

<style scoped>
.post-shell {
  display: flex; flex-direction: column;
  height: calc(100vh - 56px); background: #F8F9FA;
}

.post-topbar {
  background: #fff; border-bottom: 1px solid #DADCE0;
  padding: 0 24px; height: 56px;
  display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
}

.topbar-left { display: flex; align-items: center; gap: 12px; }

.icon-btn {
  width: 36px; height: 36px; border-radius: 50%; border: none;
  background: transparent; cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: background 150ms;
}
.icon-btn:hover { background: #F8F9FA; }

.topbar-title  { font-size: 16px; font-weight: 500; color: #202124; }
.count-badge   { font-size: 12px; color: #5F6368; background: #F8F9FA; padding: 3px 10px; border-radius: 999px; font-weight: 500; }

.export-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 18px; border-radius: 999px; border: none;
  background: #1A73E8; color: #fff; font-size: 14px; font-weight: 500;
  cursor: pointer; font-family: 'Roboto', sans-serif; transition: background 150ms;
}
.export-btn:hover { background: #1557b0; }

.columns { flex: 1; display: flex; overflow: hidden; }

/* Sidebar */
.sidebar {
  width: 260px; background: #F8F9FA; border-right: 1px solid #DADCE0;
  display: flex; flex-direction: column; flex-shrink: 0; overflow: auto;
}

.sidebar-header { padding: 16px 20px; background: #fff; border-bottom: 1px solid #DADCE0; flex-shrink: 0; }
.sidebar-title  { font-size: 14px; font-weight: 500; color: #202124; margin-bottom: 2px; }
.sidebar-sub    { font-size: 12px; color: #5F6368; }

.patient-list { padding: 12px; display: flex; flex-direction: column; gap: 6px; }

.patient-item {
  padding: 12px 14px; border-radius: 8px; background: #fff;
  cursor: pointer; border: 1px solid transparent; transition: background 150ms;
}
.patient-item:hover { background: #E8EAED; }
.patient-item.active { background: #D2E3FC; border-color: #1A73E8; }

.patient-name {
  font-size: 14px; font-weight: 500; color: #202124;
  display: flex; align-items: center; margin-bottom: 4px;
}
.patient-name.active { color: #174EA6; }

.status-dot   { width: 7px; height: 7px; border-radius: 50%; margin-right: 8px; flex-shrink: 0; }
.patient-id   { font-family: 'Roboto Mono', monospace; font-size: 11px; color: #5F6368; margin-bottom: 6px; padding-left: 15px; }

.status-chip  { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 500; margin-left: 15px; }
.status-chip.complete { background: #E6F4EA; color: #188038; }
.status-chip.pending  { background: #FEF7E0; color: #B06000; }

/* Main */
.main-content { flex: 1; overflow: auto; padding: 24px; }

.empty-state {
  height: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 12px; text-align: center; padding: 60px 0;
}
.empty-title { font-size: 16px; font-weight: 500; color: #5F6368; }
.empty-sub   { font-size: 14px; color: #80868B; max-width: 280px; }
</style>
