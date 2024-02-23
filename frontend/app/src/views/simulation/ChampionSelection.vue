<script setup>
import { ref, inject, computed } from "vue";


const { imgSrc, champions, selectChampion } = defineProps(['imgSrc', 'champions', 'selectChampion']);
const URL = inject("URL") 


const championInfo = ref("")
const champSelect = ref(false)
const searchQuery = ref('');

const filteredChampions = computed(() => {
  return champions.filter(champion =>
    champion.name.toLowerCase().includes(searchQuery.value.toLowerCase())
  );
});


const chooseChampion = (championId) => {
  selectChampion(championId)
  champSelect.value = false
}


</script>


<template>
  <div>
    <button type="button" @click="champSelect = !champSelect" class="border-4 border-black hover:border-white rounded-md">
      <img :src="imgSrc" alt="Champion" class="w-32 h-32" />
    </button>
    <div v-if="champSelect" @click="champSelect = !champSelect" class="fixed inset-0 flex items-center justify-center">
      <div class="fixed inset-0 bg-black opacity-50"></div>
        <div class="bg-gray-800 rounded p-8 shadow-lg w-1/2 h-3/5 z-10" @click.stop>
          <div class="flex items-center justify-between mb-2 mx-4">
            <h2 class="text-xl text-gray-200 font-semibold mb-4">Champion Selection:</h2>
            <input
              v-model="searchQuery" type="text" placeholder="Search..."
              class=" w-96 ml-4 p-2 border border-gray-300 rounded text-gray-800 focus:outline-none focus:border-blue-500"
            >
          </div>
          <div class="border-4 border-white rounded">
            <ul class="flex flex-row flex-wrap overflow-y-auto overflow-x-clip h-96">
              <li v-for="champion in filteredChampions" :key="champion.champion_id" class="w-16 h-16 relative group" @mouseover="championInfo = champion.champion_id" @mouseout="itemInfo = '0'">
                <button type="button" @click="chooseChampion(champion._id)" class="border-2 border-black rounded-sm hover:border-slate-200 hover:opacity-60">
                  <img :src="URL + 'images/' + champion.image.group + '/' + champion.image.full" :alt="champion.name" />
                </button>
                <div v-if="championInfo === champion.champion_id" class="absolute top-full left-0 bg-gray-200 border border-gray-300 rounded p-1 h-8 shadow-md z-20 whitespace-nowrap">
                  {{ champion.name }}
                </div>
              </li>
            </ul>
          </div>
        <button @click="champSelect = !champSelect" class="mt-4 px-4 py-2 bg-blue-500 text-white rounded">
          Close
        </button>
      </div>
    </div>
  </div>
</template>