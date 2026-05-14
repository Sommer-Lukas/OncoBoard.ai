<script setup>
defineProps({
  patients: { type: Array, required: true },
  activeId: { type: String, required: true },
})

defineEmits(['select'])

const statusColor = {
  active: '#34A853',
  pending: '#FBBC04',
  complete: '#5F6368',
}
</script>

<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title">Tumor Board Cases</div>
      <div class="sidebar-subtitle">{{ patients.length }} patients</div>
    </div>
    <div class="patient-list">
      <div
        v-for="patient in patients"
        :key="patient.id"
        class="patient-item"
        :class="{ active: patient.id === activeId }"
        @click="$emit('select', patient.id)"
      >
        <div class="patient-name" :class="{ active: patient.id === activeId }">
          <span class="status-dot" :style="{ background: statusColor[patient.status] || statusColor.pending }"></span>
          {{ patient.name }}
        </div>
        <div class="patient-id">{{ patient.id }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sidebar {
  width: 280px;
  background: #F8F9FA;
  border-right: 1px solid #DADCE0;
  overflow: auto;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #DADCE0;
  background: #fff;
}

.sidebar-title {
  font-size: 16px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 4px;
}

.sidebar-subtitle {
  font-size: 12px;
  color: #5F6368;
}

.patient-list {
  padding: 12px;
}

.patient-item {
  padding: 12px 16px;
  margin-bottom: 8px;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: background 150ms;
  border: 1px solid transparent;
}

.patient-item:hover {
  background: #E8EAED;
}

.patient-item.active {
  background: #D2E3FC;
  border-color: #1A73E8;
}

.patient-name {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
}

.patient-name.active {
  color: #174EA6;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 8px;
  flex-shrink: 0;
}

.patient-id {
  font-size: 12px;
  color: #5F6368;
  font-family: 'Roboto Mono', monospace;
}
</style>
