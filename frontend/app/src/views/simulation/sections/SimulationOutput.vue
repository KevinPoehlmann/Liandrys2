<template>
  <div class="p-4 border rounded bg-gray-100 dark:bg-gray-800 w-full">
    <div v-if="error" class="text-red-600 mt-2">{{ error }}</div>
    <h2 class="text-lg font-semibold mb-2 text-gray-900 dark:text-gray-100">Combo</h2>

    <div class="flex gap-1 flex-wrap items-center mb-4 min-h-[2.5rem]">
      <div
        v-for="(action, index) in combo"
        :key="index"
        class="w-10 h-10 rounded overflow-hidden relative cursor-pointer border-2"
        :class="action.actor === 'blue' ? 'border-blue-500' : 'border-red-500'"
        @click="remove(index)"
      >
        <img :src="getIcon(action)" class="w-full h-full object-cover" />
        <span class="absolute top-0 left-0 text-[10px] bg-black bg-opacity-70 text-white px-1 rounded-tl">
          {{ action.action_type.toUpperCase() }}
        </span>
      </div>
    </div>

    <div class="text-m text-gray-800 dark:text-gray-100">
      <p><strong>Damage:</strong> {{ safeDamage }} HP</p>
      <p><strong>Time:</strong> {{ safeTime }} seconds</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import NoIcon from '@/assets/NoChampion.png'
import autoAttack from '@/assets/autoattack.png'

const props = defineProps({
  blueConfig: Object,
  redConfig: Object,
  combo: Array,
  damage: Number,
  time: Number,
  error: String
})

const safeDamage = ref(0)
const safeTime = ref(0)

watch(() => props.damage, (newVal) => {
  if (typeof newVal === 'number') {
    safeDamage.value = newVal
  }
})

watch(() => props.time, (newVal) => {
  if (typeof newVal === 'number') {
    safeTime.value = newVal
  }
})

const emit = defineEmits(['remove'])

const remove = (index) => {
  emit('remove', index)
}

const getIcon = (action) => {
  const actor = action.actor === "blue" ? props.blueConfig : props.redConfig
  const upper = action.action_type.toUpperCase()

  if (upper === 'AA') return autoAttack
  if (['Q', 'W', 'E', 'R'].includes(upper)) {
    const spell = actor.champion?.[upper.toLowerCase()]
    return spell?.image ? `images/${spell.image.group}/${spell.image.full}` : NoIcon
  }
  if (upper.startsWith('S')) {
    const i = parseInt(upper[1]) - 1
    const spell = actor.summonerspells?.[i]
    return spell?.image ? `images/${spell.image.group}/${spell.image.full}` : NoIcon
  }
  if (upper.startsWith('I')) {
    const i = parseInt(upper[1]) - 1
    const item = actor.items?.[i]
    return item?.image ? `images/${item.image.group}/${item.image.full}` : NoIcon
  }
  return NoIcon
}
</script>

<style scoped>
</style>
