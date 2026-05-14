<script setup>
defineProps({
  patientId: { type: String, required: true },
  name: { type: String, required: true },
  age: { type: [String, Number], required: true },
  stage: { type: String, required: true },
  receptors: { type: String, required: true },
})
</script>

<template>
  <div class="patient-header">
    <span class="patient-id">{{ patientId }}</span>
    <div class="divider"></div>
    <span class="patient-name">{{ name }}</span>
    <span class="chip">{{ age }}y</span>
    <span class="chip">{{ stage }}</span>
    <span class="chip">{{ receptors }}</span>
  </div>
</template>

<style scoped>
.patient-header {
  background: #fff;
  padding: 16px 24px;
  border-bottom: 1px solid #DADCE0;
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}

.patient-id {
  font-family: 'Roboto Mono', monospace;
  font-size: 13px;
  color: #5F6368;
  font-weight: 500;
}

.patient-name {
  font-size: 16px;
  font-weight: 500;
  color: #202124;
}

.chip {
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  background: #F8F9FA;
  color: #202124;
}

.divider {
  width: 1px;
  height: 20px;
  background: #DADCE0;
}
</style>
