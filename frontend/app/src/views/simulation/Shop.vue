<script setup>
import { ref, inject, computed } from "vue";


const { items, addItem, role } = defineProps(['items', 'addItem', 'role']);
const URL = inject("URL") 

let itemId = 0;


const itemInfo = ref("")
const shop = ref(false)
const searchQuery = ref('');



const filteredItems = computed(() => {
  return items.filter(item =>
    item.name.toLowerCase().includes(searchQuery.value.toLowerCase())
  );
});



const chooseItem = (item) => {
  addItem({
    "id": itemId,
    "item": item
  }, role)
  itemId++;
}

</script>


<template>
  <div>
    <button type="button" @click="shop = !shop" class="border-4 border-black rounded-lg w-16 h-16 bg-slate-200 flex justify-center hover:border-white">
      <p class="text-5xl">+</p>
    </button>
    <div v-if="shop" @click="shop = !shop" class="fixed inset-0 flex items-center justify-center">
      <div class="fixed inset-0 bg-black opacity-50"></div>
        <div class="bg-gray-800 rounded p-8 shadow-lg w-1/2 z-10" @click.stop>
          <div class="flex items-center justify-between mb-2 mx-4">
            <h2 class="text-xl text-gray-200 font-semibold mb-4">Shop:</h2>
            <input
              v-model="searchQuery" type="text" placeholder="Search..."
              class=" w-96 ml-4 p-2 border border-gray-300 rounded text-gray-800 focus:outline-none focus:border-blue-500"
            >
          </div>
          <div class="">
            <ul class="flex flex-row flex-wrap h-96 overflow-y-auto border border-white rounded">
              <li v-for="item in filteredItems" :key="item.item_id" class="w-16 h-16 relative group" @mouseover="itemInfo = item.item_id" @mouseout="itemInfo = '0'">
                <button type="button" @click="chooseItem(item)" class="border-2 border-black rounded-sm hover:border-slate-200 hover:opacity-60">
                  <img :src="URL + 'images/' + item.image.group + '/' + item.image.full" :alt="item.name" />
                </button>
                <div v-if="itemInfo === item.item_id" class="absolute top-full left-0 bg-white border border-gray-300 rounded p-1 h-8 shadow-md z-20 whitespace-nowrap">
                  {{ item.name }}
                </div>
              </li>
            </ul>
          </div>
        <button @click="shop = !shop" class="mt-4 px-4 py-2 bg-blue-500 text-white rounded">
          Close
        </button>
      </div>
    </div>
  </div>
</template>