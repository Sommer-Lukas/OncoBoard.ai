<script setup>
defineProps({
  // { state: 'verified'|'unverified'|'none', verifiedBy?: string, ts?: string }
  status: { type: Object, required: true },
})
</script>

<template>
  <span v-if="status.state === 'verified'" class="chip verified">
    <span class="material-symbols-outlined" style="font-size: 13px">verified</span>
    Verified by {{ status.verifiedBy }}
    <span v-if="status.ts" class="chip-ts">· {{ status.ts }}</span>
  </span>
  <span v-else-if="status.state === 'unverified'" class="chip unverified">
    <span class="material-symbols-outlined" style="font-size: 13px">warning</span>
    Not verified
  </span>
</template>

<style scoped>
.chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 500;
}

.verified {
  background: #E6F4EA; color: #137333;
}

.unverified {
  background: #FEF7E0; color: #B06000;
}

.chip-ts { opacity: 0.75; }
</style>
