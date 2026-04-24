<template>
    <div class="container-fluid">
        <div v-if="!timeSeriesEnabled" class="card">
            <div class="card-header">Evolution of all topics over time</div>
            <div class="p-4 text-center text-muted">
                Time-series view is unavailable for this corpus because no year metadata was found.
            </div>
        </div>
        <div v-else class="card">
            <div class="card-header d-flex align-items-center justify-content-between flex-wrap gap-2">
                <span>Evolution of all topics over time</span>
                <div class="d-flex align-items-center gap-2">
                    <label class="small mb-0">From:</label>
                    <input type="number" class="form-control form-control-sm" style="width: 6rem"
                        :min="dataMinYear" :max="dataMaxYear"
                        v-model.number="startDate" @change="onRangeChange" />
                    <label class="small mb-0">To:</label>
                    <input type="number" class="form-control form-control-sm" style="width: 6rem"
                        :min="dataMinYear" :max="dataMaxYear"
                        v-model.number="endDate" @change="onRangeChange" />
                    <label class="small mb-0 ms-2">Interval (yrs):</label>
                    <select class="form-select form-select-sm" style="width: auto"
                        v-model.number="evolutionInterval">
                        <option v-for="opt in intervalOptions" :key="opt" :value="opt">{{ opt }}</option>
                    </select>
                </div>
            </div>
            <div class="row p-2">
                <div class="col-4">
                    <div class="mb-2">
                        <span
                            class="btn btn-sm btn-outline-danger"
                            style="cursor: pointer"
                            @click="clearAllSeries()"
                        >Clear all topics</span>
                    </div>
                    <div
                        v-for="topic in topicData"
                        :key="topic.name"
                        @click="selectTopic(topic.name)"
                        class="topic"
                    >
                        <span
                            :id="`topic-${topic.name}`"
                            class="topic-legend"
                            :style="`background-color: ${topic.color}`"
                        ></span>
                        Topic {{ topic.name }}: {{ topic.label || topic.description }}
                    </div>
                </div>
                <div class="col-8">
                    <v-chart
                        ref="timeChart"
                        :option="chartOption"
                        :autoresize="true"
                        style="width: 100%; height: 600px"
                    ></v-chart>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
import topicData from "../../topic_words.json";

export default {
    name: "TimeVue",
    data() {
        return {
            timeSeriesEnabled: this.$globalConfig.timeSeriesConfig.enabled !== false,
            intervalOptions: [1, 5, 10, 25, 50, 100],
            evolutionInterval: this.$globalConfig.timeSeriesConfig.interval || 1,
            startDate: this.$globalConfig.timeSeriesConfig.startDate,
            endDate: this.$globalConfig.timeSeriesConfig.endDate,
            dataMinYear: null,  // bounds of the raw data, shown in the year inputs
            dataMaxYear: null,
            rawTopicsOverTime: null,  // per-year data from the API, held for client-side rebucketing
            topicData: topicData,
            topicColorByName: Object.fromEntries(topicData.map(t => [t.name, t.color])),
            allSeriesVisible: true,
            seriesActive: topicData.map(topic => topic.name),
            categories: [],
            series: [{ name: 0, data: [] }]
        };
    },
    computed: {
        chartOption() {
            return {
                animation: false,
                grid: { left: 45, right: 10, top: 10, bottom: 30, containLabel: true },
                xAxis: {
                    type: "category",
                    data: this.categories,
                    boundaryGap: false
                },
                yAxis: {
                    type: "value",
                    axisLabel: {
                        formatter: val => val.toFixed(3)
                    }
                },
                tooltip: { show: false },
                legend: { show: false },
                series: this.series.map(s => ({
                    name: s.name,
                    type: "line",
                    data: s.data,
                    smooth: true,
                    showSymbol: false,
                    lineStyle: { width: 1.5, color: this.topicColorByName[s.name] },
                    itemStyle: { color: this.topicColorByName[s.name] }
                }))
            };
        }
    },
    created() {
        if (this.timeSeriesEnabled) {
            this.fetchData();
        }
    },
    watch: {
        // call again the method if the route changes
        $route: "fetchData",
        evolutionInterval() { this.rebuild(); }
    },
    methods: {
        fetchData() {
            if (!this.timeSeriesEnabled) {
                return;
            }
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_time_distributions/${this.$globalConfig.databaseName}`
                )
                .then(response => {
                    this.rawTopicsOverTime = response.data.distributions_over_time;
                    const labels = this.rawTopicsOverTime[0].topic_evolution.labels;
                    this.dataMinYear = labels[0];
                    this.dataMaxYear = labels[labels.length - 1];
                    // If the config left start/end open, fall back to the raw
                    // data's bounds so the inputs always show a concrete year.
                    if (this.startDate == null) this.startDate = this.dataMinYear;
                    if (this.endDate == null) this.endDate = this.dataMaxYear;
                    this.rebuild();
                });
        },
        onRangeChange() {
            // Clamp to available range and enforce start <= end.
            if (this.dataMinYear != null && this.startDate < this.dataMinYear) this.startDate = this.dataMinYear;
            if (this.dataMaxYear != null && this.endDate > this.dataMaxYear) this.endDate = this.dataMaxYear;
            if (this.startDate > this.endDate) this.startDate = this.endDate;
            this.rebuild();
        },
        rebucket(evolution, interval) {
            // Mirror of Topic.vue's rebucket (and the server-side DB._rebucket):
            // align bucket starts to multiples of `interval` and average within.
            if (!evolution || !evolution.labels || interval <= 1) return evolution;
            const byYear = new Map();
            for (let i = 0; i < evolution.labels.length; i += 1) {
                byYear.set(evolution.labels[i], evolution.data[i]);
            }
            const first = evolution.labels[0];
            const last = evolution.labels[evolution.labels.length - 1];
            const labels = [];
            const data = [];
            let bucketStart = Math.floor(first / interval) * interval;
            while (bucketStart <= last) {
                const bucketEnd = bucketStart + interval;
                const vals = [];
                for (let y = bucketStart; y < bucketEnd; y += 1) {
                    if (byYear.has(y)) vals.push(byYear.get(y));
                }
                if (vals.length > 0) {
                    labels.push(bucketStart);
                    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
                    data.push(mean);
                }
                bucketStart = bucketEnd;
            }
            return { labels, data };
        },
        sliceRange(labels) {
            // Snap to the bucket containing startDate / endDate.
            let start = 0;
            let end = labels.length;
            if (this.startDate != null) {
                for (let i = 0; i < labels.length; i += 1) {
                    if (labels[i] <= this.startDate) start = i;
                    else break;
                }
            }
            if (this.endDate != null) {
                for (let i = 0; i < labels.length; i += 1) {
                    if (labels[i] > this.endDate) { end = i + 1; break; }
                }
            }
            return { start, end };
        },
        rebuild() {
            if (!this.rawTopicsOverTime) return;
            const interval = parseInt(this.evolutionInterval) || 1;
            const bucketed = this.rawTopicsOverTime.map(topic => ({
                topic: topic.topic,
                evolution: this.rebucket(topic.topic_evolution, interval)
            }));
            // Normalize so the summed weight across all topics over the full
            // range totals 100 — matches the pre-bucketing behavior so the
            // visible portion stays comparable across interval settings.
            const { start, end } = this.sliceRange(bucketed[0].evolution.labels);
            let grandTotal = 0;
            for (const t of bucketed) {
                for (const w of t.evolution.data) grandTotal += w;
            }
            const multiplier = grandTotal > 0 ? 100 / grandTotal : 1;
            this.categories = bucketed[0].evolution.labels.slice(start, end);
            this.series = bucketed.map(t => ({
                name: t.topic,
                data: t.evolution.data.slice(start, end).map(w => w * multiplier)
            }));
            // Restore visibility state for topics the user had already toggled off.
            if (this.seriesActive.length !== this.series.length) {
                this.series = this.series.map(s =>
                    this.seriesActive.includes(s.name)
                        ? s
                        : { name: s.name, data: this.categories.map(() => 0.0) }
                );
            }
        },
        clearAllSeries() {
            this.series = this.series.map(series => ({
                name: series.name,
                data: this.categories.map(() => 0.0)
            }));
            document
                .querySelectorAll(".topic-legend")
                .forEach(el => (el.style.backgroundColor = "#fff"));
            document
                .querySelectorAll(".topic")
                .forEach(el => (el.style.color = "rgba(0, 0, 0, 0.35)"));
            this.seriesActive = [];
        },
        selectTopic(topic) {
            if (this.seriesActive.includes(topic)) {
                this.seriesActive.splice(this.seriesActive.indexOf(topic), 1);
                const idx = this.series.findIndex(s => s.name === topic);
                if (idx !== -1) {
                    this.series.splice(idx, 1, { name: topic, data: this.categories.map(() => 0.0) });
                }
                let el = document.getElementById(`topic-${topic}`);
                el.style.backgroundColor = "#fff";
                el.parentNode.style.color = "rgba(0, 0, 0, .35)";
            } else {
                this.seriesActive.push(topic);
                // Rebuild from raw so this topic's real data comes back.
                this.rebuild();
                const el = document.getElementById(`topic-${topic}`);
                el.style.backgroundColor = this.topicColorByName[topic];
                el.parentNode.style.color = "inherit";
            }
            window.scrollTo({ top: 0, behavior: "smooth" });
        }
    }
};
</script>
<style scoped>
.topic {
    font-size: 80%;
    padding: 0.25rem;
    text-overflow: ellipsis;
    white-space: nowrap;
    overflow: hidden;
    cursor: pointer;
}
.topic-legend {
    padding: 8px;
    vertical-align: middle;
    display: inline-block;
    border-radius: 50%;
    border-color: rgb(0, 0, 0);
    border-style: solid;
    border-width: 2px;
}
</style>
