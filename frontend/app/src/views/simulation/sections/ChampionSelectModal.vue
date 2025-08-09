<template>
  <div class="fixed inset-0 bg-black bg-opacity-60 flex justify-center items-center z-50" @click="handleBackdropClick">
    <div ref="modalContent" class="bg-white dark:bg-gray-800 p-6 rounded-lg w-full max-w-4xl">

      <!-- Sticky Search Bar -->
      <div class="bg-white dark:bg-gray-800 pb-4">
        <input
          v-model="filter"
          autofocus
          placeholder="Search champions..."
          class="w-full p-2 rounded border dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        />
      </div>

      <!-- Champion Grid -->
      <div class="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-3 h-[60vh] overflow-y-auto overflow-x-hidden items-start pt-4">
        <div
          v-for="champ in filteredChampions"
          :key="champ.key"
          @click="selectChampion(champ)"
          class="cursor-pointer hover:scale-105 transition text-center"
        >
          <img
            :src="`images/${champ.image.group}/${champ.image.full}`"
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
const modalContent = ref(null)

const filteredChampions = computed(() => {
  if (!filter.value.trim()) return props.allChampions
  return props.allChampions.filter(champ =>
    champ.name.toLowerCase().includes(filter.value.toLowerCase())
  )
})

const selectChampion = (champ) => {
  emit('select', champ)
}

const handleBackdropClick = (event) => {
  setTimeout(() => {
    if (!modalContent.value) return
    if (!modalContent.value.contains(event.target)) {
      emit('select', null)
    }
  })
}
</script>

<style scoped>
</style>
