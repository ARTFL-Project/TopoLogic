<template>
    <div class="container-fluid">
        <div v-if="!timeSeriesEnabled" class="card">
            <div class="card-header">Evolution of all topics over time</div>
            <div class="p-4 text-center text-muted">
                Time-series view is unavailable for this corpus because no year metadata was found.
            </div>
        </div>
        <div v-else class="card">
            <div class="card-header">Evolution of all topics over time</div>
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
            startIndex: 0,
            endIndex: 0,
            topicsOverTime: [],
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
        $route: "fetchData"
    },
    methods: {
        fetchData() {
            if (!this.timeSeriesEnabled) {
                return;
            }
            this.fieldName = this.$route.params.fieldName;
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_time_distributions/${this.$globalConfig.databaseName}`
                )
                .then(response => {
                    this.topicsOverTime = response.data.distributions_over_time;

                    // Get start and end index of data to display
                    this.startIndex = this.topicsOverTime[0].topic_evolution.labels.indexOf(
                        this.$globalConfig.timeSeriesConfig.startDate
                    );
                    this.endIndex = this.topicsOverTime[0].topic_evolution.labels.length;
                    for (
                        let index = 0;
                        index <
                        this.topicsOverTime[0].topic_evolution.labels.length;
                        index += 1
                    ) {
                        if (
                            this.topicsOverTime[0].topic_evolution.labels[
                                index
                            ] > this.$globalConfig.timeSeriesConfig.endDate
                        ) {
                            this.endIndex = index + 1;
                            break;
                        }
                    }
                    // Adjust weight of data so that the total weight of all weights equals to 100
                    let topicWeightTotal = 0;
                    for (let dist of this.topicsOverTime) {
                        let topicTotal = dist.topic_evolution.data.reduce(
                            (partialSum, b) => partialSum + b,
                            0
                        );
                        topicWeightTotal += topicTotal;
                    }
                    let multiplier = 100 / topicWeightTotal;
                    for (let dist of this.topicsOverTime) {
                        this.topicsOverTime[
                            dist.topic
                        ].topic_evolution.data = dist.topic_evolution.data.map(
                            weight => weight * multiplier
                        );
                    }

                    this.categories = this.topicsOverTime[0].topic_evolution.labels.slice(
                        this.startIndex,
                        this.endIndex
                    );
                    this.series = this.topicsOverTime.map(topic => ({
                        data: topic.topic_evolution.data.slice(
                            this.startIndex,
                            this.endIndex
                        ),
                        name: topic.topic
                    }));
                });
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
                const idx = this.series.findIndex(s => s.name === topic);
                if (idx !== -1) this.series.splice(idx, 1);
                this.seriesActive.splice(this.seriesActive.indexOf(topic), 1);
                let el = document.getElementById(`topic-${topic}`);
                el.style.backgroundColor = "#fff";
                el.parentNode.style.color = "rgba(0, 0, 0, .35)";
            } else {
                this.series = [
                    ...this.series,
                    {
                        name: topic,
                        data: this.topicsOverTime[topic].topic_evolution.data.slice(
                            this.startIndex,
                            this.endIndex
                        )
                    }
                ];
                this.seriesActive.push(topic);
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
