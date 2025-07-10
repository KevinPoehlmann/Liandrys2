<template>
  <div class="relative w-fit">
    <div @click="isOpen = true" class="p-4 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition">
      <p
        v-if="!(primaryRunes.length || secondaryRunes.length || statShards.length)">
        Select Runes
      </p>
      <div class="flex gap-4">
        <!-- Primary runes -->
        <div class="flex flex-col gap-1">
          <img
            v-for="(rune, index) in primaryRunes"
            :key="'prim-' + index"
            :src="getImageUrl(rune)"
            :alt="rune.name"
            class="w-10 h-10 object-cover rounded-full bg-gray-300 dark:bg-gray-700"
          />
        </div>

        <!-- Secondary runes -->
        <div class="flex flex-col gap-1">
          <img
            v-for="(rune, index) in secondaryRunes"
            :key="'sec-' + index"
            :src="getImageUrl(rune)"
            :alt="rune.name"
            class="w-10 h-10 object-cover rounded-full bg-gray-300 dark:bg-gray-700"
          />
        </div>

        <!-- Stat shards -->
        <div class="flex flex-col gap-1">
          <img
            v-for="(rune, index) in statShards"
            :key="'shard-' + index"
            :src="getImageUrl(rune)"
            :alt="rune.name"
            class="w-8 h-8 object-cover rounded-full bg-black"
          />
        </div>
      </div>
    </div>
    <RuneSelectModal
    v-if="isOpen"
    :available-runes="allRunes"
    :selected-runes="runes"
    @select="handleSelect"
    />
  </div>
</template>

<script setup>
import { computed, ref, inject, onMounted } from 'vue'
import NoItem from '@/assets/emptyicon.png'
import RuneSelectModal from './RuneSelectModal.vue'

const props = defineProps({
  runes: {
    type: Object,
    required: true
  }
})



const emit = defineEmits(['update'])
const isOpen = ref(false)
const allRunes = inject("runes", ref([]))

let secondaryRuneOrder = []


const primaryRunes = computed(() => props.runes.primary.runes.filter(Boolean))
const secondaryRunes = computed(() => props.runes.secondary.runes.filter(Boolean))
const statShards = computed(() => props.runes.shards.filter(Boolean))

const getImageUrl = (rune) => {
  return rune?.image?.group && rune?.image?.full
    ? `images/${rune.image.group}/${rune.image.full}`
    : NoItem
}

const handleSelect = (payload) => {
  if (!payload) {
    isOpen.value = false
    return
  }
  const updated = JSON.parse(JSON.stringify(props.runes))

  switch (payload.tree) {
    case 'prim':
      if (payload.row === -1) {
        updated.primary.treeId = payload.rune
        if (updated.secondary.treeId === payload.rune) {
          updated.secondary.treeId = null
          updated.secondary.runes = Array(4).fill(null)
          secondaryRuneOrder = []
        }
      }
      else {
        updated.primary.runes[payload.row] = payload.rune
      }
      break
    case 'sec':
      if (payload.row === -1) {
        updated.secondary.treeId = payload.rune
        updated.secondary.runes = Array(4).fill(null)
        secondaryRuneOrder = []
      }
      else {
        if (secondaryRuneOrder.length === 2) {
          const oldestRune = secondaryRuneOrder.shift()
          updated.secondary.runes[oldestRune] = null
        }
        updated.secondary.runes[payload.row] = payload.rune
        secondaryRuneOrder.push(payload.row)
      }
      break
    case 'shards':
      updated.shards[payload.row] = payload.rune
      break
  }
  emit('update', updated)
}
</script>

<style scoped>
</style>