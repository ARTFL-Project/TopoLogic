<template>
    <div class="container-fluid mt-4">
        <h5 class="ps-4 pe-4" style="text-align: center">
            <citations
                :doc="mainDoc"
                :philo-db="`${mainDoc.metadata.philo_db}`"
                v-if="mainDoc"
            ></citations>
        </h5>
        <doc-tabs v-if="mainDoc"></doc-tabs>

        <div class="row mb-4 mt-4">
            <div class="col-9">
                <div class="card">
                    <div class="card-header">Top 10 Topics</div>
                    <div class="ps-2 pe-2">
                        <sortable-table
                            :items="topicDistribution"
                            :fields="fields"
                            @row-clicked="goToTopic"
                        >
                            <template v-slot:cell(name)="data">
                                <span class="frequency-parent">Topic {{ data.value }}</span>
                            </template>
                            <template v-slot:cell(description)="data">
                                <span class="frequency-parent">{{ data.value }}</span>
                            </template>
                            <template v-slot:cell(frequency)="data">
                                <span class="frequency-value ps-2">{{ data.value }}%</span>
                            </template>
                        </sortable-table>
                    </div>
                </div>
            </div>
            <div class="col-3">
                <div class="card" style="height: 100%">
                    <div class="card-header">Vector Representation (up to 50 tokens shown)</div>
                    <div
                        style="
                            display: flex;
                            height: 100%;
                            justify-content: center;
                            align-items: center;
                        "
                        class="card-text"
                    >
                        <div>
                            <span
                                v-for="weightedWord in words"
                                :key="weightedWord[2]"
                            >
                                <a
                                    :id="`${weightedWord[2]}`"
                                    :style="`display:inline-block; padding: 5px; cursor: pointer; font-size: ${
                                        1 + weightedWord[1]
                                    }rem; color: ${weightedWord[3]}`"
                                >{{ weightedWord[0] }}</a>
                                <word-link
                                    :target="weightedWord[2]"
                                    :metadata="mainDoc.metadata"
                                    :word="weightedWord[0]"
                                ></word-link>
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="row mt-2">
            <div class="col-6">
                <div class="card">
                    <div class="card-header">
                        Top {{ topicSimDocs.length }} documents with most similar topic distribution
                    </div>
                    <ul class="list-group list-group-flush">
                        <li
                            v-for="doc in topicSimDocs"
                            :key="doc.doc_id"
                            class="list-group-item"
                            style="border-radius: 0px; border-width: 1px 0px"
                        >
                            <citations
                                :doc="doc"
                                :id="`${doc.doc_id}`"
                                :philo-db="`${doc.metadata.philo_db}`"
                            ></citations>
                            <span class="badge rounded-pill bg-secondary float-end">{{ doc.score.toFixed(3) }}</span>
                        </li>
                    </ul>
                </div>
            </div>
            <div class="col-6">
                <div class="card">
                    <div class="card-header">
                        Top {{ vectorSimDocs.length }} documents with most similar vocabulary
                    </div>
                    <ul class="list-group list-group-flush">
                        <li
                            v-for="doc in vectorSimDocs"
                            :key="doc.doc_id"
                            class="list-group-item"
                            style="border-radius: 0px; border-width: 1px 0px"
                        >
                            <citations
                                :doc="doc"
                                :id="`${doc.doc_id}`"
                                :philo-db="`${doc.metadata.philo_db}`"
                            ></citations>
                            <span class="badge rounded-pill bg-secondary float-end">{{ doc.score.toFixed(3) }}</span>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
import topicData from "../../topic_words.json";
import Citations from "./Citations.vue";
import WordLink from "./WordLink.vue";
import SortableTable from "./SortableTable.vue";
import DocTabs from "./DocTabs.vue";

export default {
    name: "Document",
    components: {
        Citations,
        WordLink,
        SortableTable,
        DocTabs,
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
                    sortable: false,
                },
            ],
            vectorSimDocs: [],
            topicSimDocs: [],
            topicDistribution: [],
            philoUrl: this.$globalConfig.philoLogicUrl,
        };
    },
    mounted() {
        this.fetchData();
    },
    watch: {
        // call again the method if the route changes
        $route: "loadNewData",
    },
    methods: {
        fetchData() {
            let philo_id = this.$route.params.doc.split("/").join(" ");
            this.text = "";
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_doc_data/${this.$globalConfig.databaseName}/${this.$route.params.philoDb}?philo_id=${philo_id}`
                )
                .then((response) => {
                    this.words = response.data.words;
                    this.vectorSimDocs = response.data.vector_sim_docs;
                    this.topicSimDocs = response.data.topic_sim_docs;
                    this.mainDoc = {
                        metadata: response.data.metadata,
                        doc_id: "",
                        philo_id: response.data.metadata.philo_id,
                        philo_type: response.data.metadata.philo_type,
                    };
                    this.topicDistribution = this.buildTopicDistribution(
                        response.data.topic_distribution
                    );
                });
        },
        buildTopicDistribution(topicDistribution) {
            let total = topicDistribution.data.reduce((a, b) => a + b, 0);
            let data = topicDistribution.data.map((x) => (x / total) * 100);
            let modData = [];
            let modLabels = [];
            for (let label = 0; data.length > label; label += 1) {
                modData.push(data[label].toFixed(2));
                modLabels.push(label);
            }
            let zippedData = modLabels.map((e, i) => [e, modData[i]]);
            zippedData.sort(function (a, b) {
                return b[1] - a[1];
            });
            let sortedDistribution = [];
            let count = 0;
            for (let topic of zippedData) {
                sortedDistribution.push({
                    name: topic[0],
                    frequency: topic[1],
                    description: topicData[topic[0]].label || topicData[topic[0]].description,
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
        },
    },
};
</script>
<style scoped>
.popover {
    box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15) !important;
}
:deep(.popover-body) {
    padding: 0;
}
</style>
