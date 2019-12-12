<template>
    <div class="container-fluid">
        <h5 class="mb-4" style="text-align: center">
            Representation of topic
            <b>{{ topic }}</b>
            across corpus (overall frequency of {{ frequency }}%)
        </h5>
        <b-row>
            <b-col cols="4">
                <b-card no-body class="shadow-sm" header="Top 50 Tokens">
                    <div class="p-4">
                        <apexchart
                            type="bar"
                            height="1000px"
                            :options="wordDistributionChartOptions"
                            :series="wordDistributionSeries"
                        />
                    </div>
                </b-card>
            </b-col>
            <b-col cols="8">
                <b-row>
                    <b-col cols="12">
                        <b-card no-body class="shadow-sm" header="Topic frequency over time">
                            <div class="p-2">
                                <apexchart
                                    width="100%"
                                    height="300px"
                                    type="bar"
                                    :options="topicEvolutionChartOptions"
                                    :series="topicEvolutionSeries"
                                ></apexchart>
                            </div>
                        </b-card>
                    </b-col>
                    <b-col cols="6">
                        <b-card
                            no-body
                            header="5 most correlated topics over time"
                            class="mt-4 shadow-sm"
                        >
                            <apexchart
                                ref="timeChart"
                                width="100%"
                                height="400px"
                                :series="similarEvolutionSeries"
                                :options="similarEvolutionOptions"
                            ></apexchart>
                            <div
                                v-for="(topic,
                                seriesIndex) in similarEvolutionSeries"
                                :key="topic.name"
                                class="topic pl-2 pr-2 pb-1"
                                style="font-size: 80%"
                                @click="goToTopic(topic.name)"
                            >
                                <span
                                    :id="`topic-${topic.name}`"
                                    class="topic-legend"
                                    :style="
                                        `background-color: ${similarEvolutionOptions.colors[seriesIndex]}`
                                    "
                                ></span>
                                Topic {{ topic.name }}:
                                {{
                                topicData[parseInt(topic.name)].description
                                }}
                            </div>
                        </b-card>
                    </b-col>
                    <b-col cols="6">
                        <b-card
                            no-body
                            :header="
                                `Top ${documents.length} documents for this topic (${year})`
                            "
                            class="mt-4 shadow-sm"
                        >
                            <div
                                class="d-flex justify-content-center position-absolute"
                                style="left: 0; right: 0; top: 4rem; z-index: 1;"
                                v-if="loading"
                            >
                                <b-spinner style="width: 4rem; height: 4rem;" label="Large Spinner"></b-spinner>
                            </div>
                            <b-list-group flush>
                                <b-list-group-item v-for="doc in documents" :key="doc.doc_id">
                                    <citations :doc="doc"></citations>
                                    <b-badge variant="secondary" pill class="float-right">
                                        {{
                                        (doc.score * 100).toFixed(2)
                                        }}%
                                    </b-badge>
                                </b-list-group-item>
                            </b-list-group>
                        </b-card>
                    </b-col>
                </b-row>
            </b-col>
        </b-row>
    </div>
</template>
<script>
import topicData from "../../topic_words.json";
import Citations from "./Citations";

export default {
    name: "Topic",
    components: {
        Citations
    },
    data() {
        return {
            topicData: topicData,
            documents: [],
            similarTopics: [],
            loading: false,
            frequency: 0,
            year: 0,
            topic: this.$route.params.topic,
            topicEvolutionChartOptions: {
                chart: {
                    id: "topic-evolution",
                    toolbar: {
                        show: false
                    },
                    events: {
                        click: this.goToYear
                    }
                },
                xaxis: {
                    categories: []
                },
                grid: {
                    padding: {
                        left: 0,
                        right: 0,
                        top: 0,
                        bottom: 0
                    }
                },
                fill: {
                    opacity: 0.9
                },
                theme: { palette: "palette3" },
                tooltip: {
                    x: {
                        formatter: year => {
                            return `${year}-${parseInt(year) +
                                this.$globalConfig.timeSeriesConfig.interval -
                                1}`;
                        }
                    }
                }
            },
            topicEvolutionSeries: [
                {
                    name: "Topic Evolution",
                    data: []
                }
            ],
            wordDistributionChartOptions: {
                chart: {
                    sparkline: {
                        enabled: true
                    },
                    toolbar: {
                        show: false
                    },
                    events: {
                        click: this.goToWord
                    }
                },
                plotOptions: {
                    bar: {
                        barHeight: "100%",
                        distributed: true,
                        horizontal: true,
                        dataLabels: {
                            position: "bottom"
                        }
                    }
                },
                colors: [
                    "#33b2df",
                    "#546E7A",
                    "#d4526e",
                    "#13d8aa",
                    "#A5978B",
                    "#2b908f",
                    "#f9a3a4",
                    "#90ee7e",
                    "#f48024",
                    "#69d2e7"
                ],
                dataLabels: {
                    enabled: true,
                    textAnchor: "start",
                    style: {
                        colors: ["#000"],
                        fontSize: "14px"
                    },
                    formatter: function(val, opt) {
                        return (
                            opt.w.globals.labels[opt.dataPointIndex] +
                            ":  " +
                            val
                        );
                    },
                    offsetX: 0,
                    dropShadow: {
                        enabled: true,
                        color: "#fff",
                        blur: 0.85
                    }
                },
                stroke: {
                    width: 0.5,
                    colors: ["#fff"]
                },
                xaxis: {
                    categories: []
                },
                grid: {
                    show: false
                }
            },
            wordDistributionSeries: [
                {
                    data: []
                }
            ],
            similarEvolutionOptions: {
                chart: {
                    id: "similar-evolution",
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
                colors: ["#33b2df", "#546E7A", "#d4526e", "#13d8aa", "#A5978B"],
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
                    show: false,
                    formatter: function(seriesName) {
                        return `Topic ${seriesName}`;
                    }
                }
            },
            similarEvolutionSeries: [{ name: 0, data: [] }]
        };
    },
    mounted() {
        this.fetchData();
    },
    watch: {
        // call again the method if the route changes
        $route: "loadNewData"
    },
    methods: {
        fetchData() {
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_topic_data/${this.$globalConfig.databaseName}/${this.$route.params.topic}?interval=${this.$globalConfig.timeSeriesConfig.interval}`
                )
                .then(response => {
                    this.documents = response.data.documents;
                    this.frequency = (response.data.frequency * 100).toFixed(4);
                    this.similarTopics = response.data.similar_topics;
                    this.year = `${response.data.topic_evolution.labels[0]}-${
                        response.data.topic_evolution.labels[
                            response.data.topic_evolution.labels.length - 1
                        ]
                    }`;
                    this.buildWordDistribution(response.data.word_distribution);
                    let startIndex = response.data.topic_evolution.labels.indexOf(
                        this.$globalConfig.timeSeriesConfig.startDate
                    );
                    let endIndex =
                        response.data.topic_evolution.labels.indexOf(
                            this.$globalConfig.timeSeriesConfig.endDate
                        ) + 1;
                    this.buildTopicEvolution(
                        response.data.topic_evolution,
                        startIndex,
                        endIndex
                    );
                    this.similarEvolutionOptions = {
                        ...this.similarEvolutionOptions,
                        ...{
                            xaxis: {
                                categories: response.data.similar_topics[0].topic_evolution.labels.slice(
                                    startIndex,
                                    endIndex
                                )
                            }
                        }
                    };
                    this.similarEvolutionSeries = response.data.similar_topics
                        .slice(0, 5)
                        .map(topic => ({
                            data: topic.topic_evolution.data.slice(
                                startIndex,
                                endIndex
                            ),
                            name: topic.topic.toString()
                        }));
                });
        },
        sumArray: function(arr) {
            return arr.reduce(function(a, b) {
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
        formatWordDistribution(wordDistribution) {
            for (let index = 0; index < wordDistribution.length; index += 1) {
                wordDistribution[index] = wordDistribution[index].toFixed(2);
            }
            return wordDistribution;
        },
        buildWordDistribution(wordDistribution) {
            this.wordDistributionChartOptions = {
                ...this.wordDistributionChartOptions,
                ...{
                    xaxis: {
                        categories: wordDistribution.labels
                    }
                }
            };
            this.wordDistributionSeries[0].data = this.formatWordDistribution(
                wordDistribution.data
            );
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
                        categories: topicEvolution.labels
                    }
                }
            };
        },
        loadNewData() {
            this.fetchData();
        },
        goToWord(event) {
            let seriesIndex = parseInt(event.target.getAttribute("j"));
            this.$router.push(
                `/word/${this.wordDistributionChartOptions.xaxis.categories[seriesIndex]}`
            );
        },
        goToYear(event) {
            let seriesIndex = parseInt(event.target.getAttribute("j"));
            let year = this.topicEvolutionChartOptions.xaxis.categories[
                seriesIndex
            ];
            this.loading = true;
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_docs_in_topic_by_year/${this.$globalConfig.databaseName}/${this.$route.params.topic}/${year}`
                )
                .then(response => {
                    this.documents = response.data;
                    this.year = year;
                    this.loading = false;
                });
        },
        goToTopic(topic) {
            this.$router.push(`/topic/${topic}`);
        }
    }
};
</script>
<style scoped>
/deep/ path[selected="true"] {
    fill: rgba(212, 82, 110, 0.9);
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
</style>
