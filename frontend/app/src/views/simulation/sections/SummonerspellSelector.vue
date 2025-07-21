<template>
  <div class="relative w-full">
    <div class="grid grid-cols-2 gap-4 p-3 border rounded bg-yellow-100 dark:bg-yellow-900 text-yellow-900 dark:text-yellow-100">
      <div
        v-for="(spell, index) in normalizedSpells"
        :key="index"
        @click="openSelector(index)"
        class="cursor-pointer flex flex-col items-center gap-1"
      >
        <img
          :src="getImageUrl(spell)"
          class="w-12 h-12 rounded bg-gray-300 dark:bg-gray-600 object-cover hover:border border-gray-300"
          :alt="spell?.name || 'Empty'"
        />
        <span class="text-xs text-gray-800 dark:text-gray-100">
          {{ spell?.name || 'Select' }}
        </span>
      </div>
    </div>

    <SummonerspellSelectModal
      v-if="isOpen"
      :available-spells="allSpells"
      :current-spells="spells"
      :replace-index="selectedIndex"
      @select="handleSelect"
    />
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'
import SummonerspellSelectModal from './SummonerspellSelectModal.vue'
import NoSpell from '@/assets/NoChampion.png' // temp placeholder

const props = defineProps({
  spells: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['update'])

const isOpen = ref(false)
const selectedIndex = ref(null)
const allSpells = inject("summonerspells", ref([]))


const normalizedSpells = computed(() => {
  const copy = [...props.spells]
  while (copy.length < 2) copy.push(null)
  return copy
})


const openSelector = (index) => {
  selectedIndex.value = index
  isOpen.value = true
}

const handleSelect = (payload) => {
  if (payload == null) {
    isOpen.value = false
    return
  }
  const updated = [...props.spells]
  if (payload.swap) {
    // Swap selectedIndex and otherIndex
    const other = payload.otherIndex
    const temp = updated[selectedIndex.value]
    updated[selectedIndex.value] = updated[other]
    updated[other] = temp
  } else {
    updated[payload.replaceIndex] = payload.spell
  }
  emit('update', updated)
  isOpen.value = false
}

const getImageUrl = (spell) => {
  return spell?.image?.group && spell?.image?.full
    ? `images/${spell.image.group}/${spell.image.full}`
    : NoSpell
}


</script>

<style scoped>
</style>