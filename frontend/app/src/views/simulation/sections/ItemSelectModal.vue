<template>
  <div class="fixed inset-0 bg-black bg-opacity-60 flex justify-center items-center z-50" @click="handleBackdropClick">
    <div ref="modalContent" class="bg-white dark:bg-gray-800 p-6 rounded-lg w-full max-w-5xl">

      <!-- Search Bar -->
      <div class="bg-white dark:bg-gray-800 pb-4">
        <input
          v-model="filter"
          autofocus
          placeholder="Search champions..."
          class="w-full p-2 rounded border dark:bg-gray-700 dark:border-gray-600 dark:text-white"
        />
      </div>

      <div class="flex gap-6">
        <!-- Item Grid -->
        <div class="flex-1 h-[60vh] overflow-y-auto overflow-x-hidden">
          <div v-for="cls in DISPLAY_ORDER" :key="cls" class="mb-6">
            <div
              class="flex items-center gap-2 cursor-pointer select-none mb-2"
              @click="toggleGroup(cls)"
            >
              <span class="text-sm">
                {{ openGroups[cls] ? '▲' : '▼' }}
              </span>
              <h3 class="text-md font-semibold text-gray-900 dark:text-gray-100">{{ cls }}</h3>
              <div class="flex-grow border-b border-gray-300 dark:border-gray-600 mr-2"></div>
            </div>
            <transition name="fade">
              <div v-if="filteredGroups[cls] && filteredGroups[cls].length && !openGroups[cls]" class="grid grid-cols-5 sm:grid-cols-6 md:grid-cols-8 gap-3">
                <div
                v-for="item in filteredGroups[cls]"
                :key="item.id"
                @click="handleSelect(item)"
                class="flex flex-col items-center cursor-pointer text-center hover:scale-105 transition"
                >
                  <img
                  :src="getImageUrl(item)"
                  :alt="item.name"
                  class="w-12 h-12 object-cover rounded bg-gray-300 dark:bg-gray-700"
                  />
                  <p class="text-xs mt-1 text-gray-900 dark:text-gray-100 truncate w-full">{{ item.name }}</p>
                </div>
              </div>
            </transition>
          </div>
        </div>

        <!-- Current Items Grid -->
        <div class="w-32">
          <p class="text-sm mb-2 text-center text-gray-900 dark:text-gray-100">Selected</p>
          <div class="grid grid-cols-3 gap-1 mb-2">
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
import { computed, ref, onMounted } from 'vue'
import NoItem from '@/assets/emptyicon.png'

const props = defineProps({
  availableItems: Array,
  selectedItems: Array
})

const emit = defineEmits(['select'])

const filter = ref('')
const modalContent = ref(null)
const itemClasses = ref([])
const groupedItems = ref({})
const openGroups = ref({})

const DISPLAY_ORDER = [
  "starter item",
  "trinket item",
  "consumable item",
  "boots item",
  "Basic",
  "epic item",
  "legendary item"
]

onMounted(async () => {
  itemClasses.value = await fetch('/item/itemclass/').then(res => res.json())

  const groups = {}
  for (const cls of itemClasses.value) {
    groups[cls] = props.availableItems.filter(item => item.class_ === cls)
  }
  groupedItems.value = groups
})

const normalizedItems = computed(() => {
  const copy = [...props.selectedItems]
  while (copy.length < 6) copy.push(null)
  return copy
})

const filteredGroups = computed(() => {
  const query = filter.value.trim().toLowerCase()
  const  groups = {}
  for (const cls of DISPLAY_ORDER) {
    const items = groupedItems.value[cls] || []
    groups[cls] = query
      ? items.filter(item => item.name.toLowerCase().includes(query))
      : items
  }
  return groups
})

const totalCost = computed(() => {
  return props.selectedItems.reduce((sum, item) => sum + (item?.gold || 0), 0)
})

function toggleGroup(cls) {
  openGroups.value[cls] = !openGroups.value[cls]
}


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
