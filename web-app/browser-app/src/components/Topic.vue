<template>
    <div class="container-fluid">
        <h5 class="mb-4" style="text-align: center">
            <template v-if="topicData[parseInt(topic)] && topicData[parseInt(topic)].label">
                <b>{{ topicData[parseInt(topic)].label }}</b> topic
            </template>
            <template v-else>
                Topic <b>{{ topic }}</b>
            </template>
            across corpus (overall frequency of {{ frequency }}%)
        </h5>
        <div v-if="loading" class="text-center" style="position: absolute; left: 0; right: 0; z-index: 10">
            <div class="spinner-border" style="width: 5rem; height: 5rem" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
        <div class="row">
            <div class="col-3">
                <div class="card shadow-sm">
                    <div class="card-header">Top Tokens</div>
                    <div class="px-3 pt-2 pb-2">
                        <div class="px-3" v-for="word in wordWeights" :key="word.word">
                            <div class="row word-weight" @click="goToWord(word.word)">
                                <span class="frequency-bar" :style="`width: ${word.barWidth}%;`"></span>
                                <div class="col-8 word ps-1">{{ word.word }}</div>
                                <div class="col-4 position-relative">
                                    <span class="frequency-value">{{ word.weight }}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-9">
                <div class="row">
                    <div class="col-12" v-if="timeSeriesEnabled">
                        <div class="card shadow-sm">
                            <div class="card-header d-flex align-items-center justify-content-between flex-wrap gap-2">
                                <span>Distribution of topic weight over time</span>
                                <div class="d-flex align-items-center gap-2 correlation-controls">
                                    <label class="small mb-0">Interval (yrs):</label>
                                    <select class="form-select form-select-sm smoothing-input"
                                        v-model.number="evolutionInterval">
                                        <option v-for="opt in intervalOptions" :key="opt" :value="opt">{{ opt }}</option>
                                    </select>
                                </div>
                            </div>
                            <div class="ps-2 pe-2 pt-2">
                                <v-chart :option="topicEvolutionOption" :autoresize="true"
                                    @click="goToYear" style="width: 100%; height: 300px"></v-chart>
                            </div>
                        </div>
                    </div>
                    <div class="col-6" v-if="timeSeriesEnabled">
                        <div class="card mt-4 shadow-sm">
                            <div class="card-header d-flex align-items-center justify-content-between flex-wrap gap-2">
                                <span>5 most correlated topics over time</span>
                                <div class="d-flex align-items-center gap-2 correlation-controls">
                                    <label class="small mb-0">Interval (yrs):</label>
                                    <select class="form-select form-select-sm smoothing-input"
                                        v-model.number="correlationInterval">
                                        <option v-for="opt in intervalOptions" :key="opt" :value="opt">{{ opt }}</option>
                                    </select>
                                    <span class="small mb-0 ms-2">Trend:</span>
                                    <div class="direction-toggle">
                                        <button type="button" :class="['dir-btn', { active: direction === 'positive' }]"
                                            @click="direction = 'positive'"
                                            title="Topics that rise and fall together">Same</button>
                                        <button type="button" :class="['dir-btn', { active: direction === 'negative' }]"
                                            @click="direction = 'negative'"
                                            title="Topics with opposite trends">Opposite</button>
                                    </div>
                                </div>
                            </div>
                            <v-chart ref="timeChart" :option="similarEvolutionOption" :autoresize="true"
                                style="width: 100%; height: 400px"></v-chart>
                            <div class="similar-legend">
                                <div v-for="(localTopic, seriesIndex) in similarEvolutionSeries" :key="localTopic.name"
                                    class="topic ps-2 pe-2 pb-1" style="font-size: 80%"
                                    @click="goToTopic(localTopic.name)">
                                    <span v-if="localTopic.name != topic">
                                        <span :id="`topic-${localTopic.name}`" class="topic-legend"
                                            :style="`background-color: ${similarEvolutionOptions.colors[seriesIndex]}`"></span>
                                        <template v-if="topicData[parseInt(localTopic.name)].label">
                                            <span class="ps-2">{{ topicData[parseInt(localTopic.name)].label
                                            }}</span></template>
                                        <template v-else><span class="ps-2">Topic {{ localTopic.name
                                                }}</span></template>
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div :class="timeSeriesEnabled ? 'col-6' : 'col-12'">
                        <div class="card mt-4 shadow-sm">
                            <div class="card-header">{{ documentsHeader }}</div>
                            <div class="d-flex justify-content-center position-absolute"
                                style="left: 0; right: 0; top: 4rem; z-index: 1" v-if="yearLoading">
                                <div class="spinner-border" style="width: 4rem; height: 4rem" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                            </div>
                            <ul class="list-group list-group-flush">
                                <li class="list-group-item" v-for="doc in documents" :key="doc.doc_id">
                                    <citations :doc="doc" :id="`${doc.doc_id}`" :philo-db="`${doc.metadata.philo_db}`">
                                    </citations>
                                    <span class="badge rounded-pill bg-secondary float-end">{{ (doc.score *
                                        100).toFixed(2) }}</span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
import topicData from "../../topic_words.json";
import Citations from "./Citations.vue";

export default {
    name: "Topic",
    components: {
        Citations,
    },
    data() {
        return {
            topicData: topicData,
            timeSeriesEnabled: this.$globalConfig.timeSeriesConfig.enabled !== false,
            wordWeights: [],
            documents: [],
            similarTopics: [],
            loading: false,
            yearLoading: false,
            frequency: 0,
            year: 0,
            topic: this.$route.params.topic,
            direction: "positive",
            intervalOptions: [1, 5, 10, 25, 50, 100],
            evolutionInterval: this.$globalConfig.timeSeriesConfig.interval || 1,
            correlationInterval: this.$globalConfig.timeSeriesConfig.interval || 1,
            rawTopicEvolution: null,    // per-year data, held for client-side rebucketing of the bar chart
            currentSmoothedEvolution: null,  // server-smoothed current topic for the correlation overlay
            refetchTimer: null,
            topicEvolutionCategories: [],
            topicEvolutionSeries: [
                {
                    name: "Topic Evolution",
                    data: [],
                },
            ],
            similarEvolutionCategories: [],
            similarEvolutionOptions: {
                // Retained for the in-template legend swatch lookup via `.colors[seriesIndex]`.
                colors: ["#33b2df", "#546E7A", "#d4526e", "#13d8aa", "#A5978B"],
            },
            similarEvolutionSeries: [{ name: 0, data: [] }],
        };
    },
    computed: {
        topicEvolutionOption() {
            const interval = parseInt(this.evolutionInterval) || 1;
            const formatBucket = (val) => {
                if (interval <= 1) return String(val);
                return `${val}–${parseInt(val) + interval - 1}`;
            };
            const td = topicData[parseInt(this.topic)];
            const barColor = (td && td.color) || "#ad4242";
            return {
                animation: false,
                grid: { left: 40, right: 10, top: 10, bottom: 30, containLabel: true },
                xAxis: {
                    type: "category",
                    data: this.topicEvolutionCategories,
                    axisLabel: { formatter: formatBucket, hideOverlap: true },
                },
                yAxis: { type: "value" },
                tooltip: {
                    trigger: "axis",
                    axisPointer: { type: "shadow" },
                    formatter: (params) => {
                        const p = params[0];
                        return `${formatBucket(p.name)}<br/>${p.value}`;
                    },
                },
                series: [
                    {
                        name: this.topicEvolutionSeries[0].name,
                        type: "bar",
                        data: this.topicEvolutionSeries[0].data,
                        barWidth: "90%",
                        itemStyle: { color: barColor, opacity: 0.9 },
                    },
                ],
            };
        },
        similarEvolutionOption() {
            const currentTopic = String(this.topic);
            return {
                animation: false,
                color: this.similarEvolutionOptions.colors,
                grid: { left: 40, right: 10, top: 10, bottom: 30, containLabel: true },
                xAxis: {
                    type: "category",
                    data: this.similarEvolutionCategories,
                    boundaryGap: false,
                },
                yAxis: {
                    type: "value",
                    axisLabel: {
                        formatter: (val) => (typeof val === "number" ? val.toFixed(2) : String(val)),
                    },
                },
                tooltip: { show: false },
                legend: { show: false },
                series: this.similarEvolutionSeries.map((s) => {
                    const isCurrent = String(s.name) === currentTopic;
                    return {
                        name: s.name,
                        type: "line",
                        data: s.data,
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1.5 },
                        ...(isCurrent ? { areaStyle: { opacity: 0.1 } } : {}),
                    };
                }),
            };
        },
        documentsHeader: function () {
            if (this.timeSeriesEnabled && this.year) {
                return `Top ${this.documents.length} documents by weight for this topic (${this.year})`;
            }
            return `Top ${this.documents.length} documents by weight for this topic`;
        },
        philoTimeSeriesBiBlioLink: function () {
            let dbUrls = {}
            for (let dbname in this.$globalConfig.philoLogicUrls) {
                let link = this.$globalConfig.philoLogicUrls[dbname]
                dbUrls[dbname] = `${link}/time_series?topicmodel=${this.topic}&year_interval=${this.$modelConfig.TOPICS_OVER_TIME.topics_over_time_interval}&start_date=${this.$globalConfig.timeSeriesConfig.startDate}&end_date=${this.$globalConfig.timeSeriesConfig.endDate}`;
            }
            return dbUrls
        },
        philoTimeSeriesQueryLink: function () {
            let queryString = topicData[parseInt(this.topic)].description
                .split(", ")
                .map((a) => `${a}.?`)
                .join(" OR ");
            return `${this.$globalConfig.philoLogicUrl}/time_series?year_interval=${this.$modelConfig.TOPICS_OVER_TIME.topics_over_time_interval}&start_date=${this.$globalConfig.timeSeriesConfig.startDate}&end_date=${this.$globalConfig.timeSeriesConfig.endDate}&q=${queryString}`;
        },
    },
    mounted() {
        this.fetchData();
    },
    watch: {
        // call again the method if the route changes
        $route: "fetchData",
        direction() { this.debouncedFetch(); },
        correlationInterval() { this.debouncedFetch(); },
        evolutionInterval() { this.rebuildBarChart(); },
    },
    methods: {
        debouncedFetch() {
            clearTimeout(this.refetchTimer);
            this.refetchTimer = setTimeout(this.fetchData, 300);
        },
        fetchData() {
            this.loading = true;
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_topic_data/${this.$globalConfig.databaseName}/${this.$route.params.topic}`,
                    { params: {
                        correlation_interval: this.correlationInterval,
                        direction: this.direction,
                    } }
                )
                .then((response) => {
                    this.loading = false;
                    this.topic = this.$route.params.topic;
                    this.documents = response.data.documents;
                    this.frequency = this.smartRound(response.data.frequency * 100);
                    this.similarTopics = response.data.similar_topics;
                    let scaledWeights = this.scaleWordWeights(
                        response.data.word_distribution.data
                    );
                    this.wordWeights = response.data.word_distribution.labels.map(
                        (word, i) => ({
                            word: word,
                            weight: this.smartRound(response.data.word_distribution.data[
                                i
                            ]),
                            barWidth:
                                scaledWeights[i],
                        })
                    );

                    if (this.timeSeriesEnabled) {
                        this.rawTopicEvolution = response.data.topic_evolution;
                        this.currentSmoothedEvolution = response.data.current_smoothed_evolution;
                        this.rebuildBarChart();
                        this.rebuildCorrelationChart(response.data.similar_topics);
                        this.$nextTick(function () {
                            let selectedYear = document.querySelector(
                                "path[selected='true']"
                            );
                            if (selectedYear != null) {
                                selectedYear.setAttribute("selected", "false");
                            }
                        });
                    }
                });
        },
        rebucket(evolution, interval) {
            // Align bucket starts to multiples of `interval` (e.g. interval=10 →
            // buckets 1770, 1780, 1790, not 1774, 1784). Mirror of the server-side
            // _rebucket in DB.py.
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
                const bucketEnd = bucketStart + interval; // exclusive
                const vals = [];
                for (let y = bucketStart; y < bucketEnd; y += 1) {
                    if (byYear.has(y)) vals.push(byYear.get(y));
                }
                if (vals.length > 0) {
                    labels.push(bucketStart);
                    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
                    data.push(Math.round(mean * 100) / 100);
                }
                bucketStart = bucketEnd;
            }
            return { labels, data };
        },
        sliceByConfig(evolution) {
            // Respect the per-deployment date window in appConfig.
            const startDate = this.$globalConfig.timeSeriesConfig.startDate;
            const endDate = this.$globalConfig.timeSeriesConfig.endDate;
            let start = 0;
            let end = evolution.labels.length;
            // Snap to the bucket that contains startDate (closest label ≤ startDate).
            if (startDate != null) {
                for (let i = 0; i < evolution.labels.length; i += 1) {
                    if (evolution.labels[i] <= startDate) start = i;
                    else break;
                }
            }
            if (endDate != null) {
                for (let i = 0; i < evolution.labels.length; i += 1) {
                    if (evolution.labels[i] > endDate) { end = i + 1; break; }
                }
            }
            return { start, end };
        },
        rebuildBarChart() {
            if (!this.rawTopicEvolution) return;
            const bucketed = this.rebucket(this.rawTopicEvolution, this.evolutionInterval);
            const { start, end } = this.sliceByConfig(bucketed);
            this.year = `${bucketed.labels[start]}-${bucketed.labels[end - 1]}`;
            this.buildTopicEvolution(bucketed, start, end);
        },
        rebuildCorrelationChart(similarTopics) {
            if (!similarTopics || !similarTopics.length) return;
            // Server returns similar topics' evolutions already rebucketed AND
            // smoothed at correlationInterval. Use as-is — the correlation
            // metric was computed from the same series shown here.
            const { start, end } = this.sliceByConfig(similarTopics[0].topic_evolution);
            const roundSeries = (arr) => arr.map((v) => Math.round(v * 100) / 100);
            const currentSeries = this.currentSmoothedEvolution
                ? this.currentSmoothedEvolution.data
                : [];
            this.similarEvolutionSeries = [
                ...similarTopics.slice(0, 5).map((topic) => ({
                    data: roundSeries(topic.topic_evolution.data.slice(start, end)),
                    name: topic.topic.toString(),
                    type: "line",
                })),
                {
                    name: this.topic,
                    data: roundSeries(currentSeries.slice(start, end)),
                    type: "area",
                },
            ];
            this.similarEvolutionCategories = similarTopics[0].topic_evolution.labels.slice(start, end);
            // One color per series entry, matched to the topic's own palette color
            // so the swatch in the in-page legend and the line color always agree
            // — and the same topic has the same color across TimeView, Topic, and
            // the landscape views.
            this.similarEvolutionOptions = {
                ...this.similarEvolutionOptions,
                colors: this.similarEvolutionSeries.map((s) => {
                    const td = topicData[parseInt(s.name)];
                    return td ? td.color : "#888";
                }),
            };
        },
        scaleWordWeights(wordWeights) {
            // We want to scale the word weights so that the largest weight is 100
            let maxWeight = Math.max(...wordWeights);
            return wordWeights.map((weight) => (weight / maxWeight) * 100);
        },
        smartRound(num) {
            return num === 0 ? "0.00" : Number(Number(num).toPrecision(2)).toString();
        },
        sumArray: function (arr) {
            return arr.reduce(function (a, b) {
                return a + b;
            }, 0);
        },
        formatTopicEvolution(topicEvolution) {
            let arrSum = this.sumArray(topicEvolution);
            let weightedTopicEvolution = [];
            for (let value of topicEvolution) {
                weightedTopicEvolution.push(
                    ((value / arrSum) * 100).toFixed(2)
                );
            }
            return weightedTopicEvolution;
        },
        buildTopicEvolution(topicEvolution, startIndex, endIndex) {
            topicEvolution.data = topicEvolution.data.slice(
                startIndex,
                endIndex
            );
            topicEvolution.labels = topicEvolution.labels.slice(
                startIndex,
                endIndex
            );
            this.topicEvolutionSeries = [
                {
                    name: this.topicEvolutionSeries[0].name,
                    data: this.formatTopicEvolution(topicEvolution.data),
                },
            ];
            this.topicEvolutionCategories = topicEvolution.labels;
        },
        goToWord(word) {
            this.$router.push(`/word/${word}`);
        },
        goToYear(params) {
            // ECharts click event: only react to clicks on the bar series itself
            // (not on empty chart area).
            if (!params || params.componentType !== "series") return;
            const year = this.topicEvolutionCategories[params.dataIndex];
            if (year == null) return;
            this.yearLoading = true;
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_docs_in_topic_by_year/${this.$globalConfig.databaseName}/${this.$route.params.topic}/${year}`,
                    { params: { interval: this.evolutionInterval } }
                )
                .then((response) => {
                    this.documents = response.data;
                    const interval = parseInt(this.evolutionInterval) || 1;
                    this.year = interval <= 1
                        ? String(year)
                        : `${year}–${parseInt(year) + interval - 1}`;
                    this.yearLoading = false;
                });
        },
        goToTopic(topic) {
            this.$router.push(`/topic/${topic}`);
        },
    },
};
</script>
<style scoped lang="scss">
@use "../assets/styles/theme.module.scss" as theme;

:deep(path[selected="true"]) {
    fill: rgba(theme.$passage-color, 0.9);
}

// Smoothing + direction controls embedded in the red card-header.
.correlation-controls {
    font-weight: normal;
    font-size: 0.85rem;

    .smoothing-input {
        width: auto;
        min-width: 4.5rem;
    }
}

.direction-toggle {
    display: inline-flex;
    border: 1px solid #fff;
    border-radius: 0.25rem;
    overflow: hidden;

    .dir-btn {
        background: transparent;
        color: #fff;
        border: 0;
        padding: 0.15rem 0.55rem;
        font-size: 0.9rem;
        line-height: 1;
        font-weight: 600;
        cursor: pointer;

        &+.dir-btn {
            border-left: 1px solid rgba(255, 255, 255, 0.4);
        }

        &.active {
            background: #fff;
            color: theme.$card-header-color;
        }

        &:not(.active):hover {
            background: rgba(255, 255, 255, 0.15);
        }
    }
}

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
}

.word-weight {
    position: relative;
    cursor: pointer;
    line-height: 1.75rem;
    margin-bottom: 0.5rem;
}

.frequency-value {
    display: inline-block;
    position: relative;
    z-index: 1;
    width: 100%;
    text-align: end;
}

.frequency-bar {
    display: inline-block;
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    background-color: rgba(theme.$link-color, 0.35);
}

.similar-legend {
    margin-top: -1rem;
}

.row:hover>.frequency-bar {
    background-color: rgba(theme.$link-color, 0.55);
}

.row:hover>.word {
    font-weight: 600;
}

.row.word-weight:hover {
    background-color: #f8f8f8;
}
</style>
