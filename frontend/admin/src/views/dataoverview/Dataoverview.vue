<template>
  <div class="p-6 space-y-4">
    <h1 class="text-2xl font-bold">Data Overview</h1>

    <!-- Patch Selector -->
    <div class="flex items-center gap-4">
      <label for="patchSelect" class="font-semibold">Patch:</label>
      <select
        id="patchSelect"
        v-model="selectedPatchKey"
        @change="fetchAllData"
        class="border rounded px-2 py-1"
      >
        <option
          v-for="(patch, i) in patches"
          :key="i"
          :value="patchKey(patch)"
        >
          {{ patchLabel(patch) }}
        </option>
      </select>

      <label for="mapSelect" class="font-semibold">Map:</label>
      <select
        id="mapSelect"
        v-model="selectedMapKey"
        class="border rounded px-2 py-1"
      >
        <option
          v-for="(map, i) in maps"
          :key="i"
          :value="map"
        >
          {{ map }}
        </option>
      </select>
      

      <label class="ml-4 inline-flex items-center space-x-2">
        <input type="checkbox" v-model="onlyShowInvalid" />
        <span>Only show unvalidated</span>
      </label>
    </div>

    <!-- 4-Column Layout for Data Sections -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      <div v-for="(group, key) in groupedData" :key="key">
        <h2 class="text-xl font-semibold mb-2 capitalize">{{ key }}</h2>
        <div class="flex flex-col gap-2 max-h-96 overflow-y-auto">
          <div
            v-for="item in filtered(group)"
            :key="item._id"
            @click="navigateToEditor(key, item._id)"
            :class="[
              'flex items-center p-2 rounded text-white shadow cursor-pointer transition hover:opacity-80',
              item.validated ? 'bg-green-600' : 'bg-red-600'
            ]"
          >
            <img
              :src="imageUrl(item.image)"
              alt="item.name"
              class="w-10 h-10 object-contain mr-3"
            />
            <span class="font-semibold text-sm">{{ item.name }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

const patches = ref([])
const maps = ref([])
const selectedPatchKey = ref("")
const selectedMapKey = ref("")
const onlyShowInvalid = ref(false)

const champions = ref([])
const items = ref([])
const runes = ref([])
const summoners = ref([])

const groupedData = computed(() => ({
  champions: champions.value,
  items: items.value,
  runes: runes.value,
  summonerspells: summoners.value,
}))

const typeRouteMap = {
  champions: 'champion',
  items: 'item',
  runes: 'rune',
  summonerspells: 'summonerspell',
}

function navigateToEditor(type, id) {
  const route = typeRouteMap[type]
  router.push({ name: route, params: { id } })
}

onMounted(async () => {
  const { data } = await axios.get("/patch/all")
  patches.value = data
  if (patches.value.length > 0) {
    selectedPatchKey.value = patchKey(patches.value[0])
    await fetchAllData()
  }
  const  enumRes  = await axios.get("/enum/")
  maps.value = enumRes.data.Map.map(map => map.value);
  selectedMapKey.value = maps.value[0]
})

function patchKey(patch) {
  return `${patch.patch}_${patch.hotfix}`
}

function patchLabel(patch) {
  return patch.hotfix ? `${patch.patch} (Hotfix ${new Date(patch.hotfix).toLocaleString()})` : patch.patch
}

function parseSelected() {
  const [patch, hotfix] = selectedPatchKey.value.split("_")
  return { patch, hotfix: hotfix === "null" ? null : hotfix }
}

function imageUrl(image) {
  return `/images/${image.group}/${image.full}`
}

function filtered(list) {
  return list.filter(obj => {
    const invalidFilter = !this.onlyShowInvalid || !obj.validated
    const mapFilter = !this.selectedMapKey || (obj.maps && obj.maps.includes(this.selectedMapKey)) || !obj.maps
    return invalidFilter && mapFilter
  })
}

async function fetchAllData() {
  const { patch, hotfix } = parseSelected()

  const fetch = async (type, target) => {
    const url = hotfix
      ? `/${type}/all/${patch}?hotfix=${hotfix}`
      : `/${type}/all/${patch}`

    const res = await axios.get(url)
    target.value = res.data
  }

  await Promise.all([
    fetch("champion", champions),
    fetch("item", items),
    fetch("rune", runes),
    fetch("summonerspell", summoners),
  ])
}
</script>
  