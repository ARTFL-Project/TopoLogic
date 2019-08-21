<template>
    <div class="container-fluid">
        <div class="card shadow-sm">
            <div class="card-header">
                <h5>Topic {{ }}</h5>
            </div>
            <div class="card-body">
                <div class="card-text" style="font-size: 90%">
                    <div class="row">
                        <div class="col-4">
                            <div class="card shadow-sm p-2">
                                <h6>Most relevant words</h6>
                                <canvas id="relevant-words" style="max-height:400px"></canvas>
                            </div>
                        </div>
                        <div class="col-8">
                            <div class="card shadow-sm p-2">
                                <h6>Topic frequency across time (overall frequency of {{ frequency }}%)</h6>
                                <canvas id="topic-frequency" style="max-height:400px"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-12">
                        <div class="card shadow-sm mt-4 p-2">
                            <h6>Related documents (top {{documents.length}})</h6>
                            <table id="documents" class="display" cellspacing="0">
                                <thead>
                                    <tr>
                                        <th>Title</th>
                                        <th>Author(s)</th>
                                        <th>Date</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="doc in documents" :key="doc[3]">
                                        <td>
                                            <router-link :to="`/document/${doc[3]}`">{{ doc[0] }}</router-link>
                                        </td>
                                        <td>{{ doc[1] }}</td>
                                        <td>{{ doc[2] }}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
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

            Chart.defaults.global.responsive = true;
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

