<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { chatWithCase } from '../src/services/api.js'

const props = defineProps({
  caseId:   { type: String, default: null },
  caseName: { type: String, default: null },
  phase:    { type: String, default: 'pre' }, // 'pre' | 'mid' | 'post'
})

const PHASE_LABELS = { pre: 'Pre-Meeting', mid: 'Mid-Meeting', post: 'Post-Meeting' }

const open      = ref(false)
const loading   = ref(false)
const input     = ref('')
const messages  = ref([])   // { role: 'user'|'assistant', content: string }
const bodyEl    = ref(null)
const inputEl   = ref(null)
const error     = ref(null)

const canSend = computed(() => input.value.trim().length > 0 && !loading.value && !!props.caseId)

watch(open, (val) => {
  if (val) nextTick(() => inputEl.value?.focus())
})

watch(() => props.caseId, () => {
  // Clear chat when patient changes
  messages.value = []
  error.value = null
})

async function send() {
  const text = input.value.trim()
  if (!text || !props.caseId) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  error.value = null
  loading.value = true
  scrollToBottom()

  try {
    const reply = await chatWithCase(props.caseId, messages.value, props.phase)
    messages.value.push({ role: 'assistant', content: reply })
  } catch (e) {
    error.value = e.message ?? 'Request failed'
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight
  })
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function clearChat() {
  messages.value = []
  error.value = null
}
</script>

<template>
  <!-- Floating trigger button -->
  <button
    class="chat-fab"
    :class="{ open }"
    :title="open ? 'Close clinical assistant' : 'Ask clinical assistant'"
    @click="open = !open"
  >
    <span class="material-symbols-outlined" style="font-size: 22px">
      {{ open ? 'close' : 'assistant' }}
    </span>
  </button>

  <!-- Chat panel -->
  <Transition name="panel-slide">
    <div v-if="open" class="chat-panel">

      <!-- Header -->
      <div class="chat-header">
        <div class="header-left">
          <span class="material-symbols-outlined" style="font-size:16px;color:#1A73E8">assistant</span>
          <div>
            <div class="header-title">Clinical Assistant</div>
            <div class="header-sub">
              {{ PHASE_LABELS[phase] }}
              <template v-if="caseName"> · {{ caseName }}</template>
            </div>
          </div>
        </div>
        <div class="header-actions">
          <button v-if="messages.length" class="icon-btn" title="Clear chat" @click="clearChat">
            <span class="material-symbols-outlined" style="font-size:16px">delete_sweep</span>
          </button>
          <button class="icon-btn" title="Close" @click="open = false">
            <span class="material-symbols-outlined" style="font-size:16px">close</span>
          </button>
        </div>
      </div>

      <!-- No patient selected -->
      <div v-if="!caseId" class="empty-state">
        <span class="material-symbols-outlined" style="font-size:36px;color:#DADCE0">person_search</span>
        <div>Select a patient to start asking questions about their case.</div>
      </div>

      <!-- Message body -->
      <div v-else ref="bodyEl" class="chat-body">
        <!-- Welcome state -->
        <div v-if="!messages.length" class="welcome">
          <span class="material-symbols-outlined welcome-icon">clinical_notes</span>
          <div class="welcome-title">Ask anything about this patient</div>
          <div class="welcome-sub">
            I have full context from the case record and all available agent outputs.
          </div>
          <div class="suggestions">
            <button class="suggestion" @click="input = 'Summarise the key clinical findings for this patient'; send()">
              Summarise key findings
            </button>
            <button class="suggestion" @click="input = 'What treatment options are recommended by the guidelines?'; send()">
              Treatment options
            </button>
            <button class="suggestion" @click="input = 'Are there any open clinical trials this patient qualifies for?'; send()">
              Clinical trials
            </button>
            <button class="suggestion" @click="input = 'What are the main pathology findings?'; send()">
              Pathology findings
            </button>
          </div>
        </div>

        <!-- Messages -->
        <TransitionGroup name="msg-in" tag="div" class="messages">
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="message"
            :class="msg.role"
          >
            <div v-if="msg.role === 'assistant'" class="msg-avatar">
              <span class="material-symbols-outlined" style="font-size:14px">assistant</span>
            </div>
            <div class="msg-bubble">{{ msg.content }}</div>
          </div>
        </TransitionGroup>

        <!-- Typing indicator -->
        <div v-if="loading" class="message assistant">
          <div class="msg-avatar">
            <span class="material-symbols-outlined" style="font-size:14px">assistant</span>
          </div>
          <div class="msg-bubble typing">
            <span></span><span></span><span></span>
          </div>
        </div>

        <!-- Error -->
        <div v-if="error" class="error-row">
          <span class="material-symbols-outlined" style="font-size:14px">error_outline</span>
          {{ error }}
        </div>
      </div>

      <!-- Input -->
      <div v-if="caseId" class="chat-input-row">
        <textarea
          ref="inputEl"
          v-model="input"
          class="chat-input"
          placeholder="Ask about this patient…"
          rows="1"
          :disabled="loading"
          @keydown="handleKey"
        ></textarea>
        <button
          class="send-btn"
          :disabled="!canSend"
          @click="send"
        >
          <span class="material-symbols-outlined" style="font-size:18px">send</span>
        </button>
      </div>

    </div>
  </Transition>
</template>

<style scoped>
/* ── FAB trigger ── */
.chat-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 500;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  background: #1A73E8;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(26,115,232,0.4);
  transition: background 150ms, box-shadow 150ms, transform 150ms;
}
.chat-fab:hover  { background: #1765CC; box-shadow: 0 6px 16px rgba(26,115,232,0.45); }
.chat-fab.open   { background: #5F6368; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
.chat-fab.open:hover { background: #3C4043; }

/* ── Panel ── */
.chat-panel {
  position: fixed;
  bottom: 84px;
  right: 24px;
  z-index: 499;
  width: 380px;
  max-height: calc(100vh - 120px);
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(32,33,36,0.2), 0 2px 8px rgba(32,33,36,0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #E8EAED;
}

/* ── Header ── */
.chat-header {
  padding: 14px 16px;
  border-bottom: 1px solid #E8EAED;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  background: #fff;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title {
  font-size: 13px;
  font-weight: 500;
  color: #202124;
  line-height: 1.2;
}

.header-sub {
  font-size: 11px;
  color: #5F6368;
  margin-top: 1px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.icon-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: #5F6368;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 150ms;
}
.icon-btn:hover { background: #F8F9FA; }

/* ── Empty / no patient ── */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px 20px;
  font-size: 13px;
  color: #80868B;
  text-align: center;
  line-height: 1.5;
}

/* ── Body ── */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  min-height: 0;
}

/* ── Welcome ── */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 0 8px;
  text-align: center;
}

.welcome-icon {
  font-size: 36px;
  color: #D2E3FC;
}

.welcome-title {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
}

.welcome-sub {
  font-size: 12px;
  color: #5F6368;
  line-height: 1.5;
  max-width: 280px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  margin-top: 12px;
}

.suggestion {
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid #DADCE0;
  background: #F8F9FA;
  font-size: 12px;
  color: #202124;
  cursor: pointer;
  font-family: 'Roboto', sans-serif;
  transition: background 150ms, border-color 150ms;
}
.suggestion:hover { background: #E8EAED; border-color: #BDC1C6; }

/* ── Messages ── */
.messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.message.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: #D2E3FC;
  color: #174EA6;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.msg-bubble {
  max-width: 82%;
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.message.user .msg-bubble {
  background: #1A73E8;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message.assistant .msg-bubble {
  background: #F8F9FA;
  color: #202124;
  border-bottom-left-radius: 4px;
  border: 1px solid #E8EAED;
}

/* Typing dots */
.msg-bubble.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 14px;
}
.msg-bubble.typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #BDC1C6;
  animation: typing-bounce 1.2s ease-in-out infinite;
}
.msg-bubble.typing span:nth-child(2) { animation-delay: 0.2s; }
.msg-bubble.typing span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); background: #BDC1C6; }
  30%           { transform: translateY(-5px); background: #9AA0A6; }
}

/* Error row */
.error-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #C5221F;
  padding: 8px 0;
}

/* ── Input ── */
.chat-input-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid #E8EAED;
  flex-shrink: 0;
  background: #fff;
}

.chat-input {
  flex: 1;
  resize: none;
  border: 1px solid #DADCE0;
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 13px;
  font-family: 'Roboto', sans-serif;
  color: #202124;
  line-height: 1.5;
  outline: none;
  min-height: 36px;
  max-height: 120px;
  overflow-y: auto;
  transition: border-color 150ms;
  field-sizing: content;
}
.chat-input:focus { border-color: #1A73E8; }
.chat-input::placeholder { color: #9AA0A6; }
.chat-input:disabled { background: #F8F9FA; }

.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: #1A73E8;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 150ms, opacity 150ms;
}
.send-btn:hover:not(:disabled) { background: #1765CC; }
.send-btn:disabled { background: #E8EAED; color: #BDC1C6; cursor: not-allowed; }

/* ── Panel transition ── */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: opacity 200ms, transform 200ms;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.97);
}

/* ── Message transition ── */
.msg-in-enter-active { transition: opacity 250ms, transform 250ms; }
.msg-in-enter-from   { opacity: 0; transform: translateY(6px); }
</style>
