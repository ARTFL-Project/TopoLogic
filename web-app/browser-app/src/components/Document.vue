<template>
    <b-container fluid class="mt-4">
        <h5 class="pl-4 pr-4" style="text-align: center">
            <citations :doc="mainDoc" v-if="mainDoc"></citations>
        </h5>
        <div class="card-body">
            <div class="card-text" style="font-size: 90%">
                <div class="row mb-4">
                    <div class="col-8">
                        <div class="row">
                            <div class="col-12">
                                <b-card no-body header="Top 5 Topics">
                                    <div class="pl-2 pr-2">
                                        <b-table
                                            hover
                                            :items="topicDistribution"
                                            :fields="fields"
                                            @row-clicked="goToTopic"
                                        >
                                            <template slot="[name]" slot-scope="data">
                                                <span
                                                    class="frequency-parent"
                                                >Topic {{ data.value }}</span>
                                            </template>
                                            <template slot="[description]" slot-scope="data">
                                                <span class="frequency-parent">{{ data.value }}</span>
                                            </template>
                                            <template slot="[frequency]" slot-scope="data">
                                                <span class="frequency-value pl-2">{{ data.value }}%</span>
                                            </template>
                                        </b-table>
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
                                            <citations :doc="doc"></citations>
                                            <b-badge
                                                variant="secondary"
                                                pill
                                                class="float-right"
                                            >{{(doc.score * 100).toFixed(2)}}%</b-badge>
                                        </b-list-group-item>
                                    </b-list-group>
                                </b-card>
                            </div>
                            <div class="col-6 mt-4">
                                <b-card
                                    no-body
                                    :header="`Top ${vectorSimDocs.length} documents with most similar vocabulary`"
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
                                            >{{(doc.score * 100).toFixed(0)}}%</b-badge>
                                        </b-list-group-item>
                                    </b-list-group>
                                </b-card>
                            </div>
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="row">
                            <div class="col-12">
                                <b-card
                                    no-body
                                    style="height: 100%"
                                    :header="`Vector Representation (top ${words.length} tokens)`"
                                >
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
                                <b-card header="Original Text">
                                    <div v-html="text"></div>
                                </b-card>
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
            topicDistribution: []
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
                    `${this.$globalConfig.apiServer}/get_doc_data/${this.$route.params.doc}?table=${this.$globalConfig.databaseName}`
                )
                .then(response => {
                    this.words = response.data.words;
                    this.vectorSimDocs = response.data.vector_sim_docs;
                    this.topicSimDocs = response.data.topic_sim_docs;
                    this.mainDoc = {
                        metadata: response.data.metadata,
                        doc_id: ""
                    };
                    this.topicDistribution = this.buildTopicDistribution(
                        response.data.topic_distribution
                    );
                    this.$http
                        .get(
                            `${this.$globalConfig.philoLogicUrl}/reports/navigation.py?report=navigation&philo_id=${response.data.metadata.philo_id}`
                        )
                        .then(philoResponse => {
                            this.text = philoResponse.data.text;
                        });
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
                if (count == 5) {
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
/deep/ .philologic-fragment a {
    display: none;
}
/deep/ s {
    text-decoration-line: none;
}
/deep/ .xml-pb {
    display: block;
    text-align: center;
    margin: 10px;
}
/deep/ .xml-pb::before {
    content: "-" attr(n) "-";
    white-space: pre;
}
/deep/ p {
    margin-bottom: 0.5rem;
}
/deep/ .highlight {
    background-color: red;
    color: #fff;
}
/* Styling for theater */
/deep/ .xml-castitem::after {
    content: "\A";
    white-space: pre;
}
/deep/ .xml-castlist > .xml-castitem:first-of-type::before {
    content: "\A";
    white-space: pre;
}
/deep/ .xml-castgroup::before {
    content: "\A";
    white-space: pre;
}
b.headword {
    font-weight: 700 !important;
    font-size: 130%;
    display: block;
    margin-top: 20px;
}
/deep/ #bibliographic-results b.headword {
    font-weight: 400 !important;
    font-size: 100%;
    display: inline;
}
/deep/ .xml-lb {
    display: block;
}
/deep/ .xml-sp .xml-lb:first-of-type {
    content: "";
    white-space: normal;
}
/deep/ .xml-lb[type="hyphenInWord"] {
    display: inline;
}
#book-page .xml-sp {
    display: block;
}
/deep/ .xml-sp::before {
    content: "\A";
    white-space: pre;
}
/deep/ .xml-stage + .xml-sp:nth-of-type(n + 2)::before {
    content: "";
}
/deep/ .xml-fw,
/deep/ .xml-join {
    display: none;
}
/deep/ .xml-speaker + .xml-stage::before {
    content: "";
    white-space: normal;
}
/deep/ .xml-stage {
    font-style: italic;
}
/deep/ .xml-stage::after {
    content: "\A";
    white-space: pre;
}
/deep/ div1 div2::before {
    content: "\A";
    white-space: pre;
}
/deep/ .xml-speaker {
    font-weight: 700;
}
/deep/ .xml-pb {
    display: block;
    text-align: center;
    margin: 10px;
}
/deep/ .xml-pb::before {
    content: "-" attr(n) "-";
    white-space: pre;
}
/deep/ .xml-lg {
    display: block;
}
/deep/ .xml-lg::after {
    content: "\A";
    white-space: pre;
}
/deep/ .xml-lg:first-of-type::before {
    content: "\A";
    white-space: pre;
}
/deep/ .xml-castList,
/deep/ .xml-front,
/deep/ .xml-castItem,
/deep/ .xml-docTitle,
/deep/ .xml-docImprint,
/deep/ .xml-performance,
/deep/ .xml-docAuthor,
/deep/ .xml-docDate,
/deep/ .xml-premiere,
/deep/ .xml-casting,
/deep/ .xml-recette,
/deep/ .xml-nombre {
    display: block;
}
/deep/ .xml-docTitle {
    font-style: italic;
    font-weight: bold;
}
/deep/ .xml-docTitle,
/deep/ .xml-docAuthor,
/deep/ .xml-docDate {
    text-align: center;
}
/deep/ .xml-docTitle span[type="main"] {
    font-size: 150%;
    display: block;
}
/deep/ .xml-docTitle span[type="sub"] {
    font-size: 120%;
    display: block;
}
/deep/ .xml-performance,
/deep/ .xml-docImprint {
    margin-top: 10px;
}
/deep/ .xml-set {
    display: block;
    font-style: italic;
    margin-top: 10px;
}
/*Dictionary formatting*/
body {
    counter-reset: section;
    /* Set the section counter to 0 */
}
/deep/ .xml-prononciation::before {
    content: "(";
}
/deep/ .xml-prononciation::after {
    content: ")\A";
}
/deep/ .xml-nature {
    font-style: italic;
}
/deep/ .xml-indent,
/deep/ .xml-variante {
    display: block;
}
/deep/ .xml-variante {
    padding-top: 10px;
    padding-bottom: 10px;
    text-indent: -1.3em;
    padding-left: 1.3em;
}
/deep/ .xml-variante::before {
    counter-increment: section;
    content: counter(section) ")\00a0";
    font-weight: 700;
}
/deep/ :not(.xml-rubrique) + .xml-indent {
    padding-top: 10px;
}
/deep/ .xml-indent {
    padding-left: 1.3em;
}
/deep/ .xml-cit {
    padding-left: 2.3em;
    display: block;
    text-indent: -1.3em;
}
/deep/ .xml-indent > .xml-cit {
    padding-left: 1em;
}
/deep/ .xml-cit::before {
    content: "\2012\00a0\00ab\00a0";
}
/deep/ .xml-cit::after {
    content: "\00a0\00bb\00a0("attr(aut) "\00a0"attr(ref) ")";
    font-variant: small-caps;
}
/deep/ .xml-rubrique {
    display: block;
    margin-top: 20px;
}
/deep/ .xml-rubrique::before {
    content: attr(nom);
    font-variant: small-caps;
    font-weight: 700;
}
/deep/ .xml-corps + .xml-rubrique {
    margin-top: 10px;
}
/*Methodique styling*/
/deep/ div[type="article"] .headword {
    display: inline-block;
    margin-bottom: 10px;
}
/deep/ .headword + p {
    display: inline;
}
/deep/ .headword + p + p {
    margin-top: 10px;
}
/deep/ .note {
    display: none;
}
/deep/ div[type="notes"] .xml-note {
    margin: 15px 0px;
    display: block;
}
/deep/ .xml-note::before {
    content: "note\00a0"attr(n) "\00a0:\00a0";
    font-weight: 700;
}
/*Page images*/
/deep/ .xml-pb-image {
    display: block;
    text-align: center;
    margin: 10px;
}
/deep/ .page-image-link {
    margin-top: 10px;
    /*display: block;*/
    text-align: center;
}
/*Inline images*/
/deep/ .inline-img {
    max-width: 40%;
    float: right;
    height: auto;
    padding-left: 15px;
    padding-top: 15px;
}
/deep/ .inline-img:hover {
    cursor: pointer;
}
/deep/ .link-back {
    margin-left: 10px;
    line-height: initial;
}
/deep/ .xml-add {
    color: #ef4500;
}
/deep/ .xml-seg {
    display: block;
}
/*Table display*/
/deep/ b.headword[rend="center"] {
    margin-bottom: 30px;
    text-align: center;
}
/deep/ .xml-table {
    display: table;
    position: relative;
    text-align: center;
    border-collapse: collapse;
}
/deep/ .xml-table .xml-pb-image {
    position: absolute;
    width: 100%;
    margin-top: 15px;
}
/deep/ .xml-row {
    display: table-row;
    font-weight: 700;
    text-align: left;
    min-height: 50px;
    font-variant: small-caps;
    padding-top: 10px;
    padding-bottom: 10px;
    padding-right: 20px;
    border-bottom: #ddd 1px solid;
}
/deep/ .xml-row ~ .xml-row {
    font-weight: inherit;
    text-align: justify;
    font-variant: inherit;
}
/deep/ .xml-pb-image + .xml-row {
    padding-top: 50px;
    padding-bottom: 10px;
    border-top-width: 0px;
}
/deep/ .xml-cell {
    display: table-cell;
    padding-top: inherit; /*inherit padding when image is above */
    padding-bottom: inherit;
}
</style>
