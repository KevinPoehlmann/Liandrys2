<template>
  <div class="p-4 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition w-full">
    <div class="flex gap-2 flex-wrap items-center">
      <!-- Auto Attack -->
      <button @click="addAction('aa')" class="action-tile">
        <img :src="autoAttack" class="tile-image" alt="AA" />
      </button>
      
      <!-- Abilities -->
      <button
      v-for="slot in ['q', 'w', 'e', 'r']"
      :key="slot"
      @click="addAction(slot)"
      class="action-tile"
      >
        <img :src="abilityIcons[slot]" class="tile-image" :alt="slot.toUpperCase()" />
      </button>
      
      <!-- Summoner Spells -->
      <button
      v-for="entry in activeSummonerSpells"
      :key="'s' + (entry.index + 1)"
      @click="addAction(`s${entry.index + 1}`)"
      class="action-tile"
      >
        <img :src="getImageUrl(entry.spell)" class="tile-image" :alt="entry.spell.name" />
      </button>
      
      <!-- Active Items -->
      <button
      v-for="entry in activeItems"
      :key="'i' + (entry.index + 1)"
      @click="addAction(`i${entry.index + 1}`)"
      class="action-tile"
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
  items: Array
})

const emit = defineEmits(['add'])

const addAction = (action_type) => {
  emit('add', {
    action_type,
    actor: props.team,
    target: props.team === 'blue' ? 'red' : 'blue'
  })
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
