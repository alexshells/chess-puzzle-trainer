<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CategoryRating } from '../api'

const props = defineProps<{ ratings: CategoryRating[] }>()

const SIZE = 420
const CENTER = SIZE / 2
const RADIUS = 160
const RING_FRACTIONS = [0.25, 0.5, 0.75, 1]

// A tight domain would exaggerate small differences into a wildly spiky
// shape, so the value range is padded and floored to a minimum span.
const domain = computed(() => {
  const values = props.ratings.map((r) => r.rating)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const MIN_SPAN = 400
  let lo = Math.floor((min - 50) / 100) * 100
  let hi = Math.ceil((max + 50) / 100) * 100
  if (hi - lo < MIN_SPAN) {
    const pad = (MIN_SPAN - (hi - lo)) / 2
    lo -= pad
    hi += pad
  }
  return { lo, hi }
})

function angleFor(index: number): number {
  const n = props.ratings.length
  return (Math.PI * 2 * index) / n - Math.PI / 2
}

function pointAt(index: number, radiusFraction: number): { x: number; y: number } {
  const angle = angleFor(index)
  return {
    x: CENTER + RADIUS * radiusFraction * Math.cos(angle),
    y: CENTER + RADIUS * radiusFraction * Math.sin(angle),
  }
}

function ringPolygon(fraction: number): string {
  return props.ratings
    .map((_, i) => {
      const p = pointAt(i, fraction)
      return `${p.x},${p.y}`
    })
    .join(' ')
}

const dataPoints = computed(() =>
  props.ratings.map((r, i) => {
    const fraction = (r.rating - domain.value.lo) / (domain.value.hi - domain.value.lo)
    return { ...pointAt(i, Math.max(0, Math.min(1, fraction))), rating: r }
  }),
)

const dataPolygon = computed(() => dataPoints.value.map((p) => `${p.x},${p.y}`).join(' '))

function labelPosition(index: number): { x: number; y: number; anchor: 'start' | 'middle' | 'end' } {
  const angle = angleFor(index)
  const labelRadius = RADIUS + 22
  const x = CENTER + labelRadius * Math.cos(angle)
  const y = CENTER + labelRadius * Math.sin(angle)
  // Center-anchor labels near the top/bottom axes, side-anchor the rest so
  // text grows away from the chart rather than overlapping it.
  const cos = Math.cos(angle)
  const anchor = cos > 0.3 ? 'start' : cos < -0.3 ? 'end' : 'middle'
  return { x, y, anchor }
}

const hoveredIndex = ref<number | null>(null)
</script>

<template>
  <div class="radar" v-if="ratings.length > 0">
    <svg :viewBox="`0 0 ${SIZE} ${SIZE}`" class="radar-svg">
      <polygon
        v-for="fraction in RING_FRACTIONS"
        :key="fraction"
        :points="ringPolygon(fraction)"
        class="ring"
      />
      <line
        v-for="(_, i) in ratings"
        :key="`axis-${i}`"
        :x1="CENTER"
        :y1="CENTER"
        :x2="pointAt(i, 1).x"
        :y2="pointAt(i, 1).y"
        class="axis"
      />
      <polygon :points="dataPolygon" class="data-fill" />
      <polyline :points="dataPolygon + ' ' + dataPoints[0]?.x + ',' + dataPoints[0]?.y" class="data-stroke" />

      <text
        v-for="(r, i) in ratings"
        :key="`label-${i}`"
        v-bind="labelPosition(i)"
        class="axis-label"
      >
        {{ r.label }}
      </text>

      <g v-for="(p, i) in dataPoints" :key="`point-${i}`">
        <circle
          :cx="p.x"
          :cy="p.y"
          r="12"
          class="hit-target"
          @mouseenter="hoveredIndex = i"
          @mouseleave="hoveredIndex = null"
          @focus="hoveredIndex = i"
          @blur="hoveredIndex = null"
          tabindex="0"
        />
        <circle :cx="p.x" :cy="p.y" r="4" class="data-point" />
      </g>

      <g v-if="hoveredIndex !== null" class="tooltip">
        <rect
          :x="dataPoints[hoveredIndex]!.x - 40"
          :y="dataPoints[hoveredIndex]!.y - 32"
          width="80"
          height="22"
          rx="4"
        />
        <text :x="dataPoints[hoveredIndex]!.x" :y="dataPoints[hoveredIndex]!.y - 17" text-anchor="middle">
          {{ ratings[hoveredIndex]!.label }}: {{ ratings[hoveredIndex]!.rating }}
        </text>
      </g>
    </svg>

    <ul class="rating-list">
      <li v-for="r in ratings" :key="r.category">
        <span>{{ r.label }}</span>
        <span class="rating-value">{{ r.rating }}</span>
      </li>
    </ul>
  </div>
  <p v-else class="counter">
    Solve a few more puzzles to see your category ratings.
  </p>
</template>

<style scoped>
.radar {
  display: flex;
  flex-wrap: wrap;
  gap: 2.5rem;
  align-items: center;
  justify-content: center;
}
.radar-svg { width: 420px; height: 420px; flex: none; overflow: visible; }
.ring { fill: none; stroke: #3a352c; stroke-width: 1; }
.axis { stroke: #3a352c; stroke-width: 1; }
.data-fill { fill: #b8985a; fill-opacity: 0.22; stroke: none; }
.data-stroke { fill: none; stroke: #b8985a; stroke-width: 2; stroke-linejoin: round; }
.data-point { fill: #b8985a; }
.hit-target { fill: transparent; cursor: pointer; }
.hit-target:focus { outline: none; }
.axis-label { fill: #cfc6b3; font-size: 10px; }
.tooltip rect { fill: #242019; stroke: #3a352c; stroke-width: 1; }
.tooltip text { fill: #ede6d6; font-size: 11px; }

.rating-list {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: 0.9rem;
  min-width: 160px;
}
.rating-list li {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.3rem 0;
  border-bottom: 1px solid #33302a;
}
.rating-value { color: #b8985a; font-weight: 600; }
.counter { color: #cfc6b3; font-size: 0.9rem; }
</style>
