<script setup>
import { ref, computed } from 'vue'

const recording = ref(false)
const elapsed = ref(0)
let timer = null

const transcriptLines = ref([
  { speaker: 'Dr. Chen', text: 'Given the node-positive status and Ki-67 of 22%, I lean toward chemotherapy.', time: '14:23' },
  { speaker: 'Dr. Patel', text: 'Agreed. Oncotype DX score would help, but intermediate-high risk is clear.', time: '14:24' },
])

function startRecording() {
  recording.value = true
  timer = setInterval(() => { elapsed.value++ }, 1000)
}

function stopRecording() {
  recording.value = false
  clearInterval(timer)
}

const elapsedFormatted = computed(() => {
  const m = Math.floor(elapsed.value / 60).toString().padStart(2, '0')
  const s = (elapsed.value % 60).toString().padStart(2, '0')
  return `${m}:${s}`
})
</script>

<template>
  <div class="live-panel">
    <div class="panel-header">
      <div class="panel-title">
        <span class="material-symbols-outlined" style="font-size: 20px">mic</span>
        Live Transcript
      </div>

      <div class="panel-controls">
        <template v-if="recording">
          <div class="recording-status">
            <span class="pulse-dot"></span>
            <span class="elapsed">{{ elapsedFormatted }}</span>
          </div>
          <button class="stop-btn" @click="stopRecording">
            <span class="material-symbols-outlined" style="font-size: 16px">stop</span>
            Stop
          </button>
        </template>
        <button v-else class="start-btn" @click="startRecording">
          <span class="material-symbols-outlined" style="font-size: 16px">fiber_manual_record</span>
          Start
        </button>
      </div>
    </div>

    <div class="transcript-scroll">
      <div v-if="transcriptLines.length === 0" class="empty-state">
        <span class="material-symbols-outlined" style="font-size: 32px; color: #DADCE0">mic_off</span>
        <div>No transcript yet</div>
      </div>

      <div v-for="(line, idx) in transcriptLines" :key="idx" class="transcript-line">
        <div class="line-meta">
          <span class="speaker">{{ line.speaker }}</span>
          <span class="time">{{ line.time }}</span>
        </div>
        <div class="line-text">{{ line.text }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.live-panel {
  width: 360px;
  background: #fff;
  border-left: 1px solid #DADCE0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  box-shadow: -2px 0 8px rgba(60, 64, 67, 0.08);
  overflow: hidden;
}

.panel-header {
  padding: 16px 20px;
  border-bottom: 1px solid #E8EAED;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
}

.panel-title {
  font-size: 15px;
  font-weight: 500;
  color: #202124;
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.recording-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #EA4335;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #EA4335;
  animation: pulse 1.4s ease-in-out infinite;
  flex-shrink: 0;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
}

.elapsed {
  font-family: 'Roboto Mono', monospace;
  font-size: 12px;
  font-weight: 500;
}

.start-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 999px;
  border: none;
  background: #34A853;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: 'Roboto', sans-serif;
  transition: background 150ms;
}

.start-btn:hover {
  background: #2d9247;
}

.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 999px;
  border: none;
  background: #FCE8E6;
  color: #C5221F;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: 'Roboto', sans-serif;
  transition: background 150ms;
}

.stop-btn:hover {
  background: #f5c6c2;
}

.transcript-scroll {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #80868B;
  font-size: 13px;
  text-align: center;
  padding: 40px 0;
}

.transcript-line {
  margin-bottom: 16px;
}

.line-meta {
  font-size: 12px;
  font-weight: 500;
  color: #5F6368;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.speaker {
  font-weight: 500;
}

.time {
  font-size: 11px;
  color: #80868B;
}

.line-text {
  font-size: 13px;
  color: #202124;
  line-height: 1.5;
}
</style>
