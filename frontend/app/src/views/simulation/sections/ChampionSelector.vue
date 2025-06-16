<template>
  <div>
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
      <span class="text-lg font-medium">
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
import { ref, computed, watch, inject } from 'vue'
import ChampionSelectModal from './Something.vue'
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
const allChampions = ref([])

const patch = ref('')
const hotfix = ref('')

const fetchChampions = async () => {
  if (!patch.value) return
  let url = `/champion/all/${patch.value}`
  if (hotfix.value) url += `?hotfix=${encodeURIComponent(hotfix.value)}`
  const res = await fetch(url)
  allChampions.value = await res.json()
}

const handleSelect = (champ) => {
  emit('select', champ)
  isOpen.value = false
}

const championImage = computed(() => {
  return props.champion?.image?.full ? `images/${props.champion.image.group}/${props.champion.image.full}` : NoChampion
})

// Inject patch and hotfix from the parent simulation view
const injectPatchContext = inject('patchContext', null)

watch(injectPatchContext, (ctx) => {
  if (ctx) {
    patch.value = ctx.patch
    hotfix.value = ctx.hotfix
    fetchChampions()
  }
}, { immediate: true })
</script>

<style scoped>
</style>
