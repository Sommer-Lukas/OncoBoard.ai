<script setup>
import { onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { usePatientsStore } from '../src/stores/patients.js'

const router = useRouter()
const store = usePatientsStore()

onMounted(() => store.loadPatients())

const today = new Intl.DateTimeFormat('en-US', {
  weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
}).format(new Date())

const phases = [
  { key: 'pre',     label: 'Pre-Meeting',   icon: 'checklist', route: '/pre-meeting',  status: 'complete', statusLabel: 'Ready',       description: '7 agents completed · 1 data gap flagged' },
  { key: 'meeting', label: 'Meeting Room',  icon: 'groups',    route: '/meeting',       status: 'active',   statusLabel: 'In Progress', description: 'Board convened · Transcript recording' },
  { key: 'post',    label: 'Post-Meeting',  icon: 'task_alt',  route: '/post-meeting',  status: 'pending',  statusLabel: 'Pending',     description: 'Awaiting board decisions' },
]

const statusConfig = {
  complete: { bg: '#E6F4EA', color: '#188038', dot: '#34A853' },
  active:   { bg: '#D2E3FC', color: '#174EA6', dot: '#1A73E8' },
  pending:  { bg: '#F8F9FA', color: '#80868B', dot: '#DADCE0' },
}

const activePatients = computed(() => store.patients.filter(p => p.boardStatus === 'active'))
</script>

<template>
  <div class="dashboard">
    <div class="container">

      <div class="page-header">
        <div>
          <div class="page-title">Tumor Board</div>
          <div class="page-date">{{ today }}</div>
        </div>
        <div class="board-badge">
          <span class="material-symbols-outlined" style="font-size: 16px">pending</span>
          {{ activePatients.length }} case{{ activePatients.length !== 1 ? 's' : '' }} active
        </div>
      </div>

      <div class="section-label">Workflow</div>
      <div class="phase-row">
        <template v-for="(phase, idx) in phases" :key="phase.key">
          <div class="phase-card" :class="phase.status" @click="router.push(phase.route)">
            <div class="phase-icon-box" :style="{ background: statusConfig[phase.status].bg }">
              <span class="material-symbols-outlined" :style="{ fontSize: '20px', color: statusConfig[phase.status].dot }">{{ phase.icon }}</span>
            </div>
            <div class="phase-info">
              <div class="phase-label">{{ phase.label }}</div>
              <div class="phase-desc">{{ phase.description }}</div>
            </div>
            <div class="phase-chip" :style="{ background: statusConfig[phase.status].bg, color: statusConfig[phase.status].color }">
              {{ phase.statusLabel }}
            </div>
          </div>
          <div v-if="idx < phases.length - 1" class="connector">
            <span class="material-symbols-outlined" style="font-size: 18px; color: #DADCE0">arrow_forward</span>
          </div>
        </template>
      </div>

      <div class="section-label" style="margin-top: 32px">Cases</div>

      <div v-if="store.loading" class="loading-state">Loading patients…</div>

      <div v-else class="case-list">
        <div
          v-for="patient in store.patients"
          :key="patient.id"
          class="case-card"
          @click="store.setActive(patient.id)"
        >
          <div class="case-top">
            <div class="case-avatar">
              <span class="material-symbols-outlined" style="font-size: 20px; color: #1A73E8">person</span>
            </div>
            <div class="case-meta">
              <div class="case-name">{{ patient.name }}</div>
              <div class="case-id">{{ patient.id }}</div>
            </div>
            <div class="case-chips">
              <span class="chip">{{ patient.age }}y</span>
              <span class="chip">{{ patient.stage }}</span>
              <span class="chip">{{ patient.receptors }}</span>
            </div>
            <span
              class="board-status-chip"
              :class="patient.boardStatus"
            >{{ patient.boardStatus }}</span>
          </div>
          <div class="case-diagnosis">{{ patient.diagnosis }}</div>
          <div class="case-actions">
            <button class="action-btn" @click.stop="router.push('/pre-meeting')">
              <span class="material-symbols-outlined" style="font-size: 15px">checklist</span>
              Pre-Meeting
            </button>
            <button class="action-btn" @click.stop="router.push('/post-meeting')">
              <span class="material-symbols-outlined" style="font-size: 15px">task_alt</span>
              Post-Meeting
            </button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.dashboard { background: #F8F9FA; min-height: calc(100vh - 56px); }

.container { max-width: 1280px; margin: 0 auto; padding: 24px; }

.page-header {
  background: #fff;
  padding: 20px 24px;
  margin-bottom: 24px;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(60,64,67,0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title { font-size: 20px; font-weight: 500; color: #202124; margin-bottom: 2px; }
.page-date  { font-size: 13px; color: #5F6368; }

.board-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 999px;
  background: #D2E3FC; color: #174EA6; font-size: 13px; font-weight: 500;
}

.section-label {
  font-size: 12px; font-weight: 500; color: #5F6368;
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;
}

/* Phase row */
.phase-row { display: flex; align-items: center; gap: 8px; margin-bottom: 0; }
.phase-card {
  flex: 1; display: flex; align-items: center; gap: 14px;
  padding: 16px 20px; background: #fff; border-radius: 12px;
  box-shadow: 0 1px 2px rgba(60,64,67,0.1); cursor: pointer;
  border: 1px solid transparent; transition: box-shadow 150ms, border-color 150ms;
}
.phase-card:hover { box-shadow: 0 1px 3px rgba(60,64,67,0.15), 0 4px 8px rgba(60,64,67,0.1); }
.phase-card.active { border-color: #1A73E8; }
.phase-icon-box { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.phase-info { flex: 1; min-width: 0; }
.phase-label { font-size: 14px; font-weight: 500; color: #202124; margin-bottom: 3px; }
.phase-desc  { font-size: 12px; color: #5F6368; }
.phase-chip  { padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 500; white-space: nowrap; flex-shrink: 0; }
.connector   { flex-shrink: 0; }

/* Case list */
.loading-state { font-size: 14px; color: #5F6368; padding: 24px 0; }

.case-list { display: flex; flex-direction: column; gap: 12px; }

.case-card {
  background: #fff; border-radius: 12px; padding: 18px 24px;
  box-shadow: 0 1px 2px rgba(60,64,67,0.1); cursor: pointer;
  border: 1px solid transparent; transition: border-color 150ms, box-shadow 150ms;
}
.case-card:hover { border-color: #DADCE0; box-shadow: 0 1px 3px rgba(60,64,67,0.15), 0 4px 8px rgba(60,64,67,0.1); }

.case-top { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; flex-wrap: wrap; }

.case-avatar {
  width: 40px; height: 40px; border-radius: 10px; background: #D2E3FC;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}

.case-meta { flex: 1; }
.case-name { font-size: 15px; font-weight: 500; color: #202124; margin-bottom: 2px; }
.case-id   { font-family: 'Roboto Mono', monospace; font-size: 11px; color: #5F6368; }

.case-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { padding: 3px 10px; border-radius: 999px; font-size: 12px; background: #F8F9FA; color: #202124; }

.board-status-chip { padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 500; text-transform: capitalize; flex-shrink: 0; }
.board-status-chip.active   { background: #D2E3FC; color: #174EA6; }
.board-status-chip.pending  { background: #FEF7E0; color: #B06000; }
.board-status-chip.complete { background: #E6F4EA; color: #188038; }

.case-diagnosis { font-size: 13px; color: #5F6368; margin-bottom: 14px; padding-left: 54px; }

.case-actions { display: flex; gap: 8px; padding-left: 54px; }

.action-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 14px; border-radius: 999px; border: 1px solid #DADCE0;
  font-size: 13px; font-weight: 500; cursor: pointer;
  background: #F8F9FA; color: #202124;
  font-family: 'Roboto', sans-serif; transition: background 150ms;
}
.action-btn:hover { background: #E8EAED; }
</style>
