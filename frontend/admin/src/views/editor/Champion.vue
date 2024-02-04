<script setup>
import axios from "axios";
import { getChanges, isEqual, deepCopy, updateValue } from "./helper.js"
import { ref, inject, onBeforeMount, watch } from "vue";
import { useRoute } from "vue-router";
import Edited from "./Edited.vue";
import Statfield from "./Editfields/Statfield.vue";
import Selectionfield from "./Editfields/Selectionfield.vue";
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



watch(champion, (newChampion) => {
  changed.value = !isEqual(newChampion, unchanged.value);
}, { deep: true })



const saveChanges = () => {
  mod.value = !mod.value
  axios.put(`${URL}champion`, champion.value)
  .then((res) => {
      unchanged.value = deepCopy(champion.value)
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
    })
}

const cancelChanges = () => {
  mod.value = !mod.value
}


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
        <p class="text-gray-200 font-semibold mb-1">DB:  {{ champion._id }}</p>
        <h2 class="text-gray-200 text-2xl font-bold mb-2">{{ champion.name }}</h2>
        <p class="text-gray-200 font-semibold mb-1">ID:  {{ champion.champion_id }}</p>
        <p class="text-gray-200 font-semibold mb-1">Key:  {{ champion.key }}</p>
      </div>
    </div>
    <!-- Stat Fields -->
    <h2 class="text-gray-200 text-xl font-semibold mb-3 ml-12">Base Stats</h2>
    <div class="border border-white rounded-md p-4 mb-6 flex flex-wrap gap-6">
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Other Stats</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Selectionfield label="Range Type" :value="champion.range_type" :options="rangeTypes" @update="updateValue(champion, 'range_type', $event)" /> 
          <Selectionfield label="Resource Type" :value="champion.resource_type" :options="resourceTypes" @update="updateValue(champion, 'resource_type', $event)" /> 
          <Statfield label="Movementspeed" :value="champion.movementspeed" @update="updateValue(champion, 'movementspeed', $event)" /> 
          <Statfield label="Attackrange" :value="champion.attackrange" @update="updateValue(champion, 'attackrange', $event)" /> 
        </div>
      </div>
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Hitspoints</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Statfield label="HP" :value="champion.hp" @update="updateValue(champion, 'hp', $event)" /> 
          <Statfield label="HP per Level" :value="champion.hp_per_lvl" @update="updateValue(champion, 'hp_per_lvl', $event)" /> 
          <Statfield label="HP Regen" :value="champion.hp_regen" @update="updateValue(champion, 'hp_regen', $event)" /> 
          <Statfield label="HP Regen per Level" :value="champion.hp_regen_per_lvl" @update="updateValue(champion, 'hp_regen_per_lvl', $event)" /> 
        </div>
      </div>
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Mana</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Statfield label="Mana" :value="champion.mana" @update="updateValue(champion, 'mana', $event)" /> 
          <Statfield label="Mana per Level" :value="champion.mana_per_lvl" @update="updateValue(champion, 'mana_per_lvl', $event)" /> 
          <Statfield label="Mana Regen" :value="champion.mana_regen" @update="updateValue(champion, 'mana_regen', $event)" /> 
          <Statfield label="Mana Regen per Level" :value="champion.mana_regen_per_lvl" @update="updateValue(champion, 'mana_regen_per_lvl', $event)" />
        </div>
      </div>
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Attacks</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Statfield label="AD" :value="champion.ad" @update="updateValue(champion, 'ad', $event)" /> 
          <Statfield label="AD per Level" :value="champion.ad_per_lvl" @update="updateValue(champion, 'ad_per_lvl', $event)" /> 
          <Statfield label="Attackspeed" :value="champion.attackspeed" @update="updateValue(champion, 'attackspeed', $event)" /> 
          <Statfield label="Attackspeed per Level" :value="champion.attackspeed_per_lvl" @update="updateValue(champion, 'attackspeed_per_lvl', $event)" /> 
          <Statfield label="Attackspeed Ratio" :value="champion.attackspeed_ratio" @update="updateValue(champion, 'attackspeed_ratio', $event)" /> 
          <Statfield label="Attack Windup" :value="champion.attack_windup" @update="updateValue(champion, 'attack_windup', $event)" /> 
          <Statfield label="Windup Modifier" :value="champion.manwindup_modifier" @update="updateValue(champion, 'manwindup_modifier', $event)" /> 
          <Statfield label="Missile Speed" :value="champion.missile_speed" @update="updateValue(champion, 'missile_speed', $event)" /> 
        </div>
      </div>
      <div>
        <h3 class="text-gray-200 text-lg font-semibold mb-1 ml-2">Resistances</h3>
        <div class="grid grid-cols-2 gap-8 border border-white rounded-md p-4">
          <Statfield label="Armor" :value="champion.armor" @update="updateValue(champion, 'armor', $event)" /> 
          <Statfield label="Armor per Level" :value="champion.armor_per_lvl" @update="updateValue(champion, 'armor_per_lvl', $event)" /> 
          <Statfield label="MR" :value="champion.mr" @update="updateValue(champion, 'mr', $event)" /> 
          <Statfield label="MR per Level" :value="champion.mr_per_lvl" @update="updateValue(champion, 'mr_per_lvl', $event)" /> 
        </div>
      </div>
      <!-- Add more fields as needed -->
    </div>
    <ChampionPassive v-if="champion.passive" :passive="champion.passive" @update="updateValue(champion, 'passive', $event)"/>
    <ChampionAbility v-if="champion.q" :ability="champion.q" @update="updateValue(champion, 'q', $event)"/>
    <ChampionAbility v-if="champion.w" :ability="champion.w" @update="updateValue(champion, 'w', $event)"/>
    <ChampionAbility v-if="champion.e" :ability="champion.e" @update="updateValue(champion, 'e', $event)"/>
    <ChampionAbility v-if="champion.r" :ability="champion.r" @update="updateValue(champion, 'r', $event)"/>
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
    <button
      @click="mod = !mod"
      :disabled="!changed"
      :class="{ 'opacity-50 cursor-not-allowed': !changed }"
      class="bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600"
    >
      Save Changes
    </button>
    <Edited :mod="mod" :changes="getChanges(champion, unchanged)" :pushChanges="saveChanges" :closeModal="cancelChanges"/>
  </div>
</template>