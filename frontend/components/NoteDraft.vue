<script setup>
import { ref } from 'vue'

const props = defineProps({
  note: { type: String, required: true },
})

const emit = defineEmits(['save'])

const isEditing = ref(false)
const content = ref(props.note)

function save() {
  emit('save', content.value)
  isEditing.value = false
}

function cancel() {
  content.value = props.note
  isEditing.value = false
}
</script>

<template>
  <div class="note-card">
    <div class="note-header">
      <div class="note-title-row">
        <span class="material-symbols-outlined" style="font-size: 20px; color: #5F6368">description</span>
        <div class="note-title">Tumor Board Note</div>
      </div>
      <div class="note-actions">
        <template v-if="isEditing">
          <button class="btn-text" @click="cancel">Cancel</button>
          <button class="btn-primary" @click="save">Save</button>
        </template>
        <button v-else class="btn-primary" @click="isEditing = true">Edit</button>
      </div>
    </div>

    <textarea
      v-if="isEditing"
      v-model="content"
      class="note-textarea"
    />
    <div v-else class="note-content">{{ content }}</div>
  </div>
</template>

<style scoped>
.note-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.1);
  margin-bottom: 24px;
  overflow: hidden;
}

.note-header {
  padding: 20px 24px;
  border-bottom: 1px solid #E8EAED;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.note-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.note-title {
  font-size: 16px;
  font-weight: 500;
  color: #202124;
}

.note-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.btn-primary {
  padding: 8px 16px;
  border-radius: 999px;
  border: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  background: #1A73E8;
  color: #fff;
  font-family: 'Roboto', sans-serif;
  transition: background 150ms;
}

.btn-primary:hover {
  background: #1557b0;
}

.btn-text {
  padding: 8px 16px;
  border-radius: 999px;
  border: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  background: transparent;
  color: #1A73E8;
  font-family: 'Roboto', sans-serif;
}

.btn-text:hover {
  background: #E8F0FE;
}

.note-content {
  padding: 24px;
  font-size: 14px;
  line-height: 1.8;
  color: #202124;
  white-space: pre-line;
}

.note-textarea {
  width: 100%;
  padding: 24px;
  font-size: 14px;
  line-height: 1.8;
  color: #202124;
  border: none;
  outline: none;
  resize: vertical;
  min-height: 400px;
  font-family: 'Roboto', sans-serif;
  display: block;
}
</style>
