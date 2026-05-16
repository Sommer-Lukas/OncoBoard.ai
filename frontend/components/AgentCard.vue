<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  icon: { type: String, required: true },
  status: { type: String, default: 'idle' },
  timestamp: { type: String, default: null },
  output: { type: String, default: null },
  onDatabaseClick: { type: Function, default: null },
})

const emit = defineEmits(['database-click'])
const expanded = ref(false)

const statusConfig = {
  complete: { bg: '#E6F4EA', color: '#188038', icon: 'check_circle', label: 'Complete' },
  running:  { bg: 'rgba(26,115,232,0.1)', color: '#174EA6', icon: '',              label: 'Running'  },
  error:    { bg: '#FCE8E6', color: '#C5221F', icon: 'error',         label: 'Error'    },
  idle:     { bg: '#F8F9FA', color: '#9AA0A6', icon: '',              label: 'Idle'     },
}

const config = computed(() => statusConfig[props.status] ?? statusConfig.idle)

function handleCardClick() {
  if (props.status === 'complete') expanded.value = !expanded.value
}

function handleDatabaseClick(e) {
  e.stopPropagation()
  emit('database-click', props.name)
}
</script>

<template>
  <div class="agent-card" :class="status" @click="handleCardClick">

    <!-- Scan highlight — sweeps left→right while running -->
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
          <span class="material-symbols-outlined icon-symbol">{{ icon }}</span>
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

      <!-- Expand chevron for complete cards -->
      <span
        v-if="status === 'complete'"
        class="material-symbols-outlined expand-chevron"
        :class="{ rotated: expanded }"
        aria-hidden="true"
      >expand_more</span>
    </div>

    <!-- Expandable output -->
    <Transition name="output-expand">
      <div v-if="expanded && output" class="output-box">{{ output }}</div>
    </Transition>
  </div>
</template>

<style scoped>
/* ── Base card ── */
.agent-card {
  background: #fff;
  border-radius: 10px;
  padding: 12px 14px;
  position: relative;
  border: 1.5px solid transparent;
  transition: box-shadow 200ms, border-color 200ms, background 200ms, opacity 200ms;
  cursor: default;
}

.agent-card:not(.running):not(.idle) {
  box-shadow: 0 1px 2px rgba(60,64,67,0.08);
}

/* ── Status variants ── */
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

.agent-card.idle {
  opacity: 0.6;
}

.agent-card.error {
  border-color: rgba(234,67,53,0.28);
}

/* ── Scan bar (overflow clipped inside the bar itself) ── */
.scan-bar {
  position: absolute;
  inset: 0;
  border-radius: 9px;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}
.scan-bar::after {
  content: '';
  position: absolute;
  top: 0;
  width: 90px;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(26,115,232,0.08), transparent);
  animation: scan-sweep 3s ease-in-out infinite;
}

/* ── Sonar pulse rings ── */
.icon-wrapper {
  position: relative;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}

.pulse-ring {
  position: absolute;
  inset: -4px;
  border: 1.5px solid rgba(26,115,232,0.45);
  border-radius: 10px;
  animation: ring-expand 2.2s ease-out infinite;
  pointer-events: none;
}
.ring-2 { animation-delay: 1.1s; }

/* ── Icon box ── */
.icon-box {
  position: absolute;
  inset: 0;
  border-radius: 7px;
  background: #F8F9FA;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  transition: background 200ms;
}
.icon-box.running  { background: rgba(26,115,232,0.1); }
.icon-box.complete { background: #E6F4EA; }
.icon-box.error    { background: #FCE8E6; }

.icon-symbol {
  font-size: 17px;
  color: #5F6368;
  transition: color 200ms;
}
.icon-box.running  .icon-symbol { color: #1A73E8; animation: icon-breathe 2s ease-in-out infinite; }
.icon-box.complete .icon-symbol { color: #34A853; }
.icon-box.error    .icon-symbol { color: #EA4335; }

/* ── Card header ── */
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
  z-index: 1;
}
.card-header.clickable { cursor: pointer; }

/* ── Card content ── */
.card-content { flex: 1; min-width: 0; }

.card-title {
  font-size: 13px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 4px;
  transition: color 200ms;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.agent-card.running .card-title { color: #174EA6; }

/* ── Status chip ── */
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
}

/* ── Animated dots ── */
.dot-anim { display: inline-flex; gap: 1px; margin-left: 1px; }
.dot {
  display: inline-block;
  animation: dot-fade 1.4s ease-in-out infinite;
  font-weight: 700;
}
.d1 { animation-delay: 0s; }
.d2 { animation-delay: 0.22s; }
.d3 { animation-delay: 0.44s; }

/* ── Timestamp ── */
.timestamp {
  font-size: 10px;
  color: #9AA0A6;
  margin-top: 3px;
  font-family: 'Roboto Mono', monospace;
}

/* ── Expand chevron ── */
.expand-chevron {
  font-size: 18px;
  color: #BDC1C6;
  transition: transform 220ms cubic-bezier(0.4,0,0.2,1), color 150ms;
  flex-shrink: 0;
  margin-top: 2px;
}
.expand-chevron.rotated { transform: rotate(180deg); color: #34A853; }

/* ── DB button ── */
.db-btn {
  position: absolute;
  top: 8px; right: 8px;
  width: 26px; height: 26px;
  border-radius: 50%; border: none;
  background: #F8F9FA; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 150ms;
  z-index: 2;
}
.db-btn:hover { background: #E8EAED; }

/* ── Output box ── */
.output-box {
  margin-top: 10px;
  padding: 10px 12px;
  background: #F8F9FA;
  border-radius: 7px;
  font-size: 12px;
  color: #202124;
  line-height: 1.5;
  border-left: 3px solid #34A853;
  position: relative;
  z-index: 1;
}

/* ── Output expand transition ── */
.output-expand-enter-active,
.output-expand-leave-active {
  transition: opacity 200ms, transform 200ms;
  transform-origin: top;
}
.output-expand-enter-from,
.output-expand-leave-to {
  opacity: 0;
  transform: scaleY(0.96) translateY(-4px);
}

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
  0%, 100% { opacity: 1;   }
  50%       { opacity: 0.5; }
}

@keyframes dot-fade {
  0%, 60%, 100% { opacity: 0.25; }
  30%           { opacity: 1;    }
}
</style>
