<template>
    <b-container fluid class="mt-4">
        <div class="card shadow-sm">
            <div class="card shadow-sm p-2">
                <h5 class="mb-2">Distribution of {{fieldName}} "{{ fieldValue }}" across topics</h5>
                <canvas id="field-distribution" width="400" max-height="400"></canvas>
            </div>
        </div>
    </b-container>
</template>
<script>
export default {
    name: "FieldDistribution",
    data() {
        return {
            fieldName: this.$route.params.fieldName,
            fieldValue: this.$route.params.fieldValue
        };
    },
    mounted() {
        this.fetchData();
    },
    watch: {
        // call again the method if the route changes
        $route: "fetchData"
    },
    beforeDestroy() {
        this.destroyChart();
    },
    methods: {
        fetchData() {
            console.log(this.$route.params.fieldValue);
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_field_distribution/${this.$route.params.fieldName}?table=${this.$globalConfig.databaseName}&value=${this.$route.params.fieldValue}`
                )
                .then(response => {
                    this.build_topic_distribution(
                        response.data.topic_distribution,
                        response.data.coeff
                    );
                });
        },
        build_topic_distribution(topicDistribution, coeff) {
            var ctx = document.getElementById("field-distribution");
            Chart.defaults.global.responsive = true;
            Chart.defaults.global.animation.duration = 400;
            Chart.defaults.global.tooltipCornerRadius = 0;
            // Chart.defaults.global.maintainAspectRatio = false;
            Chart.defaults.bar.scales.xAxes[0].gridLines.display = false;
            var vm = this;
            let topicData = [];
            for (let weight of topicDistribution.data) {
                topicData.push(weight * coeff);
            }
            vm.topicChart = new Chart(ctx, {
                type: "bar",
                data: {
                    labels: topicDistribution.labels,
                    datasets: [
                        {
                            label: "weight",
                            data: topicData,
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
                        vm.$router.push(`/topic/${topic}`);
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