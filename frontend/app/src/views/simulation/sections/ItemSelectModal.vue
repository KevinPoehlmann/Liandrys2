<template>
  <div class="fixed inset-0 bg-black bg-opacity-60 flex justify-center items-center z-50" @click="handleBackdropClick">
    <div ref="modalContent" class="bg-white dark:bg-gray-800 p-6 rounded-lg w-full max-w-5xl">

      <!-- Search Bar -->
      <div class="sticky top-0 z-10 bg-white dark:bg-gray-800 pb-4">
        <input
          v-model="filter"
          autofocus
          placeholder="Search champions..."
          class="w-full p-2 rounded border dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        />
      </div>

      <div class="flex gap-6">
        <!-- Item Grid -->
        <div class="flex-1 grid grid-cols-5 sm:grid-cols-6 md:grid-cols-8 gap-3 h-[60vh] overflow-y-auto">
          <div
            v-for="item in filteredItems"
            :key="item.id"
            @click="handleSelect(item)"
            class="flex flex-col items-center cursor-pointer text-center hover:scale-105"
          >
            <img
              :src="getImageUrl(item)"
              :alt="item.name"
              class="w-12 h-12 object-cover rounded bg-gray-300 dark:bg-gray-700"
            />
            <p class="text-xs mt-1 text-gray-900 dark:text-gray-100 truncate w-full">{{ item.name }}</p>
          </div>
        </div>

        <!-- Current Items Grid -->
        <div class="w-32">
          <p class="text-sm mb-2 text-center text-gray-900 dark:text-gray-100">Selected</p>
          <div class="grid grid-cols-3 mb-2">
            <div
              v-for="(item, index) in normalizedItems"
              :key="index"
              @click="handleRemove(index)"
              class="w-12 h-12 rounded overflow-hidden bg-gray-300 dark:bg-gray-600 relative cursor-pointer  hover:scale-105"
            >
              <img
                :src="getImageUrl(item)"
                class="w-full h-full object-cover"
                :alt="item?.name || 'Empty'"
              />
            </div>
          </div>
          <div class="text-xs text-right text-gray-700 dark:text-gray-200">
            {{ totalCost }} gold
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import NoItem from '@/assets/emptyicon.png'

const props = defineProps({
  availableItems: Array,
  selectedItems: Array
})

const emit = defineEmits(['select'])

const filter = ref('')
const modalContent = ref(null)

const normalizedItems = computed(() => {
  const copy = [...props.selectedItems]
  while (copy.length < 6) copy.push(null)
  return copy
})

const filteredItems = computed(() => {
  if (!filter.value.trim()) return props.availableItems
  return props.availableItems.filter(item =>
    item.name.toLowerCase().includes(filter.value.toLowerCase())
  )
})

const totalCost = computed(() => {
  return props.selectedItems.reduce((sum, item) => sum + (item?.gold || 0), 0)
})

const getImageUrl = (item) => {
  return item?.image?.group && item?.image?.full
    ? `images/${item.image.group}/${item.image.full}`
    : NoItem
}

const handleSelect = (item) => {
  emit('select', { action: 'add', item })
}

const handleRemove = (index) => {
  emit('select', { action: 'remove', index })
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
