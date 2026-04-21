<template>
    <div class="container-fluid">
        <h5 class="mb-4" style="text-align: center">
            Representation of topic
            <b>{{ topic }}</b>
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
                            <div class="card-header">Distribution of topic weight over time</div>
                            <div class="ps-2 pe-2 pt-2">
                                <apexchart width="100%" height="300px" type="bar" :options="topicEvolutionChartOptions"
                                    :series="topicEvolutionSeries"></apexchart>
                            </div>
                        </div>
                    </div>
                    <div class="col-6" v-if="timeSeriesEnabled">
                        <div class="card mt-4 shadow-sm">
                            <div class="card-header">5 most correlated topics over time</div>
                            <apexchart ref="timeChart" width="100%" height="400px" :series="similarEvolutionSeries"
                                :options="similarEvolutionOptions"></apexchart>
                            <div v-for="(localTopic, seriesIndex) in similarEvolutionSeries" :key="localTopic.name"
                                class="topic ps-2 pe-2 pb-1" style="font-size: 80%" @click="goToTopic(localTopic.name)">
                                <span v-if="localTopic.name != topic">
                                    <span :id="`topic-${localTopic.name}`" class="topic-legend"
                                        :style="`background-color: ${similarEvolutionOptions.colors[seriesIndex]}`"></span>
                                    Topic {{ localTopic.name }}:
                                    {{ topicData[parseInt(localTopic.name)].description }}
                                </span>
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
                                    <citations :doc="doc" :id="`${doc.doc_id}`" :philo-db="`${doc.metadata.philo_db}`"></citations>
                                    <span class="badge rounded-pill bg-secondary float-end">{{ (doc.score * 100).toFixed(2) }}</span>
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
            topicEvolutionChartOptions: {
                chart: {
                    id: "topic-evolution",
                    toolbar: {
                        show: false,
                    },
                    events: {
                        click: this.goToYear,
                    },
                },
                dataLabels: { enabled: false },
                xaxis: {
                    categories: [],
                },
                grid: {
                    padding: {
                        left: 0,
                        right: 0,
                        top: 0,
                        bottom: 0,
                    },
                },
                fill: {
                    opacity: 0.9,
                },
                theme: { palette: "palette3" },
                tooltip: {
                    x: {
                        formatter: (year) => {
                            return `${year}-${parseInt(year) +
                                parseInt(
                                    this.$modelConfig.TOPICS_OVER_TIME
                                        .topics_over_time_interval
                                ) -
                                1
                                }`;
                        },
                    },
                },
            },
            topicEvolutionSeries: [
                {
                    name: "Topic Evolution",
                    data: [],
                },
            ],
            similarEvolutionOptions: {
                chart: {
                    id: "similar-evolution",
                    toolbar: {
                        show: false,
                    },
                },
                dataLabels: { enabled: false },
                yaxis: {
                    labels: {
                        formatter: (val) => val.toFixed(3),
                    },
                },
                colors: ["#33b2df", "#546E7A", "#d4526e", "#13d8aa", "#A5978B"],
                stroke: {
                    curve: "smooth",
                    width: 1.5,
                },
                grid: {
                    padding: {
                        left: 0,
                        // right: 0,
                        top: 0,
                        bottom: 0,
                    },
                },
                tooltip: {
                    enabled: false,
                },
                legend: {
                    show: false,
                    formatter: function (seriesName) {
                        return `Topic ${seriesName}`;
                    },
                },
                plotOptions: {},
                fill: {
                    opacity: 0.5,
                },
            },
            similarEvolutionSeries: [{ name: 0, data: [] }],
        };
    },
    computed: {
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
    },
    methods: {
        fetchData() {
            this.loading = true;
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_topic_data/${this.$globalConfig.databaseName}/${this.$route.params.topic}`
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
                        let startIndex = response.data.topic_evolution.labels.indexOf(
                            this.$globalConfig.timeSeriesConfig.startDate
                        );
                        let endIndex = response.data.topic_evolution.labels.length;
                        for (
                            let index = 0;
                            index < response.data.topic_evolution.labels.length;
                            index += 1
                        ) {
                            if (
                                response.data.topic_evolution.labels[index] >
                                this.$globalConfig.timeSeriesConfig.endDate
                            ) {
                                endIndex = index + 1;
                                break;
                            }
                        }
                        this.year = `${response.data.topic_evolution.labels[startIndex]
                            }-${response.data.topic_evolution.labels[endIndex - 1]}`;
                        this.buildTopicEvolution(
                            response.data.topic_evolution,
                            startIndex,
                            endIndex
                        );

                        this.similarEvolutionSeries = [
                            ...response.data.similar_topics
                                .slice(0, 5)
                                .map((topic) => ({
                                    data: topic.topic_evolution.data.slice(
                                        startIndex,
                                        endIndex
                                    ),
                                    name: topic.topic.toString(),
                                    type: "line",
                                })),
                            {
                                name: this.topic,
                                data: response.data.topic_evolution.data.slice(
                                    startIndex,
                                    endIndex
                                ),
                                type: "area",
                            },
                        ];
                        this.similarEvolutionOptions = {
                            ...this.similarEvolutionOptions,
                            ...{
                                xaxis: {
                                    categories: response.data.similar_topics[0].topic_evolution.labels.slice(
                                        startIndex,
                                        endIndex
                                    ),
                                },
                                fill: {
                                    opacity: [
                                        ...response.data.similar_topics,
                                        this.topic,
                                    ]
                                        .slice(startIndex, endIndex)
                                        .map((topic) => {
                                            if (
                                                topic.topic !=
                                                this.$route.params.topic
                                            ) {
                                                return 1;
                                            } else {
                                                return 0.1;
                                            }
                                        }),
                                },
                                colors: [
                                    "#2E93fA",
                                    "#66DA26",
                                    "#546E7A",
                                    "#E91E63",
                                    "#FF9800",
                                    "rgba(156, 60, 60, 0.15)",
                                ],
                            },
                        };
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
            this.topicEvolutionSeries[0].data = this.formatTopicEvolution(
                topicEvolution.data
            );

            this.topicEvolutionChartOptions = {
                ...this.topicEvolutionChartOptions,
                ...{
                    xaxis: {
                        categories: topicEvolution.labels,
                    },
                },
            };
        },
        goToWord(word) {
            this.$router.push(`/word/${word}`);
        },
        goToYear(event) {
            let seriesIndex = parseInt(event.target.getAttribute("j"));
            let year = this.topicEvolutionChartOptions.xaxis.categories[
                seriesIndex
            ];
            this.yearLoading = true;
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_docs_in_topic_by_year/${this.$globalConfig.databaseName}/${this.$route.params.topic}/${year}`
                )
                .then((response) => {
                    this.documents = response.data;
                    this.year = year;
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
