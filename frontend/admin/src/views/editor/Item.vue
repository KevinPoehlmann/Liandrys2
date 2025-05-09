<template>
  <div v-if="item" class="p-6 space-y-6">
    <h1 class="text-2xl font-bold">Item Editor</h1>

    <!-- Top Info Block -->
    <div class="flex items-center gap-4">
      <img :src="imageUrl(item?.image)" class="w-20 h-20 rounded shadow" />
      <div>
        <p><strong>Name:</strong> {{ item?.name }}</p>
        <p><strong>Item ID:</strong> {{ item?.item_id }}</p>
        <p><strong>ID:</strong> {{ item?.id }}</p>
        <p><strong>Patch:</strong> {{ item?.patch }}</p>
        <p><strong>Hotfix:</strong> {{ item?.hotfix || '—' }}</p>
      </div>
    </div>

    <!-- Basic Info (Gold, Class, Requirements) -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label class="block text-sm font-medium mb-1">Gold</label>
        <input type="number" v-model.number="item.gold" class="w-full px-2 py-1 border rounded" />
      </div>

      <div>
        <label class="block text-sm font-medium mb-1">Item Class</label>
        <select v-model="item.class_" class="w-full px-2 py-1 border rounded">
          <option v-for="cls in enums.classes" :key="cls.value" :value="cls.value">
            {{ formatEnumLabel(cls.name) }}
          </option>
        </select>
      </div>

      <div>
        <label class="block text-sm font-medium mb-1">Limitations</label>
        <input v-model="item.limitations" class="w-full px-2 py-1 border rounded" />
      </div>

      <div>
        <label class="block text-sm font-medium mb-1">Requirements</label>
        <input v-model="item.requirements" class="w-full px-2 py-1 border rounded" />
      </div>
    </div>

    <!-- Map Selection -->
    <div>
      <label class="block text-sm font-medium mb-1">Maps</label>
      <div class="flex flex-wrap gap-2">
        <label v-for="map in enums.maps" :key="map.value" class="flex items-center gap-1 text-sm">
          <input type="checkbox" :value="map.value" v-model="item.maps" />
          {{ formatEnumLabel(map.name) }}
        </label>
      </div>
    </div>

    <!-- Build Path -->
    <ItemBuild :from="item.from_" :into="item.into" />

    <!-- Stats -->
    <ItemStats :stats="item.stats" :masterwork="item.masterwork" />

    <!-- Active Ability -->
    <details v-if="item.active" open>
      <summary class="text-lg font-semibold cursor-pointer">Active</summary>
      <Ability :ability="item.active" show-type show-unique />
    </details>

    <!-- Passives -->
    <details open>
      <summary class="text-lg font-semibold cursor-pointer">Passives</summary>
      <div class="space-y-4 mt-2">
        <Passive
          v-for="(passive, i) in item.passives"
          :key="i"
          :passive="item.passives[i]"
          show-unique
        />
        <button @click="addPassive" class="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
          + Add Passive
        </button>
      </div>
    </details>

    <!-- Validation and Save -->
    <div class="flex items-center gap-4">
      <label class="inline-flex items-center gap-2">
        <input type="checkbox" v-model="item.validated" />
        <span>Validated</span>
      </label>
      <button class="bg-blue-600 text-white px-4 py-2 rounded shadow" @click="showConfirm = true">
        Save Changes
      </button>
    </div>

    <!-- Confirmation Modal -->
    <ModalConfirm
      v-if="showConfirm"
      :current="item"
      :original="originalItem"
      @confirm="saveItem"
      @cancel="showConfirm = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import ModalConfirm from './sections/ModalConfirm.vue'
import Ability from './sections/Ability.vue'
import Passive from './sections/Passive.vue'
import ItemBuild from './sections/ItemBuild.vue'
import ItemStats from './sections/ItemStats.vue'
import { formatEnumLabel } from '@/utils/formatters'

const route = useRoute()
const item = ref(null)
const originalItem = ref(null)
const showConfirm = ref(false)

const enums = ref({ classes: [], maps: [] })

onMounted(async () => {
  const { id } = route.params
  const { data: itemData } = await axios.get(`/item/${id}`)
  item.value = JSON.parse(JSON.stringify(itemData))
  originalItem.value = JSON.parse(JSON.stringify(itemData))

  const { data: enumData } = await axios.get('/enum/')
  enums.value.classes = enumData.ItemClass
  enums.value.maps = enumData.Map
})

function imageUrl(image) {
  return `/images/${image?.group}/${image?.full}`
}

async function saveItem() {
  await axios.put('/item', item.value)
  showConfirm.value = false
}

function addPassive() {
  item.value.passives.push({
    name: '',
    description: '',
    static_cooldown: '',
    effects: [],
    raw_stats: {},
    unique: false,
    changes: [],
    validated: false
  })
}
</script>
