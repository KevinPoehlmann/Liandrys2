<script setup>
import axios from "axios";

import ChampionSelection from "./ChampionSelection.vue";
import Shop from "../../components/Shop.vue";
import { ref, inject, onBeforeMount, watchEffect } from "vue";
import basicAttackImage from "@/assets/basic_attack.png"
import noChampion from "@/assets/NoChampion.png"



let actionId = 0;
const basicAttack = {
  id: "aa",
  name: "Basic Attack",
  img: basicAttackImage
}

const URL = inject("URL");
const patch = ref("")
const attacker = ref({});
const defender = ref({});
const allChampions = ref([])
const allItems = ref([])
const q = ref({});
const w = ref({});
const e = ref({});
const r = ref({});
const levelAttacker = ref(1);
const levelDefender = ref(1);
const itemsAttacker = ref([]);
const itemsDefender = ref([]);
const goldAttacker = ref(0)
const goldDefender = ref(0)
const combo = ref([]);
const activeItems = ref([]);
const damage = ref(0);




onBeforeMount(() => {
  axios.get(`${URL}patch/`)
  .then((res) => {
    patch.value = res.data.patch;
    if (patch.value) {
      console.log("Hi this is patch: " + patch.value)
      axios.get(`${URL}champion/all/${patch.value}`)
      .then((champs) => {
        allChampions.value = champs.data;
      })
      .catch((error) => {
        console.error(`Error: ${error}`)
      })
      axios.get(`${URL}item/all/${patch.value}`)
      .then((items) => {
        allItems.value = items.data;
      })
      .catch((error) => {
        console.error(`Error: ${error}`)
      })
    }
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
})


const selectAttacker = (championId) => {
  axios.get(`${URL}champion/${championId}`)
    .then((res) => {
      combo.value = []
      attacker.value = res.data;
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
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
}

const selectDefender = (championId) => {
  axios.get(`${URL}champion/${championId}`)
    .then((res) => {
      defender.value = res.data;
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
}

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

const changeLevel = (i, role) => {
  let levelRef
  if(role === "A") {
    levelRef = levelAttacker
  }
  if(role === "D") {
    levelRef = levelDefender
  }
  if (levelRef.value + i > 0 && levelRef.value + i < 19) {
    
    levelRef.value += i
  }
}


const addItem = (item, role) => {
  let itemsRef
  let goldRef
  if(role === "A") {
    itemsRef = itemsAttacker
    goldRef = goldAttacker
  }
  if(role === "D") {
    itemsRef = itemsDefender
    goldRef = goldDefender
  }
  if( itemsRef.value.length < 6) {
    axios.post(`${URL}simulation/item`,
    {
      items: itemsRef.value.map(e => e.item._id),
      new_item: item.item._id
    })
    .then((res) => {
      if( res.data) {
        itemsRef.value.push(item)
        goldRef.value += item.item.gold
      }
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
  }
}

const removeItem = (id, role) => {
  if(role === "A") {
    goldAttacker.value -= itemsAttacker.value.filter((item) => item.id === id)[0].item.gold
    itemsAttacker.value = itemsAttacker.value.filter((item) => item.id !== id)
  }
  if(role === "D") {
    goldDefender.value -= itemsDefender.value.filter((item) => item.id === id)[0].item.gold
    itemsDefender.value = itemsDefender.value.filter((item) => item.id !== id)
  }
}


watchEffect(() => {
  if(attacker.value._id && defender.value._id) {
    axios.post(`${URL}simulation/v1`,
    {
      id_attacker: attacker.value._id,
      lvl_attacker: levelAttacker.value,
      items_attacker: itemsAttacker.value.map(e => e.item._id),
      id_defender: defender.value._id,
      lvl_defender: levelDefender.value,
      items_defender: itemsDefender.value.map(e => e.item._id),
      combo: combo.value.map(e => e.action.id)
    })
    .then((res) => {
      damage.value = res.data
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
  }
})


</script>

<template>
  <div class="">
    <!--   STATS   -->
    <div class="flex justify-between">
      <div class="flex">
        <ChampionSelection :imgSrc="attacker.image ? URL + 'images/' + attacker.image.group + '/' + attacker.image.full : noChampion"
        :champions="allChampions" :selectChampion="selectAttacker"/>
        <div class="mx-4">
          <h2 class="text-bold text-white text-4xl">{{ attacker.name ? attacker.name : "Select Champion" }}</h2>
          <p class="text-white">Level:</p>
          <div class="inline-flex bg-white">
            <button type="button" @click="changeLevel(-1, 'A')"
              class="border-x-2 border-black w-6 active:bg-slate-200">-</button>
            <p class="w-8 text-center">{{ levelAttacker }}</p>
            <button type="button" @click="changeLevel(1, 'A')"
              class=" border-x-2 border-black w-6 active:bg-slate-200">+</button>
          </div>
        </div>
        <div class="flex">
          <div class="border-4 border-black inline-block">
            <ul class="flex flex-row flex-wrap w-48 h-32">
              <li v-for="item in itemsAttacker" :key="item.item.name" class="w-16 h-16">
                <button type="button" @click="removeItem(item.id, 'A')" class="border-2 border-black hover:border-white">
                  <img :src="URL + 'images/' + item.item.image.group + '/' + item.item.image.full" :alt="item.item.name" />
                </button>
              </li>
            </ul>
          </div>
          <div class="flex flex-col">
            <Shop :items="allItems" :addItem="addItem" role="A"/>
            <p class="text-xl text-white m-4">{{ goldAttacker }} Gold</p>
          </div>
        </div>
      </div>
      <div class="flex">
        <div class="flex">
          <div class="flex flex-col">
            <Shop :items="allItems" :addItem="addItem" role="D"/>
            <p class="text-xl text-white m-4">{{ goldDefender }} Gold</p>
          </div>
          <div class="border-4 border-black inline-block">
            <ul class="flex flex-row flex-wrap w-48 h-32">
              <li v-for="item in itemsDefender" :key="item.item.name" class="w-16 h-16">
                <button type="button" @click="removeItem(item.id, 'D')" class="border-2 border-black hover:border-white">
                  <img :src="URL + 'images/' + item.item.image.group + '/' + item.item.image.full" :alt="item.item.name" />
                </button>
              </li>
            </ul>
          </div>
        </div>
        <div class="mx-4">
          <h2 class="text-bold text-white text-4xl">{{ defender.name ? defender.name : "Select Champion" }}</h2>
          <p class="text-white">Level:</p>
          <div class="inline-flex bg-white">
            <button type="button" @click="changeLevel(-1, 'D')"
              class="border-x-2 border-black w-6 active:bg-slate-200">-</button>
            <p class="w-8 text-center">{{ levelDefender }}</p>
            <button type="button" @click="changeLevel(1, 'D')"
              class=" border-x-2 border-black w-6 active:bg-slate-200">+</button>
          </div>
        </div>
        <ChampionSelection :imgSrc="defender.image ? URL + 'images/' + defender.image.group + '/' + defender.image.full : noChampion"
        :champions="allChampions" :selectChampion="selectDefender"/>
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
      <p class="text-4xl">{{ damage }} Damage</p>
  </div>
</div></template>