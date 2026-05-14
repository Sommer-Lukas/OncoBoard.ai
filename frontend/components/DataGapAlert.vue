<script setup>
defineProps({
  title: { type: String, default: 'Missing Data' },
  message: { type: String, required: true },
  showUploadButton: { type: Boolean, default: false },
})

defineEmits(['upload'])
</script>

<template>
  <div class="alert">
    <span class="material-symbols-outlined alert-icon">warning</span>
    <div class="alert-content">
      <div class="alert-title">{{ title }}</div>
      <div class="alert-text">{{ message }}</div>
    </div>
    <button v-if="showUploadButton" class="upload-btn" @click="$emit('upload')">
      Upload Missing File
    </button>
  </div>
</template>

<style scoped>
.alert {
  background: #FEF7E0;
  border-left: 4px solid #FBBC04;
  padding: 16px 20px;
  border-radius: 8px;
  margin-bottom: 24px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.alert-icon {
  color: #B06000;
  flex-shrink: 0;
}

.alert-content {
  flex: 1;
}

.alert-title {
  font-weight: 500;
  color: #202124;
  margin-bottom: 4px;
}

.alert-text {
  font-size: 13px;
  color: #5F6368;
}

.upload-btn {
  padding: 6px 16px;
  border-radius: 999px;
  border: none;
  background: #1A73E8;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  flex-shrink: 0;
  font-family: 'Roboto', sans-serif;
}

.upload-btn:hover {
  background: #1557b0;
}
</style>
