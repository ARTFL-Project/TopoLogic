<template>
    <b-container fluid class="mt-4">
        <h5 class="pl-4 pr-4" style="text-align: center">
            <citations :doc="mainDoc" v-if="mainDoc"></citations>
        </h5>

        <b-row class="mb-4 mt-4">
            <b-col cols="9">
                <b-card no-body header="Top 10 Topics">
                    <div class="pl-2 pr-2">
                        <b-table
                            hover
                            :items="topicDistribution"
                            :fields="fields"
                            @row-clicked="goToTopic"
                        >
                            <template slot="[name]" slot-scope="data">
                                <span class="frequency-parent">Topic {{ data.value }}</span>
                            </template>
                            <template slot="[description]" slot-scope="data">
                                <span class="frequency-parent">
                                    {{
                                    data.value
                                    }}
                                </span>
                            </template>
                            <template slot="[frequency]" slot-scope="data">
                                <span class="frequency-value pl-2">{{ data.value }}%</span>
                            </template>
                        </b-table>
                    </div>
                </b-card>
            </b-col>
            <b-col cols="3">
                <b-card
                    no-body
                    style="height: 100%"
                    header="Vector Representation (up to 50 tokens shown)"
                >
                    <div
                        style="display: flex; height: 100%; justify-content: center; align-items: center;"
                        class="card-text"
                    >
                        <div>
                            <span v-for="weightedWord in words" :key="weightedWord[2]">
                                <a
                                    :id="`${weightedWord[2]}`"
                                    :style="
                                    `display:inline-block; padding: 5px; cursor: pointer; font-size: ${1 +
                                        weightedWord[1]}rem; color: ${
                                        weightedWord[3]
                                    }`
                                "
                                >{{ weightedWord[0] }}</a>
                                <b-popover
                                    :target="`${weightedWord[2]}`"
                                    triggers="click blur"
                                    placement="top"
                                >
                                    <template v-slot:title>
                                        <span
                                            style="font-variant: small-caps;"
                                        >{{ weightedWord[0] }}</span>
                                    </template>
                                    <b-list-group flush>
                                        <b-list-group-item>
                                            <router-link
                                                :to="`/word/${weightedWord[0]}`"
                                            >Explore usage in corpus</router-link>
                                        </b-list-group-item>
                                        <b-list-group-item>
                                            <a
                                                :href="`${philoUrl}/query?report=concordance&philo_doc_id=${mainDoc.metadata.philo_doc_id}&q=${weightedWord[0]}`"
                                                target="_blank"
                                            >See all occurrences in document</a>
                                        </b-list-group-item>
                                    </b-list-group>
                                </b-popover>
                            </span>
                        </div>
                    </div>
                </b-card>
            </b-col>
        </b-row>
        <b-row class="mt-2">
            <div class="col-6">
                <b-card
                    no-body
                    :header="
                        `Top ${topicSimDocs.length} documents with most similar topic distribution`
                    "
                >
                    <b-list-group flush>
                        <b-list-group-item
                            v-for="doc in topicSimDocs"
                            :key="doc.doc_id"
                            class="list-group-item"
                            style="border-radius: 0px; border-width: 1px 0px"
                        >
                            <citations :doc="doc"></citations>
                            <b-badge
                                variant="secondary"
                                pill
                                class="float-right"
                            >{{ (doc.score * 100).toFixed(2) }}%</b-badge>
                        </b-list-group-item>
                    </b-list-group>
                </b-card>
            </div>
            <div class="col-6">
                <b-card
                    no-body
                    :header="
                        `Top ${vectorSimDocs.length} documents with most similar vocabulary`
                    "
                >
                    <b-list-group flush>
                        <b-list-group-item
                            v-for="doc in vectorSimDocs"
                            :key="doc.doc_id"
                            class="list-group-item"
                            style="border-radius: 0px; border-width: 1px 0px"
                        >
                            <citations :doc="doc"></citations>
                            <b-badge
                                variant="secondary"
                                pill
                                class="float-right"
                            >{{ (doc.score * 100).toFixed(0) }}%</b-badge>
                        </b-list-group-item>
                    </b-list-group>
                </b-card>
            </div>
        </b-row>
    </b-container>
</template>
<script>
import topicData from "../../topic_words.json";
import Citations from "./Citations";

export default {
    name: "Document",
    components: {
        Citations
    },
    data() {
        return {
            mainDoc: null,
            text: "",
            words: [],
            fields: [
                { key: "name", label: "Topic", sortable: false },
                { key: "description", label: "Top 10 tokens", sortable: false },
                {
                    key: "frequency",
                    label: "Topic weight",
                    sortable: false
                }
            ],
            vectorSimDocs: [],
            topicSimDocs: [],
            topicDistribution: [],
            philoUrl: this.$globalConfig.philoLogicUrl
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
            this.text = "";
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_doc_data/${this.$globalConfig.databaseName}/${this.$route.params.doc}`
                )
                .then(response => {
                    this.words = response.data.words;
                    this.vectorSimDocs = response.data.vector_sim_docs;
                    this.topicSimDocs = response.data.topic_sim_docs;
                    this.mainDoc = {
                        metadata: response.data.metadata,
                        doc_id: "",
                        philo_id: response.data.metadata.philo_id,
                        philo_type: response.data.metadata.philo_type
                    };
                    this.topicDistribution = this.buildTopicDistribution(
                        response.data.topic_distribution
                    );
                });
        },
        buildTopicDistribution(topicDistribution) {
            let total = topicDistribution.data.reduce((a, b) => a + b, 0);
            let data = topicDistribution.data.map(x => (x / total) * 100);
            let modData = [];
            let modLabels = [];
            for (let label = 0; data.length > label; label += 1) {
                modData.push(data[label].toFixed(2));
                modLabels.push(label);
            }
            let zippedData = modLabels.map((e, i) => [e, modData[i]]);
            zippedData.sort(function(a, b) {
                return b[1] - a[1];
            });
            let sortedDistribution = [];
            let count = 0;
            for (let topic of zippedData) {
                sortedDistribution.push({
                    name: topic[0],
                    frequency: topic[1],
                    description: topicData[topic[0]].description
                });
                count++;
                if (count == 10) {
                    break;
                }
            }
            return sortedDistribution;
        },
        loadNewData() {
            this.fetchData();
        },
        goToTopic(topic) {
            this.$router.push(`/topic/${topic.name}`);
        }
    }
};
</script>
<style scoped>
.popover {
    box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15) !important;
}
/deep/ .popover-body {
    padding: 0;
}
</style>
