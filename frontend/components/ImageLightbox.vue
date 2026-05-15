<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { imageUrl } from '../src/services/api.js'

const props = defineProps({
  images: { type: Array, required: true },  // list of /images/... paths
  index:  { type: Number, required: true },  // currently open index
})

const emit = defineEmits(['close', 'navigate'])

const current = computed(() => props.images[props.index])
const label   = computed(() => `${props.index + 1} / ${props.images.length}`)
const hasPrev = computed(() => props.index > 0)
const hasNext = computed(() => props.index < props.images.length - 1)

function prev() { if (hasPrev.value) emit('navigate', props.index - 1) }
function next() { if (hasNext.value) emit('navigate', props.index + 1) }

function onKey(e) {
  if (e.key === 'Escape')     emit('close')
  if (e.key === 'ArrowLeft')  prev()
  if (e.key === 'ArrowRight') next()
}

onMounted(()  => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="lb-overlay" @click.self="$emit('close')">
    <div class="lb-frame">

      <button class="lb-close" @click="$emit('close')">
        <span class="material-symbols-outlined">close</span>
      </button>

      <button class="lb-arrow lb-prev" :disabled="!hasPrev" @click="prev">
        <span class="material-symbols-outlined">chevron_left</span>
      </button>

      <img class="lb-img" :src="imageUrl(current)" :alt="current" />

      <button class="lb-arrow lb-next" :disabled="!hasNext" @click="next">
        <span class="material-symbols-outlined">chevron_right</span>
      </button>

      <div class="lb-counter">{{ label }}</div>
    </div>
  </div>
</template>

<style scoped>
.lb-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.88);
  z-index: 2000;
  display: flex; align-items: center; justify-content: center;
}

.lb-frame {
  position: relative;
  display: flex; align-items: center; justify-content: center;
  max-width: 92vw; max-height: 92vh;
}

.lb-img {
  display: block;
  max-width: 80vw; max-height: 88vh;
  object-fit: contain;
  border-radius: 6px;
  user-select: none;
}

.lb-close {
  position: fixed; top: 20px; right: 24px;
  width: 40px; height: 40px; border-radius: 50%; border: none;
  background: rgba(255,255,255,0.12); color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: background 150ms;
}
.lb-close:hover { background: rgba(255,255,255,0.24); }
.lb-close .material-symbols-outlined { font-size: 22px; }

.lb-arrow {
  position: absolute;
  width: 48px; height: 48px; border-radius: 50%; border: none;
  background: rgba(255,255,255,0.12); color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: background 150ms; z-index: 1;
  flex-shrink: 0;
}
.lb-arrow:hover:not(:disabled) { background: rgba(255,255,255,0.26); }
.lb-arrow:disabled { opacity: 0.2; cursor: default; }
.lb-arrow .material-symbols-outlined { font-size: 28px; }

.lb-prev { left: -68px; }
.lb-next { right: -68px; }

.lb-counter {
  position: fixed; bottom: 24px; left: 50%;
  transform: translateX(-50%);
  font-size: 13px; color: rgba(255,255,255,0.7);
  font-family: 'Roboto', sans-serif;
  background: rgba(0,0,0,0.4); padding: 4px 14px; border-radius: 999px;
  pointer-events: none;
}
</style>
