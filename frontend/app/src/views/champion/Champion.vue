<script setup>
import axios from "axios";
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";


const { params } = useRoute();

let actionId = 0;
const basicAttack = {
  name: "Basic Attack"
}

const URL = inject("URL");
const id = params.id;
const champion = ref({});
const level = ref(1);
const items = ref([]);
const combo = ref([]);
const butts = ref([]);


onBeforeMount(() => {
  axios.get(`${URL}champion/${id}`)
    .then((res) => {
      champion.value = res.data;
      butts.value = [res.data.q, res.data.w, res.data.e, res.data.r]
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
      patch.value = "Error"
    })
})


const addAction = (action) => {
  combo.value.push({
    "id": actionId,
    "action": action
  })
  actionId++;
}

const removeAction = (id) => {
  combo.value = combo.value.filter((act) => act.id !== id)
}

const changeLevel = (i) => {
  if (level.value + i > 0 && level.value + i < 19) {
    level.value += i
  }
}

</script>

<template>
  <div class="w-full p-8">
    <div class="flex">
      <img :src="URL + 'images/' + champion.image.group + '/' + champion.image.full" :alt="champion.name" class="w-32 h-32" />
      <div class="mx-4">
        <h2 class="text-bold text-white text-4xl">{{ champion.name }}</h2>
        <p class="text-white">Level:</p>
        <div class="inline-flex bg-white">
          <button type="button" @click="changeLevel(-1)"
            class="border-x-2 border-black w-6 active:bg-slate-200">-</button>
          <p class="w-8 text-center">{{ level }}</p>
          <button type="button" @click="changeLevel(1)"
            class=" border-x-2 border-black w-6 active:bg-slate-200">+</button>
        </div>
      </div>
      <div class="flex">
        <div class="border-4 border-black inline-block">
          <ul class="flex flex-row flex-wrap w-48 h-32">
            <li v-for="item in items" :key="item.name" class="w-16 h-16">
              <button type="button" @click="" class="border-2 border-slate-300">
                <img :src="URL + 'images/' + item.image.group + '/' + item.image.full" :alt="item.name" />
              </button>
            </li>
          </ul>
        </div>
        <button type="button" class="border-4 border-black w-16 h-16 bg-slate-200 flex justify-center hover:border-white">
          <p class="text-5xl">+</p>
        </button>
      </div>
    </div>
    <div>
      <div class="border-4 border-black m-2 inline-block">
        <ul class="flex flex-row flex-wrap w-96">
          <li class="w-16 h-16">
            <button type="button" @click="addAction(basicAttack)" class="border-2 border-black hover:border-white">
              <img src="@/assets/basic_attack.png" alt="Basic Attack" />
            </button>
          </li>
          <li v-for="butt in butts" :key="butt.name" class="w-16 h-16">
            <button type="button" @click="addAction(butt)" class="border-2 border-black hover:border-white">
              <img :src="URL + 'images/' + butt.image.group + '/' + butt.image.full" :alt="butt.name" />
            </button>
          </li>
        </ul>
      </div>
      <div class="border-4 border-black m-2">
        <ul class="flex flex-row flex-wrap h-16">
          <li v-for="action in combo" :key="action.id" class="w-16 h-16">
            <button type="button" @click="removeAction(action.id)" class="border-2 border-black hover:border-white">
              <img v-if="action.action.name !== 'Basic Attack'"
                :src="URL + 'images/' + action.action.image.group + '/' + action.action.image.full"
                :alt="action.action.name" />
              <img v-else src="@/assets/basic_attack.png" alt="Basic Attack" />
            </button>
          </li>
        </ul>
      </div>
    </div>
    <div>
      <button type="button" class="border-4 border-black w-48 h-16 bg-slate-200 flex justify-center hover:border-white">
        <p class="text-5xl">Attack</p>
      </button>
  </div>
</div></template>