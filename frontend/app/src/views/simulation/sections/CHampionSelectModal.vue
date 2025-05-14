<template>
  <div class="fixed inset-0 bg-black bg-opacity-60 flex justify-center items-center z-50">
    <div class="bg-white dark:bg-gray-800 p-6 rounded-lg w-full max-w-4xl max-h-[80vh] overflow-y-auto">

      <!-- Search Bar -->
      <input
        v-model="filter"
        placeholder="Search champions..."
        class="mb-4 w-full p-2 rounded border dark:bg-gray-700 dark:border-gray-600 dark:text-white"
      />

      <!-- Champion Grid -->
      <div class="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-3">
        <div
          v-for="champ in filteredChampions"
          :key="champ.key"
          @click="selectChampion(champ)"
          class="cursor-pointer hover:scale-105 transition text-center"
        >
          <img
            :src="champ.imageUrl"
            alt="Champion"
            class="rounded mx-auto w-16 h-16 object-cover"
          />
          <p class="text-sm mt-1 text-gray-800 dark:text-gray-100">{{ champ.name }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  allChampions: Array
})
const emit = defineEmits(['select'])

const filter = ref('')

const filteredChampions = computed(() => {
  if (!filter.value.trim()) return props.allChampions
  return props.allChampions.filter(champ =>
    champ.name.toLowerCase().includes(filter.value.toLowerCase())
  )
})

const selectChampion = (champ) => {
  emit('select', champ)
}
</script>

<style scoped>
</style>
