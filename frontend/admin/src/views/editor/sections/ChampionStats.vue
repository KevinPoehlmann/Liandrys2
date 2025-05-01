<template>
  <div class="space-y-4">
    <!-- Read-only Types -->
    <div class="flex gap-8">
      <div><strong>Range Type:</strong> {{ champion.range_type }}</div>
      <div><strong>Resource Type:</strong> {{ champion.resource_type }}</div>
    </div>

    <!-- Editable Stat Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
      <div v-for="field in editableFields" :key="field.key">
        <label class="block text-sm font-medium mb-1">{{ field.label }}</label>
        <input
          type="number"
          v-model.number="localStats[field.key]"
          class="w-full px-2 py-1 border rounded"
        />
      </div>
    </div>

    <!-- Changes List -->
    <div v-if="champion.changes?.length" class="bg-yellow-100 border border-yellow-400 p-4 rounded">
      <h3 class="font-semibold mb-2">Manual Patch Changes to Review:</h3>
      <ul class="list-disc ml-5 text-sm">
        <li v-for="change in champion.changes" :key="change">{{ change }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, toRefs } from 'vue'
const props = defineProps({ champion: Object })
const emit = defineEmits(['update'])

const { champion } = toRefs(props)
const localStats = ref({})

// Initialize local editable values
watch(champion, () => {
  localStats.value = { ...champion.value }
}, { immediate: true })

watch(localStats, () => {
  const diff = {}

  for (const key in localStats.value) {
    if (localStats.value[key] !== champion.value[key]) {
      diff[key] = localStats.value[key]
    }
  }

  if (Object.keys(diff).length) {
    emit('update', diff)
  }
}, { deep: true })

const editableFields = [
  { key: 'hp', label: 'HP' },
  { key: 'hp_per_lvl', label: 'HP per Level' },
  { key: 'ad', label: 'AD' },
  { key: 'ad_per_lvl', label: 'AD per Level' },
  { key: 'mana', label: 'Mana' },
  { key: 'mana_per_lvl', label: 'Mana per Level' },
  { key: 'movementspeed', label: 'Movement Speed' },
  { key: 'armor', label: 'Armor' },
  { key: 'armor_per_lvl', label: 'Armor per Level' },
  { key: 'mr', label: 'MR' },
  { key: 'mr_per_lvl', label: 'MR per Level' },
  { key: 'attackrange', label: 'Attack Range' },
  { key: 'hp_regen', label: 'HP Regen' },
  { key: 'hp_regen_per_lvl', label: 'HP Regen per Level' },
  { key: 'mana_regen', label: 'Mana Regen' },
  { key: 'mana_regen_per_lvl', label: 'Mana Regen per Level' },
  { key: 'attackspeed', label: 'Attack Speed' },
  { key: 'attackspeed_ratio', label: 'Attack Speed Ratio' },
  { key: 'attackspeed_per_lvl', label: 'Attack Speed per Level' },
  { key: 'attack_windup', label: 'Attack Windup' },
  { key: 'windup_modifier', label: 'Windup Modifier' },
  { key: 'missile_speed', label: 'Missile Speed' },
]
</script>
