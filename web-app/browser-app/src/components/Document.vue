<template>
    <b-container fluid class="mt-4">
        <h5 class="pl-4 pr-4" style="text-align: center">
            <i>{{ metadata.title }}</i>
            ({{ metadata.year }})
            <br />
            {{ metadata.author}}
        </h5>
        <div class="card-body">
            <div class="card-text" style="font-size: 90%">
                <div class="row mb-4">
                    <div class="col-8">
                        <div class="row">
                            <div class="col-12">
                                <b-card header="Topic Distribution">
                                    <canvas
                                        id="topic-distribution"
                                        class="m-1"
                                        style="height: 300px; width:100%"
                                    ></canvas>
                                </b-card>
                            </div>
                            <div class="col-6 mt-4">
                                <b-card
                                    no-body
                                    :header="`Top ${topicSimDocs.length} documents with most similar topic distribution`"
                                >
                                    <b-list-group flush>
                                        <b-list-group-item
                                            v-for="doc in topicSimDocs"
                                            :key="doc.doc_id"
                                            class="list-group-item"
                                            style="border-radius: 0px; border-width: 1px 0px"
                                        >
                                            <router-link :to="`/document/${doc.doc_id}`">
                                                <i>{{ doc.metadata.title }}</i>
                                            </router-link>
                                            ({{ doc.metadata.year }})
                                        </b-list-group-item>
                                    </b-list-group>
                                </b-card>
                            </div>
                            <div class="col-6 mt-4">
                                <b-card
                                    no-body
                                    :header="`Top ${vectorSimDocs.length} documents with most similar topic distribution`"
                                >
                                    <b-list-group flush>
                                        <b-list-group-item
                                            v-for="doc in vectorSimDocs"
                                            :key="doc.doc_id"
                                            class="list-group-item"
                                            style="border-radius: 0px; border-width: 1px 0px"
                                        >
                                            <router-link :to="`/document/${doc.doc_id}`">
                                                <i>{{ doc.metadata.title }}</i>
                                            </router-link>
                                            ({{ doc.metadata.year }})
                                        </b-list-group-item>
                                    </b-list-group>
                                </b-card>
                            </div>
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="row">
                            <div class="col-12">
                                <b-card no-body style="height: 100%" header="Vector Representation">
                                    <div
                                        style="display: flex; height: 100%; justify-content: center; align-items: center;"
                                        class="card-text"
                                    >
                                        <div>
                                            <router-link
                                                v-for="weightedWord in words"
                                                :key="weightedWord[2]"
                                                :to="`/word/${weightedWord[0]}`"
                                                :style="`display:inline-block; padding: 5px; font-size: ${1+weightedWord[1]}rem; color: ${weightedWord[3]}`"
                                            >{{weightedWord[0]}}</router-link>
                                        </div>
                                    </div>
                                </b-card>
                            </div>
                            <div class="col-12 text-justify mt-4">
                                <b-card header="Original Text">{{ text }}</b-card>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </b-container>
</template>
<script>
import topicData from "../../topic_words.json";

export default {
    name: "Document",
    data() {
        return {
            metadata: {},
            text: "",
            words: [],
            vectorSimDocs: [],
            topicSimDocs: []
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
                    `${this.$globalConfig.apiServer}/get_doc_data/${this.$route.params.doc}?table=${this.$globalConfig.databaseName}`
                )
                .then(response => {
                    this.words = response.data.words;
                    this.vectorSimDocs = response.data.vector_sim_docs;
                    this.topicSimDocs = response.data.topic_sim_docs;
                    this.text = response.data.text;
                    this.metadata = response.data.metadata;
                    this.buildTopicDistribution(
                        response.data.topic_distribution
                    );
                });
        },
        buildTopicDistribution(topicDistribution) {
            var ctx = document.getElementById("topic-distribution");
            Chart.defaults.global.responsive = false;
            Chart.defaults.global.animation.duration = 400;
            Chart.defaults.global.tooltipCornerRadius = 0;
            // Chart.defaults.global.maintainAspectRatio = false;
            Chart.defaults.bar.scales.xAxes[0].gridLines.display = false;
            var vm = this;
            vm.myChart = new Chart(ctx, {
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
                    maintainAspectRatio: false,
                    legend: {
                        display: false
                    },
                    tooltips: {
                        callbacks: {
                            title: function() {
                                return "";
                            },
                            label: function(tooltipItem) {
                                return `Topic ${tooltipItem.xLabel}: ${
                                    topicData[tooltipItem.xLabel].description
                                } (${tooltipItem.yLabel.toFixed(3)})`;
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
                    let target = vm.myChart.getElementAtEvent(e);
                    if (typeof target[0] !== "undefined") {
                        console.log(target[0]._view.label);
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
            this.myChart.destroy();
        }
    }
};
</script>

