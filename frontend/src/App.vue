<script setup>
import { useRoute } from 'vue-router'
import { useAgentsStore } from './stores/agents.js'

const route = useRoute()
const agentsStore = useAgentsStore()

const noNav = ['/meeting']
</script>

<template>
  <div class="app-shell">
    <header v-if="!noNav.includes(route.path)" class="top-nav">
      <RouterLink to="/" class="nav-brand">
        <span class="material-symbols-outlined brand-icon">ecg_heart</span>
        <span class="brand-name">OncoBoard<span class="brand-accent">.ai</span></span>
      </RouterLink>

      <nav class="nav-links">
        <RouterLink to="/" class="nav-link" active-class="active" exact>
          Dashboard
        </RouterLink>
        <RouterLink to="/pre-meeting" class="nav-link" active-class="active">
          Pre-Meeting
        </RouterLink>
        <RouterLink to="/meeting" class="nav-link" active-class="active">
          Meeting Room
        </RouterLink>
        <RouterLink to="/post-meeting" class="nav-link" active-class="active">
          Post-Meeting
        </RouterLink>
      </nav>

      <div class="nav-right">
        <Transition name="ai-chip">
          <div v-if="agentsStore.runningCount > 0" class="ai-live-chip">
            <span class="ai-live-dot"></span>
            {{ agentsStore.runningCount }} agent{{ agentsStore.runningCount !== 1 ? 's' : '' }} running
          </div>
        </Transition>
      </div>
    </header>

    <RouterView />
  </div>
</template>

<style>
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: 'Roboto', sans-serif;
  color: #202124;
  -webkit-font-smoothing: antialiased;
  background: #F8F9FA !important;
}
</style>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #F8F9FA;
}

.top-nav {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #DADCE0;
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 32px;
  position: sticky;
  top: 0;
  z-index: 100;
  flex-shrink: 0;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: #202124;
  flex-shrink: 0;
}

.brand-icon { font-size: 22px; color: #1A73E8; }

.brand-name { font-size: 16px; font-weight: 500; color: #202124; }

.brand-accent { color: #1A73E8; }

.nav-links {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.nav-link {
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 500;
  color: #5F6368;
  text-decoration: none;
  transition: background 150ms, color 150ms;
}

.nav-link:hover { background: #F8F9FA; color: #202124; }
.nav-link.active { background: #D2E3FC; color: #174EA6; }

/* AI live chip */
.nav-right { display: flex; align-items: center; flex-shrink: 0; }

.ai-live-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 13px;
  border-radius: 999px;
  background: rgba(26, 115, 232, 0.08);
  color: #174EA6;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid rgba(26, 115, 232, 0.2);
}

.ai-live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #1A73E8;
  animation: ai-dot-pulse 1.6s ease-in-out infinite;
}

/* Transition for chip appearing/disappearing */
.ai-chip-enter-active,
.ai-chip-leave-active {
  transition: opacity 300ms, transform 300ms;
}
.ai-chip-enter-from,
.ai-chip-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

@keyframes ai-dot-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.5); opacity: 0.5; }
}
</style>
