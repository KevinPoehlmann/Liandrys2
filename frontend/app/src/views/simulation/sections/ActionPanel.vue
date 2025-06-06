<template>
  <div class="p-4 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition w-full">
    <div class="flex gap-2 flex-wrap items-center">
      <!-- Auto Attack -->
      <button @click="addAction('aa')" class="action-tile cursor-pointer">
        <img :src="autoAttack" class="tile-image" alt="AA" />
      </button>

      <!-- Abilities with + / - buttons -->
      <div
        v-for="slot in ['q', 'w', 'e', 'r']"
        :key="slot"
        class="flex flex-col items-center"
      >
        <button @click="increase(slot)" class="text-xs text-gray-700 dark:text-gray-300 cursor-pointer">▲</button>
        <button @click="addAction(slot)" class="action-tile relative cursor-pointer">
          <img :src="abilityIcons[slot]" class="tile-image" :alt="slot.toUpperCase()" />
          <span class="absolute top-0 left-0 text-[10px] bg-black bg-opacity-70 text-white px-1 rounded-br">
            {{ slot.toUpperCase() }}
          </span>
          <span
            class="absolute top-0 right-0 text-[10px] bg-black bg-opacity-70 text-white px-1 rounded-tl"
          >
            {{ props.abilityPoints[slot] || 0 }}
          </span>
        </button>
        <button @click="decrease(slot)" class="text-xs text-gray-700 dark:text-gray-300 cursor-pointer">▼</button>
      </div>

      <!-- Summoner Spells -->
      <button
        v-for="entry in activeSummonerSpells"
        :key="'s' + (entry.index + 1)"
        @click="addAction(`s${entry.index + 1}`)"
        class="action-tile cursor-pointer"
      >
        <img :src="getImageUrl(entry.spell)" class="tile-image" :alt="entry.spell.name" />
      </button>

      <!-- Active Items -->
      <button
        v-for="entry in activeItems"
        :key="'i' + (entry.index + 1)"
        @click="addAction(`i${entry.index + 1}`)"
        class="action-tile cursor-pointer"
      >
        <img :src="getImageUrl(entry.item)" class="tile-image" :alt="entry.item.name" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import autoAttack from '@/assets/autoattack.png'

const props = defineProps({
  team: String,
  champion: Object,
  summonerspells: Array,
  items: Array,
  abilityPoints: Object
})

const emit = defineEmits(['add', 'addPoint', 'removePoint'])

const addAction = (action_type) => {
  emit('add', {
    action_type,
    actor: props.team,
    target: props.team === 'blue' ? 'red' : 'blue'
  })
}

const increase = (slot) => {
  emit('addPoint', slot)
}
const decrease = (slot) => {
  emit('removePoint', slot)
}

const activeSummonerSpells = computed(() => {
  const copy = [...props.summonerspells]
  while (copy.length < 2) copy.push(null)
  return copy
    .map((s, i) => ({ spell: s, index: i }))
    .filter(entry => entry.spell)
})

const activeItems = computed(() => {
  const copy = [...props.items]
  while (copy.length < 6) copy.push(null)
  return copy
    .map((item, i) => ({ item, index: i }))
    .filter(entry => entry.item?.active)
})

const abilityIcons = computed(() => {
  const result = { q: autoAttack, w: autoAttack, e: autoAttack, r: autoAttack }
  if (!props.champion) return result
  for (const slot of ['q', 'w', 'e', 'r']) {
    const spell = props.champion[slot]
    if (spell?.image?.group && spell?.image?.full) {
      result[slot] = `images/${spell.image.group}/${spell.image.full}`
    }
  }
  return result
})

const getImageUrl = (entry) => {
  return entry?.image?.group && entry?.image?.full
    ? `images/${entry.image.group}/${entry.image.full}`
    : autoAttack
}
</script>

<style scoped>
.action-tile {
  @apply w-12 h-12 rounded overflow-hidden bg-gray-200 dark:bg-gray-700 p-0;
}
.tile-image {
  @apply w-full h-full object-cover;
}
</style>
