<template>
  <div class="w-full mt-2">
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
  mode: { type: String, default: "subtype" },

  actor: { type: String, default: "blue" },

  type_: { type: String, default: "Damage" },

  // optional later: filter sources
  selectedSources: { type: Array, default: () => [] },
})


function groupKey(e) {
  if (props.mode === "source") return String(e.source ?? "UNKNOWN_SOURCE")
  if (props.mode === "subtype") return String(e.damage_sub_type ?? "UNKNOWN_SUBTYPE")
  return "TOTAL"
}

const typeObject = computed(() => {
  if (props.type_ === "Damage") {
    return {
      filter_: e => e.type_ === "Damage" && e.actor === props.actor,
      contributions: e => [{
        key: String(e.damage_sub_type ?? "UNKNOWN_SUBTYPE"),
        value: Number(e.value) || 0
      }],
      label: "Damage dealt"
    }
  } else if (props.type_ === "Tank") {
    return {
      filter_: e => e.type_ === "Damage" && e.target === props.actor,
      contributions: e => {
        const subtype = String(e.damage_sub_type ?? "UNKNOWN_SUBTYPE")
        const out = []

        if (e.value > 0) {
          out.push({ key: subtype, value: Number(e.value) || 0 })
        }
        if (e.mitigated > 0) {
          out.push({ key: `Mitigated ${subtype}`, value: Number(e.mitigated) || 0 })
        }
        return out
      },
      label: "Damage taken"
    }
  } else if (props.type_ === "Heal") {
    return {
      filter_: e => e.type_ === "Heal" && e.actor === props.actor,
      contributions: e => [{
        key: "Heal",
        value: Number(e.value) || 0
      }],
      label: "Healing done"
    }
  }
})

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

  const spec = typeObject.value
  const events = props.flatList.filter(spec.filter_)
  // delta damage per tick per group
  const deltasByTick = new Map() // tick -> Map(key -> delta)
  for (const e of events) {
    for (const c of spec.contributions(e)) {
      const tick = Number(e.tick)
      const key = c.key
      const val = Number(c.value) || 0

      if (!deltasByTick.has(tick)) deltasByTick.set(tick, new Map())
      const m = deltasByTick.get(tick)
      m.set(key, (m.get(key) ?? 0) + val)
    }
  }
  console.log("Deltas by tick:", deltasByTick)

  const ticks = Array.from(deltasByTick.keys()).sort((a, b) => a - b)
  const labels = ticks.map(t => (t / tickRate))

  console.log("Ticks:", ticks)
  console.log("Labels (s):", labels)

  // Determine all keys that occur (for consistent dataset ordering)
  const allKeys = new Set()
  for (const m of deltasByTick.values()) {
    for (const k of m.keys()) allKeys.add(k)
  }

  console.log("All group keys:", allKeys)

  // Running totals per key
  const running = new Map(Array.from(allKeys).map(k => [k, 0]))
  const series = new Map(Array.from(allKeys).map(k => [k, []]))

  console.log("Initial running totals:", running)
  console.log("Initial series:", series)

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

  console.log("Final series:", series)

  return { labels, series }
})

// Simple color mapping for subtype mode (you can theme later)
// (Chart.js wants a color per dataset; we keep it minimal for now)
function datasetLabel(key) {
  if (key === "TOTAL") return "Total damage"
  return key
}


function padStepSeries(labels, ys) {
  // labels: number[] (seconds), ys: number[] (cumulative)
  if (!labels.length) {
    // still show origin
    return { labels: [0], ys: [0] }
  }

  // ensure we start at (0,0)
  let newLabels = labels
  let newYs = ys
  if (labels[0] !== 0) {
    newLabels = [0, ...labels]
    newYs = [0, ...ys]
  } else if (ys[0] !== 0) {
    // if first event is at 0 but starts above 0, still force baseline
    newLabels = [0, ...labels]
    newYs = [0, ...ys]
  }

  // pad end to next full second (or at least +1s)
  const lastX = newLabels[newLabels.length - 1]
  const lastY = newYs[newYs.length - 1]

  const paddedEnd = Math.max(Math.ceil(lastX), lastX + 1e-6) // ceil, but never less than lastX
  const endX = paddedEnd === lastX ? lastX + 1 : paddedEnd  // ensure visible horizontal room

  newLabels = [...newLabels, endX]
  newYs = [...newYs, lastY]

  return { labels: newLabels, ys: newYs }
}


const chartData = computed(() => {
  const { labels, series } = seriesData.value

  const keys = Array.from(series.keys())

  const paddedLabels = keys.length
    ? padStepSeries(labels, series.get(keys[0]) ?? []).labels
    : [0]
  
  let datasets = []
  datasets = keys.map((k) => {
    const rawYs = series.get(k) ?? []
    const padded = padStepSeries(labels, rawYs)
    const c = colorForKey(k)
    return {
      label: datasetLabel(k),
      data: padded.ys,
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

  return { labels: paddedLabels, datasets }
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
