<template>
  <div
    @click="openChampionModal"
    class="cursor-pointer flex items-center gap-3 p-3 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition"
    :class="team === 'red' ? 'flex-row-reverse text-right' : ''"
  >
    <img
      :src="championImage"
      alt="Champion Icon"
      class="w-12 h-12 rounded object-cover bg-gray-300 dark:bg-gray-600"
    />
    <span class="text-lg font-medium">
      {{ champion?.name || 'Select Champion' }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import NoChampion from '@/assets/NoChampion.png'

const props = defineProps({
  champion: Object,
  team: {
    type: String,
    required: true,
    validator: (value) => ['blue', 'red'].includes(value)
  }
})

const emit = defineEmits(['select'])

const openChampionModal = () => {
  // Placeholder logic: replace with real modal later
  console.log('Champion modal should open')
}

const championImage = computed(() => {
  return props.champion?.image?.full ? `/path/to/champion/images/${props.champion.image.full}` : NoChampion
})
</script>

<style scoped>
</style>
