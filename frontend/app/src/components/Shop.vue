<script setup>
import axios from "axios";
import { ref, inject, onUpdated } from "vue";


const { items, addItem } = defineProps(['items', 'addItem']);

let itemId = 0;

const URL = inject("URL") 
// const items = ref([])

/* onUpdated(() => {
  console.log(patch)
  axios.get(`${URL}item/${patch}`)
  .then((res) => {
    items.value = res.data;
  })
  .catch((error) => {
    console.error(`Error: ${error}`)
  })
}) */


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
      <li v-for="item in items" :key="item.item_id" class="w-16 h-16">
       <button type="button" @click="chooseItem(item)" class="border-2 border-black hover:border-slate-200">
        <img :src="URL + 'images/' + item.image.group + '/' + item.image.full" :alt="item.name" />
       </button>
      </li>
    </ul>
  </div>
</template>