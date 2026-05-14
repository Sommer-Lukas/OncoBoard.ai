<script setup>
defineProps({
  actions: { type: Array, required: true },
})

const statusConfig = {
  complete: { bg: '#E6F4EA', color: '#188038' },
  pending: { bg: '#FEF7E0', color: '#B06000' },
  overdue: { bg: '#FCE8E6', color: '#C5221F' },
}

function initials(name) {
  return name.charAt(0).toUpperCase()
}
</script>

<template>
  <div class="tracker-card">
    <div class="tracker-header">
      <span class="material-symbols-outlined" style="font-size: 20px; color: #5F6368">task</span>
      <div class="tracker-title">Action Items</div>
      <div class="count-badge">{{ actions.length }} total</div>
    </div>
    <table class="actions-table">
      <thead>
        <tr>
          <th>Action</th>
          <th>Owner</th>
          <th>Due Date</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(action, idx) in actions" :key="idx">
          <td>{{ action.description }}</td>
          <td>
            <div class="owner-cell">
              <div class="avatar">{{ initials(action.owner) }}</div>
              {{ action.owner }}
            </div>
          </td>
          <td>{{ action.dueDate }}</td>
          <td>
            <span
              class="status-chip"
              :style="{
                background: (statusConfig[action.status] || statusConfig.pending).bg,
                color: (statusConfig[action.status] || statusConfig.pending).color,
              }"
            >
              {{ action.status }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.tracker-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(60, 64, 67, 0.1);
  overflow: hidden;
  margin-bottom: 24px;
}

.tracker-header {
  padding: 20px 24px;
  border-bottom: 1px solid #E8EAED;
  display: flex;
  align-items: center;
  gap: 12px;
}

.tracker-title {
  font-size: 16px;
  font-weight: 500;
  color: #202124;
  flex: 1;
}

.count-badge {
  font-size: 12px;
  color: #5F6368;
  background: #F8F9FA;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
}

.actions-table {
  width: 100%;
  border-collapse: collapse;
}

.actions-table th {
  text-align: left;
  padding: 12px 24px;
  font-size: 12px;
  font-weight: 500;
  color: #5F6368;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #E8EAED;
  background: #F8F9FA;
}

.actions-table td {
  padding: 16px 24px;
  font-size: 14px;
  color: #202124;
  border-bottom: 1px solid #F8F9FA;
}

.actions-table tbody tr:last-child td {
  border-bottom: none;
}

.owner-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #1A73E8;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 500;
  flex-shrink: 0;
}

.status-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  text-transform: capitalize;
}
</style>
