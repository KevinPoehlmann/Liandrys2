<script setup>
import axios from "axios";
import { ref, inject } from "vue";


const { imgSrc, champions, selectChampion } = defineProps(['imgSrc', 'champions', 'selectChampion']);
const URL = inject("URL") 


const championInfo = ref("")
const champSelect = ref(false)


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
        <div class="bg-white rounded p-8 shadow-lg w-1/2 h-3/5 z-10" @click.stop>
          <h2 class="text-xl font-semibold mb-4">Champion Selection</h2>
          <div class="border-4 border-black rounded">
            <ul class="flex flex-row flex-wrap overflow-y-auto h-96">
              <li v-for="champion in champions" :key="champion.champion_id" class="w-16 h-16 relative group" @mouseover="championInfo = champion.champion_id" @mouseout="itemInfo = '0'">
                <button type="button" @click="chooseChampion(champion._id)" class="border-2 border-black hover:border-slate-200">
                  <img :src="URL + 'images/' + champion.image.group + '/' + champion.image.full" :alt="champion.name" />
                </button>
                <div v-if="championInfo === champion.champion_id" class="absolute top-full left-0 bg-white border border-gray-300 p-1 h-8 shadow-md z-20 whitespace-nowrap">
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