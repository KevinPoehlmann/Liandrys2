<template>
  <div
    class="p-4 rounded shadow w-full h-full flex flex-col gap-4 bg-white dark:bg-gray-800"
    :class="team === 'red' ? 'items-end text-right' : ''"
  >
    <!-- Champion Selector -->
    <ChampionSelector
      :champion="config.champion"
      @select="config.champion = $event"
      :team="team"
    />

    <!-- Level Selector -->
    <div class="flex items-center gap-3">
      <span class="text-sm font-semibold">Level</span>
      <button @click="decreaseLevel" class="px-2 py-1 rounded bg-gray-200 dark:bg-gray-700">-</button>
      <span class="text-md font-mono w-6 text-center">{{ props.config.level }}</span>
      <button @click="increaseLevel" class="px-2 py-1 rounded bg-gray-200 dark:bg-gray-700">+</button>
    </div>

    <!-- Runes Placeholder -->
    <div class="p-3 border rounded bg-purple-100 dark:bg-purple-900 text-purple-900 dark:text-purple-100">
      <span class="text-sm">Runes Placeholder</span>
    </div>

    <!-- Summoner Spells Placeholder -->
    <div class="p-3 border rounded bg-yellow-100 dark:bg-yellow-900 text-yellow-900 dark:text-yellow-100">
      <span class="text-sm">Summoner Spells Placeholder</span>
    </div>

    <!-- Items Placeholder -->
    <div class="p-3 border rounded bg-green-100 dark:bg-green-900 text-green-900 dark:text-green-100">
      <span class="text-sm">Items Placeholder</span>
    </div>

    <!-- Stack Configuration Placeholder -->
    <div class="p-3 border rounded bg-indigo-100 dark:bg-indigo-900 text-indigo-900 dark:text-indigo-100">
      <span class="text-sm">Stacks Configuration Placeholder</span>
    </div>

    <!-- Action Buttons Placeholder -->
    <div class="p-3 border rounded bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-100">
      <span class="text-sm">Actions Placeholder (Abilities, Auto, Summoner Spells, Active Items)</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

import ChampionSelector from './ChampionSelector.vue'

const props = defineProps({
  team: {
    type: String,
    required: true,
    validator: (value) => ['blue', 'red'].includes(value)
  },
  config: {
    type: Object,
    required: true
  }
})

const level = ref(1)
const selectedChampionName = ref('')

const increaseLevel = () => {
  if (props.config.level < 18) props.config.level++
}
const decreaseLevel = () => {
  if (props.config.level > 1) props.config.level--
}

const selectChampion = () => {
  // Placeholder for future modal logic
}
</script>

<style scoped>
</style>
