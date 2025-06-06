<template>
  <div
    class="p-4 rounded shadow w-full h-full flex flex-col gap-4 bg-white dark:bg-gray-800"
    :class="team === 'red' ? 'items-end text-right' : ''"
  >
    <!-- Champion Selector -->
    <ChampionSelector
      :champion="config.champion"
      @select="selectChampion"
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
    <SummonerspellSelector
      :spells="config.summonerspells"
      @update="updateSummonerspells"
    />

    <!-- Items Placeholder -->
    <ItemSelector
      :items="config.items"
      @update="updateItems"
    />

    <!-- Stack Configuration Placeholder -->
    <div class="p-3 border rounded bg-indigo-100 dark:bg-indigo-900 text-indigo-900 dark:text-indigo-100">
      <span class="text-sm">Stacks Configuration Placeholder</span>
    </div>

    <!-- Action Buttons Placeholder -->
     <ActionPanel
      :team="team"
      :champion="config.champion"
      :summonerspells="config.summonerspells"
      :items="config.items"
      :abilityPoints="config.ability_points"
      @add="(action) => emit('add', action)"
      @addPoint="increaseAbilityPoint"
      @removePoint="decreaseAbilityPoint"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'

import ActionPanel from './ActionPanel.vue'
import ChampionSelector from './ChampionSelector.vue'
import SummonerspellSelector from './SummonerspellSelector.vue'
import ItemSelector from './ItemSelector.vue'

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


const emit = defineEmits(['add'])

const increaseLevel = () => {
  if (props.config.level < 18) props.config.level++
}
const decreaseLevel = () => {
  if (props.config.level > 1) props.config.level--
}

const selectChampion = (value) => {
  props.config.champion = value
}
const updateSummonerspells = (value) => {
  props.config.summonerspells = value
}
const updateItems = (value) => {
  props.config.items = value
}
const increaseAbilityPoint = (slot) => {
  const points = props.config.ability_points
  const champion = props.config.champion
  const level = props.config.level

  if (!champion) return

  const maxRank = champion[slot]?.maxrank ?? 5
  const current = points[slot]
  const total = Object.values(points).reduce((acc, v) => acc + v, 0)

  if (current >= maxRank || total >= level) return

  if (slot === 'r') {
    const allowedR = Math.floor((level - 1) / 5) // R at 6,11,16
    if (current >= allowedR) return
  }
  else {
    const allowedQWE = Math.floor((level - 1) / 2) 
    if (current > allowedQWE) return
  }

  points[slot]++
}
const decreaseAbilityPoint = (slot) => {
  const points = props.config.ability_points
  if (points[slot] > 0) {
    points[slot]--
  }
}
</script>

<style scoped>
</style>
