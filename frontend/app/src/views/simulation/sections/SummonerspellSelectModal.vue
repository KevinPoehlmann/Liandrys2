<template>
  <div class="fixed inset-0 bg-black bg-opacity-60 flex justify-center items-center z-50" @click="handleBackdropClick">
    <div ref="modalContent" class="bg-white dark:bg-gray-800 p-6 rounded-lg w-full max-w-2xl max-h-[80vh] overflow-y-auto">
      <h2 class="text-lg font-semibold mb-4 text-center text-gray-900 dark:text-gray-100">Select Summoner Spell</h2>

      <div class="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-4">
        <div
          v-for="spell in availableSpells"
          :key="spell.key"
          @click="handleSelect(spell)"
          class="flex flex-col items-center cursor-pointer text-center"
          :class="{ 'opacity-50 pointer-events-none': isAlreadyUsed(spell) }"
        >
          <img
            :src="getImageUrl(spell)"
            class="w-14 h-14 rounded bg-gray-300 dark:bg-gray-700 object-cover"
            :alt="spell.name"
          />
          <span class="text-xs mt-1 text-gray-900 dark:text-gray-100">{{ spell.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import NoSpell from '@/assets/NoChampion.png'

const props = defineProps({
  availableSpells: Array,
  currentSpells: Array,
  replaceIndex: Number
})

const emit = defineEmits(['select'])

const modalContent = ref(null)

const isAlreadyUsed = (spell) => {
  return props.currentSpells.some((s, i) => s?.key === spell.key && i !== props.replaceIndex)
}

const handleSelect = (spell) => {
  const otherIndex = props.currentSpells.findIndex((s, i) => s?.key === spell.key && i !== props.replaceIndex)
  if (otherIndex !== -1) {
    emit('select', { swap: true, otherIndex })
  } else {
    emit('select', { spell, replaceIndex: props.replaceIndex })
  }
}

const getImageUrl = (spell) => {
  return spell?.image?.group && spell?.image?.full
    ? `images/${spell.image.group}/${spell.image.full}`
    : NoSpell
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
