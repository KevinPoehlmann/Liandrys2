<script setup>
import axios from "axios";
import { ref, inject } from "vue";


const { champions, selectChampion } = defineProps(['champions', 'selectChampions']);
const URL = inject("URL") 

let itemId = 0;


const itemInfo = ref("")

const chooseItem = (item) => {
  addItem({
    "id": itemId,
    "item": item
  })
  itemId++;
}

</script>


<template>
  <div class="border-4 border-black">
    <ul class="flex flex-row flex-wrap w-96 h-96 overflow-y-auto">
      <li v-for="item in items" :key="item.item_id" class="w-16 h-16 relative group" @mouseover="itemInfo = item.item_id" @mouseout="itemInfo = '0'">
        <button type="button" @click="chooseItem(item)" class="border-2 border-black hover:border-slate-200">
          <img :src="URL + 'images/' + item.image.group + '/' + item.image.full" :alt="item.name" />
        </button>
        <div v-if="itemInfo === item.item_id" class="absolute top-full left-0 bg-white border border-gray-300 p-1 h-8 shadow-md z-20 whitespace-nowrap">
          {{ item.name }}
        </div>
      </li>
    </ul>
  </div>
</template>