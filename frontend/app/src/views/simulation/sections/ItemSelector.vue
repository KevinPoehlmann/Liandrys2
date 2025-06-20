<template>
  <div @click="isOpen = true" class="p-4 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition w-full">
    <div class="grid grid-cols-3 gap-2 mb-2">
      <div
        v-for="(item, index) in normalizedItems"
        :key="index"
        class="w-12 h-12 rounded overflow-hidden bg-gray-300 dark:bg-gray-600 relative"
      >
        <img
          :src="getImageUrl(item)"
          class="w-full h-full object-cover"
          :alt="item?.name || 'Empty'"
        />
        <span
          v-if="item?.gold?.total"
          class="absolute bottom-0 right-0 text-[10px] bg-black bg-opacity-70 text-white px-1 rounded-tl"
        >
          {{ item.gold.total }}g
        </span>
      </div>
    </div>
    <div class="text-xs text-right text-gray-700 dark:text-gray-200">
      {{ totalCost }} gold
    </div>

    <ItemSelectModal
      v-if="isOpen"
      :available-items="allItems"
      :selected-items="items"
      @select="handleSelect"
    />
  </div>
</template>

<script setup>
import { computed, ref, inject } from 'vue'
import NoItem from '@/assets/emptyicon.png'
import ItemSelectModal from './ItemSelectModal.vue'

const props = defineProps({
  items: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['update'])
const isOpen = ref(false)
const allItems = inject("items", ref([]))



const normalizedItems = computed(() => {
  const copy = [...props.items]
  while (copy.length < 6) copy.push(null)
  return copy
})

const getImageUrl = (item) => {
  return item?.image?.group && item?.image?.full
    ? `images/${item.image.group}/${item.image.full}`
    : NoItem
}

const totalCost = computed(() => {
  return props.items.reduce((sum, item) => sum + (item?.gold || 0), 0)
})

const handleSelect = (payload) => {
  if (!payload) {
    isOpen.value = false
    return
  }
  console.log('ItemSelector: handleSelect', payload)
  const updated = [...props.items]

  if (payload.action === 'add') {
    const emptyIndex = updated.findIndex(i => i === null || i === undefined)
    console.log('ItemSelector: emptyIndex', emptyIndex)
    if (emptyIndex !== -1) {
      updated[emptyIndex] = payload.item
    }
  } else if (payload.action === 'remove') {
    updated[payload.index] = null
  }
  console.log('ItemSelector: updated', updated)

  emit('update', updated)
}
</script>

<style scoped>
</style>
