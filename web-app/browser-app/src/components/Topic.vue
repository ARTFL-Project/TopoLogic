<template>
    <div class="container-fluid">
        <h5 class="mb-4" style="text-align: center">
            Representation of topic
            <b>{{topic}}</b> across corpus
        </h5>
        <div class="card-text" style="font-size: 90%">
            <div class="row">
                <div class="col-4">
                    <b-card class="shadow-sm" header="Top 20 Tokens">
                        <canvas id="relevant-words" style="height:400px; width: 100%"></canvas>
                    </b-card>
                </div>
                <div class="col-8">
                    <b-card
                        class="shadow-sm"
                        :header="`Topic frequency across time (overall frequency of ${frequency}%)`"
                    >
                        <canvas id="topic-frequency" style="height:400px; width: 100%"></canvas>
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
            topic: this.$route.params.topic
        };
    },
    mounted() {
        this.fetchData();
    },
    beforeDestroy() {
        this.destroyChart();
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
        buildWordDistribution(wordDistribution) {
            var ctx = document.getElementById("relevant-words");

            Chart.defaults.global.responsive = false;
            Chart.defaults.global.animation.duration = 400;
            Chart.defaults.global.tooltipCornerRadius = 0;
            Chart.defaults.bar.scales.xAxes[0].gridLines.display = false;
            Chart.defaults.global.defaultFontSize = "14";
            var vm = this;
            vm.wordChart = new Chart(ctx, {
                type: "horizontalBar",
                data: {
                    labels: wordDistribution.labels,
                    datasets: [
                        {
                            label: "weight",
                            data: wordDistribution.data,
                            backgroundColor: "rgba(85,172,238, .6)"
                        }
                    ]
                },
                options: {
                    maintainAspectRatio: false,
                    tooltips: {
                        enabled: false
                    },
                    legend: {
                        display: false
                    },
                    scales: {
                        xAxes: [
                            {
                                display: false,
                                gridLines: {
                                    display: false,
                                    offsetGridLines: false
                                }
                            }
                        ],
                        yAxes: [
                            {
                                display: false,
                                gridLines: {
                                    barThickness: 20,
                                    display: false
                                }
                            }
                        ]
                    },
                    hover: {
                        animationDuration: 0
                    },
                    animation: {
                        duration: 1,
                        onComplete() {
                            const chartInstance = this.chart;
                            const ctx2 = chartInstance.ctx;
                            const dataset = this.data.datasets[0];
                            const meta = chartInstance.controller.getDatasetMeta(
                                0
                            );

                            Chart.helpers.each(
                                meta.data.forEach((bar, index) => {
                                    const label = this.data.labels[index];
                                    const labelPositionX = 10;
                                    const labelWidth =
                                        ctx2.measureText(label).width +
                                        labelPositionX;

                                    ctx2.textBaseline = "middle";
                                    ctx2.textAlign = "left";
                                    ctx2.fillStyle = "#444";
                                    ctx2.fillText(
                                        label,
                                        labelPositionX,
                                        bar._model.y
                                    );
                                })
                            );
                        }
                    }
                }
            });

            ctx.addEventListener(
                "click",
                function(e) {
                    let target = vm.wordChart.getElementAtEvent(e);
                    if (typeof target[0] !== "undefined") {
                        let word = target[0]._view.label;
                        vm.$router.push(`../word/${word}`);
                    }
                },
                false
            );
        },
        buildTopicEvolution(topicEvolution) {
            var ctx2 = document.getElementById("topic-frequency");
            Chart.defaults.global.responsive = true;
            Chart.defaults.global.animation.duration = 400;
            Chart.defaults.global.tooltipCornerRadius = 0;
            // Chart.defaults.global.maintainAspectRatio = false;
            Chart.defaults.bar.scales.xAxes[0].gridLines.display = false;
            this.topicChart = new Chart(ctx2, {
                type: "line",
                data: {
                    labels: topicEvolution.labels,
                    datasets: [
                        {
                            data: topicEvolution.data,
                            borderColor: "#55acee",
                            fill: false,
                            borderWidth: 1,
                            pointRadius: 0,
                            pointTension: 0
                        }
                    ]
                },
                options: {
                    maintainAspectRatio: false,
                    legend: {
                        display: false
                    }
                }
            });
        },
        loadNewData() {
            this.destroyChart();
            this.fetchData();
        },
        destroyChart() {
            this.wordChart.destroy();
            this.topicChart.destroy();
        }
    }
};
</script>

