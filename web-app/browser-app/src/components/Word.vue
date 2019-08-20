<template>
    <div class="card shadow-sm">
        <div class="card-header">
            <h5>
                <b>{{ word }}</b> in the corpus
            </h5>
        </div>
        <div class="row mt-4 p-2">
            <div class="col-7">
                <div class="card shadow-sm p-2">
                    <h5 class="mb-2">Word distribution of "{{ word }}" across topics</h5>
                    <canvas id="word-distribution" width="400" max-height="400"></canvas>
                </div>
            </div>
            <div class="col-5">
                <div class="card shadow-sm">
                    <h5 class="p-2">Top {{ documents.length }} documents by relevance</h5>
                    <ul class="list-group">
                        <li
                            v-for="doc in documents"
                            :key="doc[1]"
                            class="list-group-item"
                            style="border-radius: 0px; border-width: 1px 0px; font-size: 90%"
                        >
                            <strong>
                                <router-link :to="`/document/${doc[1]}`">{{ doc[0]["title"] }}</router-link>
                            </strong>
                            <br />
                            {{ doc[0]["author"] }}
                            <br />
                            <i>‡{{ doc[0]["title"] }}</i>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
export default {
    name: "Word",
    data() {
        return {
            word: "",
            documents: []
        };
    },
    mounted() {
        this.fetchData();
    },
    watch: {
        // call again the method if the route changes
        $route: "loadNewData"
    },
    beforeDestroy() {
        this.destroyChart();
    },
    methods: {
        fetchData() {
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_word_data/${this.$route.params.word}?table=${this.$globalConfig.databaseName}`
                )
                .then(response => {
                    this.word = response.data.word;
                    this.documents = response.data.documents;
                    this.build_topic_distribution(
                        response.data.topic_distribution
                    );
                });
        },
        build_topic_distribution(topicDistribution) {
            var ctx = document.getElementById("word-distribution");
            Chart.defaults.global.responsive = true;
            Chart.defaults.global.animation.duration = 400;
            Chart.defaults.global.tooltipCornerRadius = 0;
            // Chart.defaults.global.maintainAspectRatio = false;
            Chart.defaults.bar.scales.xAxes[0].gridLines.display = false;
            var vm = this;
            vm.topicChart = new Chart(ctx, {
                type: "bar",
                data: {
                    labels: topicDistribution.labels,
                    datasets: [
                        {
                            label: "weight",
                            data: topicDistribution.data,
                            backgroundColor: "#55acee"
                        }
                    ]
                },
                options: {
                    legend: {
                        display: false
                    },
                    tooltips: {
                        callbacks: {
                            title: function(tooltipItem) {
                                return "Topic " + tooltipItem[0].xLabel;
                            }
                        }
                    },
                    scales: {
                        yAxes: {
                            scaleLabel: {
                                display: true,
                                labelString: "weight"
                            }
                        },
                        yAxes: {
                            scaleLabel: {
                                display: true,
                                labelString: "topics"
                            }
                        }
                    }
                }
            });
            ctx.addEventListener(
                "click",
                function(e) {
                    let target = vm.topicChart.getElementAtEvent(e);
                    if (typeof target[0] !== "undefined") {
                        let topic = target[0]._view.label;
                        vm.$router.push(`../topic/${topic}`);
                    }
                },
                false
            );
        },
        loadNewData() {
            this.destroyChart();
            this.fetchData();
        },
        destroyChart() {
            this.topicChart.destroy();
        }
    }
};
</script>