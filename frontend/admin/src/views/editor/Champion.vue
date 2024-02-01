<script setup>
import axios from "axios";
import { ref, inject, onBeforeMount, computed, watch } from "vue";
import { useRoute } from "vue-router";
import Edited from "./Edited.vue";
import Statfield from "./Statfield.vue";
import ChampionPassive from "./ChampionPassive.vue";
import ChampionAbility from "./ChampionAbility.vue";

const { params } = useRoute();
const URL = inject("URL");
const champion = ref({});
const unchanged = ref({})
const changed = ref(false)
const rangeTypes = ref([]);
const resourceTypes = ref([]);
const mod = ref(false)


onBeforeMount(() => {
  axios.get(`${URL}champion/${params.id}`)
  .then((res) => {
    champion.value = res.data;
    unchanged.value = deepCopy(res.data);
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
  axios.get(`${URL}champion/rangetype/`)
  .then((res) => {
    rangeTypes.value = res.data;
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
  axios.get(`${URL}champion/resourcetype/`)
  .then((res) => {
    resourceTypes.value = res.data;
  })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
})

function deepCopy(obj) {
  if (typeof obj !== 'object' || obj === null) {
    return obj;
  }

  const result = Array.isArray(obj) ? [] : {};

  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      result[key] = deepCopy(obj[key]);
    }
  }

  return result;
}


watch(champion, (newChampion) => {
  // Deep comparison of nested properties
  changed.value = !isEqual(newChampion, unchanged.value);
}, { deep: true })


function isEqual(obj1, obj2) {
  if (typeof obj1 === 'object' || typeof obj2 === 'object') {
    for (const key in obj1) {
      if (!isEqual(obj1[key], obj2[key])) {
        return false;
      }
    }
    for (const key in obj2) {
      if (!(key in obj1)) {
        return false;
      }
    }
    return true
  }
  if (obj1 != obj2) {
    return false;
  }
  return true;
}

const getChanges = () => {
  const changedFields = Object.entries(champion.value).filter(([key, value]) => {
    const oldVal = unchanged.value[key]
    return value !== oldVal
  }).map(([key, value]) => ({ key, value, oldValue: unchanged.value[key] }));
  return changedFields
}


const saveChanges = () => {
  mod.value = !mod.value
  axios.put(`${URL}champion`, champion.value)
  .then((res) => {
      unchanged.value = {...champion.value}
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
}

const cancelChanges = () => {
  mod.value = !mod.value
}

const updateValue = (field, value) => {
  champion.value[field] = value;
};


</script>


<template>
  <div class="p-8">
    <div class="flex items-center mb-8">
      <!-- Image -->
      <img
        v-if="champion.image && champion.image.full"
        :src="URL + 'images/' + champion.image.group + '/' + champion.image.full"
        :alt="champion.name"
        class="w-32 h-32 object-cover rounded mr-4"
      />
      <!-- Item Details -->
      <div>
        <p class="text-gray-200 mb-1">DB:  {{ champion._id }}</p>
        <h2 class="text-gray-200 text-2xl font-bold mb-2">{{ champion.name }}</h2>
        <p class="text-gray-200 mb-1">ID:  {{ champion.champion_id }}</p>
        <p class="text-gray-200 mb-1">Key:  {{ champion.key }}</p>
      </div>
    </div>
    <!-- Stat Fields -->
    <div class="flex flex-wrap gap-6 mb-6">
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Other Stats</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <div class="flex flex-col">
            <label for="rangeType" class="text-gray-200 w-40 mb-1">Range Type:</label>
            <select v-model="champion.range_type" class="form-select">
              <option v-for="ty in rangeTypes" :key="ty" :value="ty">{{ ty }}</option>
            </select>
          </div>
          <div class="flex flex-col">
            <label for="resourceType" class="text-gray-200 w-40 mb-1">Resource Type:</label>
            <select v-model="champion.resource_type" class="form-select">
              <option v-for="ty in resourceTypes" :key="ty" :value="ty">{{ ty }}</option>
            </select>
          </div>
          <Statfield label="Movementspeed" :value="champion.movementspeed" @update="updateValue('movementspeed', $event)" /> 
          <Statfield label="Attackrange" :value="champion.attackrange" @update="updateValue('attackrange', $event)" /> 
        </div>
      </div>
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Hitspoints</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Statfield label="HP" :value="champion.hp" @update="updateValue('hp', $event)" /> 
          <Statfield label="HP per Level" :value="champion.hp_per_lvl" @update="updateValue('hp_per_lvl', $event)" /> 
          <Statfield label="HP Regen" :value="champion.hp_regen" @update="updateValue('hp_regen', $event)" /> 
          <Statfield label="HP Regen per Level" :value="champion.hp_regen_per_lvl" @update="updateValue('hp_regen_per_lvl', $event)" /> 
        </div>
      </div>
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Mana</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Statfield label="Mana" :value="champion.mana" @update="updateValue('mana', $event)" /> 
          <Statfield label="Mana per Level" :value="champion.mana_per_lvl" @update="updateValue('mana_per_lvl', $event)" /> 
          <Statfield label="Mana Regen" :value="champion.mana_regen" @update="updateValue('mana_regen', $event)" /> 
          <Statfield label="Mana Regen per Level" :value="champion.mana_regen_per_lvl" @update="updateValue('mana_regen_per_lvl', $event)" />
        </div>
      </div>
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Attacks</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Statfield label="AD" :value="champion.ad" @update="updateValue('ad', $event)" /> 
          <Statfield label="AD per Level" :value="champion.ad_per_lvl" @update="updateValue('ad_per_lvl', $event)" /> 
          <Statfield label="Attackspeed" :value="champion.attackspeed" @update="updateValue('attackspeed', $event)" /> 
          <Statfield label="Attackspeed per Level" :value="champion.attackspeed_per_lvl" @update="updateValue('attackspeed_per_lvl', $event)" /> 
          <Statfield label="Attackspeed Ratio" :value="champion.attackspeed_ratio" @update="updateValue('attackspeed_ratio', $event)" /> 
          <Statfield label="Attack Windup" :value="champion.attack_windup" @update="updateValue('attack_windup', $event)" /> 
          <Statfield label="Windup Modifier" :value="champion.manwindup_modifier" @update="updateValue('manwindup_modifier', $event)" /> 
          <Statfield label="Missile Speed" :value="champion.missile_speed" @update="updateValue('missile_speed', $event)" /> 
        </div>
      </div>
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Resistances</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Statfield label="Armor" :value="champion.armor" @update="updateValue('armor', $event)" /> 
          <Statfield label="Armor per Level" :value="champion.armor_per_lvl" @update="updateValue('armor_per_lvl', $event)" /> 
          <Statfield label="MR" :value="champion.mr" @update="updateValue('mr', $event)" /> 
          <Statfield label="MR per Level" :value="champion.mr_per_lvl" @update="updateValue('mr_per_lvl', $event)" /> 
        </div>
      </div>
      <!-- Add more fields as needed -->
    </div>
    <ChampionPassive v-if="champion.passive" :passive="champion.passive" @update="updateValue('passive', $event)"/>
    <ChampionAbility v-if="champion.q" :ability="champion.q" @update="updateValue('q', $event)"/>
    <ChampionAbility v-if="champion.w" :ability="champion.w" @update="updateValue('w', $event)"/>
    <ChampionAbility v-if="champion.e" :ability="champion.e" @update="updateValue('e', $event)"/>
    <ChampionAbility v-if="champion.r" :ability="champion.r" @update="updateValue('r', $event)"/>
      <!-- Switch for ready_to_use -->
    <div
      :class="{'bg-green-500': champion.ready_to_use, 'bg-red-400': !champion.ready_to_use}"
      class="mb-6 border border-white rounded-md w-40 p-2"
    >
      <label for="readyToUse" class="flex items-center cursor-pointer">
        <span class="mr-2">Ready to Use:</span>
        <input
        type="checkbox"
        id="readyToUse"
        v-model="champion.ready_to_use"
          class="form-checkbox h-5 w-5"
        />
      </label>
    </div>
    <!-- Save Changes Button -->
    <Edited :champion="champion.value" :unchanged="unchanged.value" :pushChanges="saveChanges"/>
    <button
      @click="mod = !mod"
      :disabled="!changed"
      :class="{ 'opacity-50 cursor-not-allowed': !changed }"
      class="bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600"
    >
      Save Changes
    </button>
    <Edited :mod="mod" :changes="getChanges()" :pushChanges="saveChanges" :closeModal="cancelChanges"/>
  </div>
</template>