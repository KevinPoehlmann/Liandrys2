<script setup>
import axios from 'axios'
import { ref, onBeforeMount } from 'vue'

defineProps({
  header: String,
})
const URL = "http://127.0.0.1:5001/";  //add patch/  to URL

const status = ref("");
const patch = ref("4.20");
const todos = ref([]);


const get_status = () => {
  axios.get(`${URL}patch/status/`)
    .then((res) => {
      status.value = res.data.msg;
      console.log(res.data.todo)
      todos.value = res.data.todo;
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
      status.value = "Error"
    })
}

const update = () => {
  axios.post(`${URL}patch/`)
    .then((res) => {
      status.value = res.data.msg;
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
      status.value = "Error"
    })
}

const get_patch = () => {
  axios.get(`${URL}patch/`)
    .then((res) => {
      patch.value = res.data.patch;
    })
    .catch((error) => {
      console.error(`Error: ${error}`)
      patch.value = "Error"
    })
}

onBeforeMount(() => {
  get_patch();
});
</script>



<template>
  <div>
    <h1>{{ header }}</h1>
    
    <div class="card">
      <p>
        {{ patch }}
      </p>
      <button type="button" @click="get_status()">Get Status</button>
      <p>
        {{ status }}
      </p>
      <ul>
        <li v-for="todo in todos" :key="todo">
          {{ todo.todo_type }} :  - {{ todo.patch }} -   {{ todo.hotfix }}
        </li>
      </ul>
    </div>
    <div class="card">
      <button type="button" @click="update()" :disabled="todos.length === 0">Load Updates</button>
    </div>
  </div>
</template>

<style scoped>
</style>
