<template>
  <div class="fixed inset-0 bg-black bg-opacity-60 flex justify-center items-center z-50" @click="handleBackdropClick">
    <div ref="modalContent" class="flex gap-12 bg-white dark:bg-gray-800 p-6 rounded-lg w-full max-w-5xl max-h-[90vh] overflow-y-auto">
      <div>
        <div class="flex gap-3 mb-6">
          <div
            v-for="(info, id) in runeTrees"
            :key="id"
            @click="handleSelect('prim', -1, Number(id))"
            >
            <img
              :src="info.image"
              :alt="info.name"
              :class="[
                'w-14 h-14 object-cover rounded-full bg-gray-300 dark:bg-gray-700 cursor-pointer hover:scale-105',
                props.selectedRunes.primary.treeId === Number(id) ? 'ring-2 ring-amber-400' : '']" />
          </div>
        </div>
        <div class="flex flex-col gap-y-2">
          <div
            v-for="(row, rowIndex) in primaryRunes"
            :key="rowIndex"
            class="flex gap-1"
          >
            <div
              v-for="rune in row"
              :key="rune.id"
              @click="handleSelect('prim', rune.row, rune)"
            >
              <img
                :src="getImageUrl(rune.image.full ? rune : null)"
                :alt="rune.name"
                :class="[
                  'w-12 h-12 object-cover rounded-full bg-gray-300 dark:bg-gray-700 cursor-pointer hover:scale-105',
                  props.selectedRunes.primary.runes[rune.row]?.rune_id === rune.rune_id
                    ? 'ring-2 ring-amber-400'
                    : ''
                ]"
              />
            </div>
          </div>
        </div>
      </div>
      <div>
        <div class="flex gap-3 mb-6">
          <div
            v-for="(info, id) in secondaryTrees"
            :key="id"
            @click="handleSelect('sec', -1, Number(id))"
            >
            <img
              :src="info.image"
              :alt="info.name"
              :class="[
                'w-14 h-14 object-cover rounded-full bg-gray-300 dark:bg-gray-700 cursor-pointer hover:scale-105',
                props.selectedRunes.secondary.treeId === Number(id) ? 'ring-2 ring-amber-400' : '']" />
          </div>
        </div>
        <div class="flex flex-col gap-y-2">
          <div
            v-for="(row, rowIndex) in secondaryRunes.slice(1)"
            :key="rowIndex"
            class="flex gap-1"
            >
            <div
              v-for="rune in row"
              :key="rune.id"
              @click="handleSelect('sec', rune.row, rune)"
              >
              <img
                :src="getImageUrl(rune.image.full ? rune : null)"
                :alt="rune.name"
                :class="[
                  'w-12 h-12 object-cover rounded-full bg-gray-300 dark:bg-gray-700 cursor-pointer hover:scale-105',
                  props.selectedRunes.secondary.runes[rune.row]?.rune_id === rune.rune_id
                    ? 'ring-2 ring-amber-400'
                    : '']" />
            </div>
          </div>
        </div>
      </div>
      <div class="flex flex-col gap-y-2 mt-24">
        <div
          v-for="(row, rowIndex) in shards"
          :key="rowIndex"
          class="flex gap-1"
          >
          <div
            v-for="rune in row"
            :key="rune.id"
            @click="handleSelect('shards', rune.row, rune)"
            >
            <img
              :src="getImageUrl(rune.image.full ? rune : null)"
              :alt="rune.name"
              :class="[
                'w-10 h-10 object-cover rounded-full bg-black dark:bg-gray-700 cursor-pointer hover:scale-105',
                props.selectedRunes.shards[rune.row]?.rune_id === rune.rune_id ? 'ring-2 ring-amber-400' : '']" />
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
  availableRunes: Array,
  selectedRunes: Object
})

const runeTrees = ref({})

onMounted(async () => {
  const res = await fetch('/rune/trees/')
  runeTrees.value = await res.json()
})

const emit = defineEmits(['select'])

const filter = ref('')
const modalContent = ref(null)

const secondaryTrees = computed(() => {
  if (!props.selectedRunes.primary.treeId) return []

  const primaryTreeId = props.selectedRunes.primary.treeId
  const result = {}
  for (const [id, tree] of Object.entries(runeTrees.value)) {
    if (Number(id) !== primaryTreeId) {
      result[Number(id)] = tree
    }
  }
  return result
})

const primaryRunes = computed(() => groupRunesByTree(props.selectedRunes.primary.treeId))

const secondaryRunes = computed(() => groupRunesByTree(props.selectedRunes.secondary.treeId))

const shards = computed(() => groupRunesByTree(0))


function groupRunesByTree(treeId) {
  const filtered = props.availableRunes.filter(rune => rune.tree_id === treeId)
  const result = [[], [], [], []]
  for (const rune of filtered) {
    result[rune.row].push(rune)
  }
  for (const row of result) {
    row.sort((a, b) => a.sort_order - b.sort_order)
  }
  return result
}

const getImageUrl = (rune) => {
  return rune?.image?.group && rune?.image?.full
    ? `images/${rune.image.group}/${rune.image.full}`
    : NoItem
}

const handleSelect = (tree, row, rune) => {
  emit('select', { tree, row, rune })
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
