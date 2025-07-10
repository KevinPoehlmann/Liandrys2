<template>
  <div class="w-full">
    <div
      @click="isOpen = true"
      class="cursor-pointer flex items-center gap-3 p-3 border rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition"
      :class="team === 'red' ? 'flex-row-reverse text-right' : ''"
    >
      <img
        :src="championImage"
        alt="Champion Icon"
        class="w-12 h-12 rounded object-cover bg-gray-300 dark:bg-gray-600"
      />
      <span class="text-xl font-medium">
        {{ champion?.name || 'Select Champion' }}
      </span>
    </div>

    <ChampionSelectModal
      v-if="isOpen"
      :all-champions="allChampions"
      @select="handleSelect"
    />
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'
import ChampionSelectModal from './ChampionSelectModal.vue'
import NoChampion from '@/assets/NoChampion.png'

const props = defineProps({
  champion: Object,
  team: {
    type: String,
    required: true,
    validator: (value) => ['blue', 'red'].includes(value)
  }
})

const emit = defineEmits(['select'])

const isOpen = ref(false)
const allChampions = inject('champions', ref([]))


const handleSelect = (champ) => {
  emit('select', champ)
  isOpen.value = false
}

const championImage = computed(() => {
  return props.champion?.image?.full ? `images/${props.champion.image.group}/${props.champion.image.full}` : NoChampion
})

</script>

<style scoped>
</style>
