<template>
    <div class="container-fluid">
        <h5 class="mb-4" style="text-align: center">
            Representation of topic
            <b>{{topic}}</b>
            across corpus (overall frequency of {{frequency}}%)
        </h5>
        <div class="card-text" style="font-size: 90%">
            <div class="row">
                <div class="col-4">
                    <b-card no-body class="shadow-sm" header="Top 20 Tokens">
                        <div class="p-4">
                            <apexchart
                                type="bar"
                                height="450px"
                                :options="wordDistributionChartOptions"
                                :series="wordDistributionSeries"
                            />
                        </div>
                    </b-card>
                </div>
                <div class="col-8">
                    <b-card no-body class="shadow-sm" header="Topic frequency across time">
                        <div class="p-4">
                            <apexchart
                                width="100%"
                                height="435px"
                                type="line"
                                :options="topicEvolutionChartOptions"
                                :series="topicEvolutionSeries"
                            ></apexchart>
                        </div>
                    </b-card>
                </div>
            </div>
        </div>
        <div class="row">
            <div class="col-12">
                <b-card
                    no-body
                    :header="`Top ${documents.length} documents for this topic`"
                    class="mt-4 shadow-sm"
                >
                    <b-list-group flush>
                        <b-list-group-item
                            v-for="doc in documents"
                            :key="doc[3]"
                            :to="`/document/${doc[3]}`"
                        >
                            <span style="font-style: italic">{{doc[0]}}</span>
                            <br />
                            <span style="color:initial">{{ doc[1] }} ({{doc[2]}})</span>
                            <b-badge
                                variant="primary"
                                pill
                                class="float-right"
                            >{{doc[4].toFixed(3)}}</b-badge>
                        </b-list-group-item>
                    </b-list-group>
                </b-card>
            </div>
        </div>
    </div>
</template>
<script>
export default {
    name: "Topic",
    data() {
        return {
            topicData: {},
            documents: [],
            frequency: 0,
            topic: this.$route.params.topic,
            topicEvolutionChartOptions: {
                chart: {
                    id: "topic-evolution",
                    toolbar: {
                        show: false
                    }
                },
                xaxis: {
                    categories: []
                },
                stroke: {
                    curve: "smooth",
                    width: 2
                },
                grid: {
                    padding: {
                        left: 0,
                        right: 0,
                        top: 0,
                        bottom: 0
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
                        colors: ["#fff"],
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
                        enabled: true
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
            ]
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
                    `${this.$globalConfig.apiServer}/get_topic_data/${this.$route.params.topic}?table=${this.$globalConfig.databaseName}`
                )
                .then(response => {
                    this.documents = response.data.documents;
                    this.frequency = response.data.frequency;
                    this.buildWordDistribution(response.data.word_distribution);
                    this.buildTopicEvolution(response.data.topic_evolution);
                });
        },
        sumArray: function(arr) {
            return arr.reduce(function(a, b) {
                return a + b;
            }, 0);
        },
        formatTopicEvolution(topicEvolution) {
            let arrSum = this.sumArray(topicEvolution);
            let coeff = 1.0 / arrSum;
            let weightedTopicEvolution = [];
            for (let value of topicEvolution) {
                weightedTopicEvolution.push((coeff * value).toFixed(2));
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
        buildTopicEvolution(topicEvolution) {
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
        }
    }
};
</script>

