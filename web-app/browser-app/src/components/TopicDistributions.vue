<template>
    <b-container fluid class="mt-4">
        <b-card no-body class="shadow-sm">
            <div class="card-body">
                <h5 class="card-title">Each bar represents a topic. Click one to get more details</h5>
                <div class="card-text">
                    <canvas
                        id="topic-weights"
                        :style="`height: ${topicData.length * 32}px !important`"
                    ></canvas>
                </div>
            </div>
        </b-card>
    </b-container>
</template>

<script>
import topics from "../../topic_words.json";
import Chart from "chart.js/dist/Chart.js";

export default {
    name: "TopicDistributions",
    data() {
        return {
            topicData: topics
        };
    },
    beforeDestroy() {
        this.topicChart.destroy();
    },
    mounted() {
        var ctx = document.getElementById("topic-weights");
        var labels = [];
        var weights = [];
        var descriptions = [];
        for (var i = 0; i < this.topicData.length; i += 1) {
            labels.push("Topic " + this.topicData[i].name);
            weights.push(this.topicData[i].frequency);
            descriptions.push(this.topicData[i].description);
        }
        Chart.defaults.global.responsive = true;
        Chart.defaults.global.animation.duration = 400;
        Chart.defaults.global.tooltipCornerRadius = 0;
        Chart.defaults.bar.scales.xAxes[0].gridLines.display = false;
        Chart.defaults.global.tooltips.enabled = false;
        Chart.defaults.global.defaultFontSize = "16";
        var vm = this;
        vm.topicChart = new Chart(ctx, {
            type: "horizontalBar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "topics",
                        data: weights,
                        backgroundColor: "rgba(85,172,238, .4)",
                        borderWidth: 25
                    }
                ]
            },
            options: {
                maintainAspectRatio: false,
                scales: {
                    yAxes: [
                        {
                            id: "topics",
                            // type: 'category',
                            // display: false,
                            categoryPercentage: 1.0,
                            barPercentage: 1.0,
                            barThickness: 25,
                            gridLines: {
                                display: false,
                                offsetGridLines: false
                            }
                            // stacked: true
                        }
                    ],
                    xAxes: [
                        {
                            // stacked: true,
                            display: false
                        }
                    ]
                },
                legend: {
                    display: false
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
                        const meta = chartInstance.controller.getDatasetMeta(0);

                        Chart.helpers.each(
                            meta.data.forEach((bar, index) => {
                                const label = descriptions[index];
                                const labelPositionX = 90;
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
        // ctx.style.height = labels.length * 140
        // ctx.style.backgroundColor = 'rgba(85,172,238, .2)';
        ctx.addEventListener(
            "click",
            function(e) {
                let target = vm.topicChart.getElementAtEvent(e);
                if (typeof target[0] !== "undefined") {
                    let topic = target[0]._view.label.replace("Topic ", "");
                    vm.$router.push(`/topic/${topic}`);
                }
            },
            false
        );
    }
};
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>
