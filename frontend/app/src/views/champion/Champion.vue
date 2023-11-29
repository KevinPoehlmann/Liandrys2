<script setup>
import axios from "axios";
import { ref, inject, onBeforeMount } from "vue";
import { useRoute } from "vue-router";


const {params} = useRoute();

let actionId = 0;

const URL = inject("URL");
const id = params.id;
const champion = ref({});
const actions = ref([]);


onBeforeMount(() => {
  axios.get(`${URL}champion/${id}`)
    .then((res) => {
      champion.value = res.data;
      spells = {
        "q": champion
      }
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
      patch.value = "Error"
    })
})


const addAction = (action) => {
  actions.value.push({
    "id": actionId,
    "action": action
  })
  actionId++;
}

</script>

<template>
  <div class="w-full p-8">
    <img :src="URL + 'images/' + champion.image.group + '/' + champion.image.full" :alt="champion.name"/>
    <h2 class="text-bold text-white text-4xl">{{ champion.name }}</h2>
    <div class="flex border-4 border-black">
      <div>
        <button type="button">
          <img :src="URL + 'images/' + champion.q.image.group + '/' + champion.q.image.full" :alt="champion.q.name"/>
        </button>
      </div>
      <div>
        <button type="button">
          <img :src="URL + 'images/' + champion.w.image.group + '/' + champion.w.image.full" :alt="champion.w.name"/>
        </button>
      </div>
      <div>
        <button type="button">
          <img :src="URL + 'images/' + champion.e.image.group + '/' + champion.e.image.full" :alt="champion.e.name"/>
        </button>
      </div>
      <div>
        <button type="button">
          <img :src="URL + 'images/' + champion.r.image.group + '/' + champion.r.image.full" :alt="champion.r.name"/>
        </button>
      </div>
      <div>
        <img :src="URL + 'images/' + champion.passive.image.group + '/' + champion.passive.image.full" :alt="champion.passive.name"/>
      </div>
    </div>
    <div class="flex border-4 border-black">
      <ul class="flex flex-row flex-wrap">
        <li v-for="action in actions" :key="action.id">
          <button type="button">
            <img :src="URL + 'images/' + action.image.group + '/' + action.image.full" :alt="action.name"/>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>