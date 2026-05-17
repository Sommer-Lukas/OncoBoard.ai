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

const formattedOutput = computed(() => {
  if (!props.rawData) return props.output ?? 'No output available.'
  try {
    return JSON.stringify(props.rawData, null, 2)
  } catch {
    return props.output ?? 'No output available.'
  }
})

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
            <pre class="output-pre">{{ formattedOutput }}</pre>
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

.output-pre {
  margin: 0;
  font-family: 'Roboto Mono', monospace;
  font-size: 12.5px;
  line-height: 1.6;
  color: #202124;
  white-space: pre-wrap;
  word-break: break-word;
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
