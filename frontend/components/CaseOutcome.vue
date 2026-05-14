<script setup>
defineProps({
  patient: { type: Object, required: true },
  recommendation: { type: String, required: true },
  rationale: { type: String, required: true },
})
</script>

<template>
  <div class="outcome-card">
    <div class="outcome-header">
      <div class="icon-box">
        <span class="material-symbols-outlined" style="font-size: 24px; color: #34A853">check_circle</span>
      </div>
      <div class="title-section">
        <div class="patient-name">{{ patient.name }}</div>
        <div class="patient-sub">{{ patient.id }} • Board Completed {{ patient.completedDate }}</div>
      </div>
      <div class="decision-chip">
        <span class="material-symbols-outlined" style="font-size: 16px">done</span>
        Decision Recorded
      </div>
    </div>

    <div class="outcome-section">
      <div class="section-label">Recommendation</div>
      <div class="section-value">{{ recommendation }}</div>
    </div>

    <div class="outcome-section">
      <div class="section-label">Rationale</div>
      <div class="section-value">{{ rationale }}</div>
    </div>
  </div>
</template>

<style scoped>
.outcome-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(60, 64, 67, 0.15), 0 4px 8px rgba(60, 64, 67, 0.1);
  margin-bottom: 24px;
}

.outcome-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #E8EAED;
}

.icon-box {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: #E6F4EA;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.title-section {
  flex: 1;
}

.patient-name {
  font-size: 18px;
  font-weight: 500;
  color: #202124;
  margin-bottom: 4px;
}

.patient-sub {
  font-size: 13px;
  color: #5F6368;
}

.decision-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: #E6F4EA;
  color: #188038;
  white-space: nowrap;
}

.outcome-section {
  margin-bottom: 16px;
}

.outcome-section:last-child {
  margin-bottom: 0;
}

.section-label {
  font-size: 12px;
  font-weight: 500;
  color: #5F6368;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.section-value {
  font-size: 15px;
  color: #202124;
  line-height: 1.6;
}
</style>
