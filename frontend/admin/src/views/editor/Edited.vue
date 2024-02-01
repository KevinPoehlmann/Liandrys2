<script setup>
import { ref, inject } from "vue";


const { mod, changes, pushChanges, closeModal } = defineProps(['mod', 'changes', 'pushChanges', 'closeModal']);


/* const mod = ref(false) */



const saveChanges = () => {
  pushChanges()
}

const cancelChanges = () => {
  closeModal()
}

</script>


<template>
  <div>
    <div v-if="mod" @click="cancelChanges" class="fixed inset-0 flex items-center justify-center">
      <div class="fixed inset-0 bg-black opacity-50"></div>
        <div class="bg-white rounded p-8 shadow-lg z-10" @click.stop>
          <h2 class="text-xl font-semibold mb-4">Changes</h2>
          <div class="border-4 border-black">
            <ul class="w-96 h-96 overflow-y-auto">
              <li v-for="change in changes" :key="change[0]" class="relative group">
                <p>{{ change.key }}: {{ change.oldValue }}  ->  {{ change.value }}</p>
              </li>
            </ul>
          </div>
        <button @click="saveChanges" class="mt-4 px-4 py-2 bg-blue-500 text-white rounded">
          Save
        </button>
        <button @click="cancelChanges" class="mt-4 px-4 py-2 bg-blue-500 text-white rounded">
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>