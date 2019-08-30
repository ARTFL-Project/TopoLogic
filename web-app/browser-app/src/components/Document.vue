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
                                <b-card no-body header="Topic Distribution">
                                    <div class="pl-2 pr-2">
                                        <apexchart
                                            height="300px"
                                            width="100%"
                                            type="bar"
                                            :options="options"
                                            :series="series"
                                        ></apexchart>
                                    </div>
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
            topicSimDocs: [],
            options: {
                chart: {
                    id: "topic-distribution",
                    toolbar: {
                        show: false
                    },
                    events: {
                        click: this.goToTopic
                    }
                },
                xaxis: {
                    categories: []
                },
                yaxis: {
                    labels: {
                        formatter: val => val.toFixed(2)
                    }
                },
                grid: {
                    padding: {
                        left: 0,
                        right: 0,
                        top: 0,
                        bottom: 0
                    }
                },
                dataLabels: {
                    enabled: false
                },
                tooltip: {
                    x: {
                        formatter: val =>
                            `Topic ${val}: ${topicData[val].description}`
                    },
                    y: {
                        formatter: val => val.toFixed(4)
                    }
                }
            },
            series: [
                {
                    name: "",
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
            this.series[0].data = topicDistribution.data;
            this.options = {
                ...this.options,
                ...{
                    xaxis: {
                        categories: topicDistribution.labels
                    }
                }
            };
        },
        loadNewData() {
            this.fetchData();
        },
        goToTopic(event) {
            let seriesIndex = parseInt(event.target.getAttribute("j"));
            this.$router.push(
                `/topic/${this.options.xaxis.categories[seriesIndex]}`
            );
        }
    }
};
</script>

