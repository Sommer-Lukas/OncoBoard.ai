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
  complete: { bg: '#34A853', color: '#fff', icon: 'check_circle', label: 'Complete' },
  running: { bg: '#1A73E8', color: '#fff', icon: 'sync', label: 'Running' },
  error: { bg: '#EA4335', color: '#fff', icon: 'error', label: 'Error' },
  idle: { bg: '#E8EAED', color: '#5F6368', icon: '', label: 'Idle' },
}

const config = computed(() => statusConfig[props.status] || statusConfig.idle)

function handleCardClick() {
  if (props.status === 'complete') {
    expanded.value = !expanded.value
  }
}

function handleDatabaseClick(e) {
  e.stopPropagation()
  emit('database-click', props.name)
}
</script>

<template>
  <div class="agent-card">
    <button
      v-if="onDatabaseClick && status === 'complete'"
      class="db-btn"
      :title="`View ${name} data in database`"
      @click="handleDatabaseClick"
    >
      <span class="material-symbols-outlined" style="font-size: 18px; color: #5F6368">database</span>
    </button>

    <div
      class="card-header"
      :class="{ clickable: status === 'complete' }"
      @click="handleCardClick"
    >
      <div class="icon-box">
        <span class="material-symbols-outlined" style="font-size: 20px; color: #5F6368">{{ icon }}</span>
      </div>
      <div class="card-content">
        <div class="card-title">{{ name }}</div>
        <div class="status-chip" :style="{ background: config.bg, color: config.color }">
          <span v-if="config.icon" class="material-symbols-outlined" style="font-size: 14px">{{ config.icon }}</span>
          <span style="text-transform: capitalize">{{ status }}</span>
        </div>
        <div v-if="timestamp" class="timestamp">{{ timestamp }}</div>
      </div>
    </div>

    <div v-if="expanded && output" class="output-box">
      {{ output }}
    </div>
  </div>
</template>

<style scoped>
.agent-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.1);
  position: relative;
  transition: box-shadow 150ms cubic-bezier(0.4, 0, 0.2, 1);
}

.agent-card:hover {
  box-shadow: 0 1px 3px rgba(60, 64, 67, 0.15), 0 4px 8px rgba(60, 64, 67, 0.1);
}

.db-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: #F8F9FA;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 150ms;
  z-index: 1;
}

.db-btn:hover {
  background: #E8EAED;
}

.card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.card-header.clickable {
  cursor: pointer;
}

.icon-box {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #F8F9FA;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.card-content {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 15px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 4px;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.timestamp {
  font-size: 12px;
  color: #80868B;
  margin-top: 8px;
}

.output-box {
  margin-top: 16px;
  padding: 16px;
  background: #F8F9FA;
  border-radius: 8px;
  font-size: 13px;
  color: #202124;
  line-height: 1.6;
  border-left: 3px solid #34A853;
}
</style>
