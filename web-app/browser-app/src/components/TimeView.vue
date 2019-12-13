<template>
    <b-container fluid>
        <b-card no-body header="Evolution of all topics over time">
            <b-row class="p-2">
                <b-col cols="4">
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
                            :style="
                                `background-color: ${
                                    options.colors[topic.name]
                                }`
                            "
                        ></span>
                        Topic {{ topic.name }}: {{ topic.description }}
                    </div>
                </b-col>
                <b-col cols="8">
                    <apexchart
                        ref="timeChart"
                        width="100%"
                        height="600px"
                        :series="series"
                        :options="options"
                    ></apexchart>
                </b-col>
            </b-row>
        </b-card>
    </b-container>
</template>
<script>
import topicData from "../../topic_words.json";

export default {
    name: "TimeVue",
    data() {
        return {
            startIndex: 0,
            endIndex: 0,
            topicsOverTime: [],
            topicData: topicData,
            allSeriesVisible: true,
            seriesActive: topicData.map(topic => topic.name),
            options: {
                chart: {
                    id: "topic-evolution",
                    toolbar: {
                        show: false
                    }
                },
                yaxis: {
                    labels: {
                        formatter: val => val.toFixed(3)
                    }
                },
                xaxis: {
                    categories: []
                },
                colors: this.shuffleColors(),
                stroke: {
                    curve: "smooth",
                    width: 1.5
                },
                grid: {
                    padding: {
                        left: 0,
                        // right: 0,
                        top: 0,
                        bottom: 0
                    }
                },
                tooltip: {
                    enabled: false
                },
                legend: {
                    show: false
                }
            },
            series: [{ name: 0, data: [] }]
        };
    },
    created() {
        this.fetchData();
    },
    watch: {
        // call again the method if the route changes
        $route: "fetchData"
    },
    methods: {
        fetchData() {
            this.fieldName = this.$route.params.fieldName;
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_time_distributions/${this.$globalConfig.databaseName}?interval=${this.$globalConfig.timeSeriesConfig.interval}`
                )
                .then(response => {
                    this.topicsOverTime = response.data.distributions_over_time;
                    this.startIndex = this.topicsOverTime[0].topic_evolution.labels.indexOf(
                        this.$globalConfig.timeSeriesConfig.startDate
                    );
                    this.endIndex =
                        this.topicsOverTime[0].topic_evolution.labels.indexOf(
                            this.$globalConfig.timeSeriesConfig.endDate
                        ) + 1;
                    this.options = {
                        ...this.options,
                        ...{
                            xaxis: {
                                categories: this.topicsOverTime[0].topic_evolution.labels.slice(
                                    this.startIndex,
                                    this.endIndex
                                )
                            }
                        }
                    };
                    this.series = this.topicsOverTime.map(topic => ({
                        data: topic.topic_evolution.data.slice(
                            this.startIndex,
                            this.endIndex
                        ),
                        name: topic.topic
                    }));
                });
        },
        shuffleColors() {
            let unshuffled = topicData.map(topic =>
                this.randomizeColors(topicData.length, topic.name)
            );
            let shuffled = unshuffled
                .map(a => ({ sort: Math.random(), value: a }))
                .sort((a, b) => a.sort - b.sort)
                .map(a => a.value);
            return shuffled;
        },
        clearAllSeries() {
            this.series = this.series.map(series => ({
                name: series.name,
                data: this.options.xaxis.categories.map(() => 0.0)
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
            console.log(topic, this.seriesActive.indexOf(topic));
            if (this.seriesActive.includes(topic)) {
                for (let i = 0; i < this.series.length; i += 1) {
                    if (topic == this.series[i].name) {
                        this.series[i].data = [];
                    }
                }
                this.seriesActive.splice(this.seriesActive.indexOf(topic), 1);
                this.series.splice(this.series.indexOf(topic), 1);
                let el = document.getElementById(`topic-${topic}`);
                el.style.backgroundColor = "#fff";
                el.parentNode.style.color = "rgba(0, 0, 0, .35)";
            } else {
                let localSeries = JSON.parse(JSON.stringify(this.series));
                localSeries[topic] = {
                    name: topic,
                    data: this.topicsOverTime[topic].topic_evolution.data.slice(
                        this.startIndex,
                        this.endIndex
                    )
                };
                this.series = localSeries;
                this.seriesActive.push(topic);
                this.highlightTopic(topic, topic, this.series.length);
                let el = document.getElementById(`topic-${topic}`);
                el.parentNode.style.color = "inherit";
            }
            window.scrollTo({ top: 0, behavior: "smooth" });
        },
        highlightTopic(topic, indexNum) {
            document.getElementById(
                `topic-${topic}`
            ).style.backgroundColor = this.options.colors[indexNum];
        },
        randomizeColors(colors, colorNum) {
            colorNum += 1;
            var HSLToRGB = function(h, s, l) {
                // Must be fractions of 1
                s /= 100;
                l /= 100;

                let c = (1 - Math.abs(2 * l - 1)) * s,
                    x = c * (1 - Math.abs(((h / 60) % 2) - 1)),
                    m = l - c / 2,
                    r = 0,
                    g = 0,
                    b = 0;
                if (0 <= h && h < 60) {
                    r = c;
                    g = x;
                    b = 0;
                } else if (60 <= h && h < 120) {
                    r = x;
                    g = c;
                    b = 0;
                } else if (120 <= h && h < 180) {
                    r = 0;
                    g = c;
                    b = x;
                } else if (180 <= h && h < 240) {
                    r = 0;
                    g = x;
                    b = c;
                } else if (240 <= h && h < 300) {
                    r = x;
                    g = 0;
                    b = c;
                } else if (300 <= h && h < 360) {
                    r = c;
                    g = 0;
                    b = x;
                }
                r = Math.round((r + m) * 255);
                g = Math.round((g + m) * 255);
                b = Math.round((b + m) * 255);

                return "rgb(" + r + "," + g + "," + b + ")";
            };
            return HSLToRGB((colorNum * (360 / colors)) % 360, 100, 60);
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
