<script setup>
import axios from "axios";
import Shop from "../../components/Shop.vue";
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";
import basicAttackImage from "@/assets/basic_attack.png"


const { params } = useRoute();

let actionId = 0;
const basicAttack = {
  id: "aa",
  name: "Basic Attack",
  img: basicAttackImage
}

const URL = inject("URL");
const id = params.id;
const champion = ref({});
const allItems = ref([])
const shop = ref(false)
const q = ref({});
const w = ref({});
const e = ref({});
const r = ref({});
const level = ref(1);
const items = ref([]);
const gold = ref(0)
const combo = ref([]);
const activeItems = ref([]);
const damage = ref(0);


onBeforeMount(() => {
  axios.get(`${URL}champion/${id}`)
    .then((res) => {
      champion.value = res.data;
      q.value = {
        id: "q",
        name: res.data.q.name,
        img: `${URL}images/${res.data.q.image.group}/${res.data.q.image.full}`
      }      
      w.value = {
        id: "w",
        name: res.data.w.name,
        img: `${URL}images/${res.data.w.image.group}/${res.data.w.image.full}`
      }      
      e.value = {
        id: "e",
        name: res.data.e.name,
        img: `${URL}images/${res.data.e.image.group}/${res.data.e.image.full}`
      }      
      r.value = {
        id: "r",
        name: res.data.r.name,
        img: `${URL}images/${res.data.r.image.group}/${res.data.r.image.full}`
      }
      axios.get(`${URL}item/${res.data.patch}`)
        .then((resp) => {
          allItems.value = resp.data;
        })
        .catch((error) => {
          console.error(`Error: ${error}`)
        })
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
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


const addItem = (item) => {
  if( items.value.length < 6) {
    items.value.push(item)
  }
}

const removeItem = (id) => {
  items.value = items.value.filter((item) => item.id !== id)
}

const calculateDamage = () => {
  axios.post(`${URL}simulation/dummy`,
  {
    champion_id: id,
    lvl: level.value,
    itmes: items.value.map(e => e.item._id),
    combo: combo.value.map(e => e.action.id)
  })
  .then((res) => {
    damage.value = res.data
  })
  .catch((error) => {
    console.error(`Error: ${error}`)
  })
}


</script>

<template>
  <div class="w-full p-8">
    <!--   STATS   -->
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
            <li v-for="item in items" :key="item.item.name" class="w-16 h-16">
              <button type="button" @click="removeItem(item.id)" class="border-2 border-slate-300">
                <img :src="URL + 'images/' + item.item.image.group + '/' + item.item.image.full" :alt="item.item.name" />
              </button>
            </li>
          </ul>
        </div>
        <div class="flex flex-col">
          <div>
            <button type="button" @click="shop = !shop" class="border-4 border-black w-16 h-16 bg-slate-200 flex justify-center hover:border-white">
              <p class="text-5xl">+</p>
            </button>
            <div v-if="shop">
              <Shop :items="allItems" :addItem="addItem"/>
            </div>
          </div>
          <p class="text-xl text-white m-4">{{ gold }} Gold</p>
        </div>
      </div>
    </div>
    <!--   ACTIONS   -->
    <div>
      <div class="m-2 flex flex-row flex-wrap">
        <div class="border-4 border-black m-2 flex">
          <button type="button" @click="addAction(basicAttack)" class="border-2 border-black w-16 h-16 hover:border-white">
            <img :src="basicAttack.img" :alt="basicAttack.name" />
          </button>
        </div>
        <div class="inline-flex flex-row flex-wrap border-4 border-black m-2">
          <button type="button" @click="addAction(q)"
          :disabled="!q.ready_to_use"
          :class="{ 'opacity-50 cursor-not-allowed': !q.ready_to_use }"
          class="border-2 border-black w-16 h-16 hover:border-white">
            <img :src="q.img" :alt="q.name" />
          </button>
          <button type="button" @click="addAction(w)"
          :disabled="!w.ready_to_use"
          :class="{ 'opacity-50 cursor-not-allowed': !w.ready_to_use }"
          class="border-2 border-black w-16 h-16 hover:border-white">
            <img :src="w.img" :alt="w.name" />
          </button>
          <button type="button" @click="addAction(e)"
          :disabled="!e.ready_to_use"
          :class="{ 'opacity-50 cursor-not-allowed': !e.ready_to_use }"
          class="border-2 border-black w-16 h-16 hover:border-white">
            <img :src="e.img" :alt="e.name" />
          </button>
          <button type="button" @click="addAction(r)"
          :disabled="!r.ready_to_use"
          :class="{ 'opacity-50 cursor-not-allowed': !r.ready_to_use }"
          class="border-2 border-black w-16 h-16 hover:border-white">
            <img :src="r.img" :alt="r.name" />
          </button>
        </div>
        <div class="inline-flex flex-row flex-wrap border-4 border-black m-2">
        </div>
      </div>
      <div class="border-4 border-black m-2">
        <ul class="flex flex-row flex-wrap h-16">
          <li v-for="action in combo" :key="action.id" class="w-16 h-16">
            <button type="button" @click="removeAction(action.id)" class="border-2 border-black hover:border-white">
              <img :src="action.action.img" :alt="action.action.name" />
            </button>
          </li>
        </ul>
      </div>
    </div>
    <!--   CALCULATIONS   -->
    <div>
      <button type="button" @click="calculateDamage()" class="border-4 border-black w-48 h-16 bg-slate-200 flex justify-center hover:border-white">
        <p class="text-5xl">Attack</p>
      </button>
      <p class="text-4xl">{{ damage }}</p>
  </div>
</div></template>