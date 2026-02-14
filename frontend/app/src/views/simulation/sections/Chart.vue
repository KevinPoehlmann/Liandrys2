<template>
  <div class="w-full">
    <Line :data="chartData" :options="chartOptions" />
  </div>
</template>

<script setup>
import { computed } from "vue"
import { Line } from "vue-chartjs"
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
} from "chart.js"

ChartJS.register(
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler
)

const props = defineProps({
  tickRate: { type: Number, required: true },
  flatList: { type: Array, required: true },

  // start simple: 'total' | 'subtype' | 'source'
  mode: { type: String, default: "total" },

  // optional later: filter sources
  selectedSources: { type: Array, default: () => [] },
})

function isDamage(effect) {
  // your backend enum likely serializes as "Damage"
  return effect?.type_ === "Damage"
}


const damageEvents = computed(() => {
  let ev = props.flatList.filter(isDamage)

  // optional filtering by selectedSources
  if (props.selectedSources?.length) {
    const set = new Set(props.selectedSources.map(String))
    ev = ev.filter(e => set.has(String(e.source)))
  }

  return ev
})

function groupKey(e) {
  if (props.mode === "source") return String(e.source ?? "UNKNOWN_SOURCE")
  if (props.mode === "subtype") return String(e.damage_sub_type ?? "UNKNOWN_SUBTYPE")
  return "TOTAL"
}

/**
 * Returns:
 *  - labels: array of time strings in seconds (x-axis)
 *  - series: Map(groupKey -> array of cumulative values aligned to labels)
 */
const seriesData = computed(() => {
  const tickRate = props.tickRate
  if (typeof tickRate !== "number" || tickRate <= 0) {
    return { labels: [], series: new Map() }
  }

  // delta damage per tick per group
  const deltasByTick = new Map() // tick -> Map(key -> delta)
  for (const e of damageEvents.value) {
    const tick = Number(e.tick)
    const key = groupKey(e)
    const val = Number(e.value) || 0

    if (!deltasByTick.has(tick)) deltasByTick.set(tick, new Map())
    const m = deltasByTick.get(tick)
    m.set(key, (m.get(key) ?? 0) + val)
  }

  const ticks = Array.from(deltasByTick.keys()).sort((a, b) => a - b)
  const labels = ticks.map(t => (t / tickRate).toFixed(2))

  // Determine all keys that occur (for consistent dataset ordering)
  const allKeys = new Set()
  for (const m of deltasByTick.values()) {
    for (const k of m.keys()) allKeys.add(k)
  }

  // Running totals per key
  const running = new Map(Array.from(allKeys).map(k => [k, 0]))
  const series = new Map(Array.from(allKeys).map(k => [k, []]))

  for (const tick of ticks) {
    const m = deltasByTick.get(tick)

    // update running totals
    for (const [k, delta] of m.entries()) {
      running.set(k, (running.get(k) ?? 0) + delta)
    }

    // push a value for every key so arrays align with labels
    for (const k of allKeys) {
      series.get(k).push(running.get(k) ?? 0)
    }
  }

  return { labels, series }
})

// Simple color mapping for subtype mode (you can theme later)
// (Chart.js wants a color per dataset; we keep it minimal for now)
function datasetLabel(key) {
  if (key === "TOTAL") return "Total damage"
  return key
}

const chartData = computed(() => {
  const { labels, series } = seriesData.value

  const keys = Array.from(series.keys())

  let datasets = []
  datasets = keys.map((k) => {
    const c = colorForKey(k)
    return {
      label: datasetLabel(k),
      data: series.get(k),
      fill: true,
      stepped: true,
      pointRadius: 0,
      stack: "damage",
      backgroundColor: c.bg,
      borderColor: c.border,
      borderWidth: 2,
      tension: 0,
    }
    })

  return { labels, datasets }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: "index", intersect: false },
  plugins: {
    legend: { display: true },
    tooltip: { enabled: true },
  },
  scales: {
    x: {
      type: "linear",
      title: { display: true, text: "Time (s)" },
    },
    y: {
      title: { display: true, text: "Cumulative damage" },
      beginAtZero: true,
      stacked: props.mode !== "total", // stacked in subtype/source mode
    },
  },
}))


function colorForKey(key) {
  if (key === "Physical") return {
    bg: "rgba(200, 40, 40, 0.5)",
    border: "rgb(200, 40, 40)"
  }
  if (key === "Magical") return {
    bg: "rgba(180, 80, 200, 0.5)",
    border: "rgb(180, 80, 200)"
  }
  if (key === "True") return {
    bg: "rgba(230, 230, 230, 0.6)",
    border: "rgb(230, 230, 230)"
  }

  return {
    bg: "rgba(100,100,100,0.4)",
    border: "rgb(100,100,100)"
  }
}


</script>

<style scoped>
/* Give the chart some height */
div {
  height: 280px;
}
</style>
