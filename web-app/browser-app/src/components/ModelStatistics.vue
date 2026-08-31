<template>
    <div class="container-fluid">
        <div class="card shadow-sm">
            <div class="card-header">
                <a id="show-stats" v-if="!showStats" @click="toggleStatistics">Show</a>
                Model configuration
                <span v-if="showStats">
                    :
                    {{ config.corpus_size }} documents with
                    <router-link to="/view/word">{{ config.vocabularySize }} unique tokens</router-link>
                </span>
            </div>
            <div class="row p-4" v-if="showStats">
                <div class="col-6">
                    <div class="card shadow-sm p-2">
                        <h6>Vectorization parameters:</h6>
                        <ul>
                            <li style="padding: 5px">Corpus using {{ config.vectorization }} weighting.</li>
                            <li style="padding: 5px">{{ ngramDescription }}</li>
                            <li style="padding: 5px">{{ filterDescription }}</li>
                        </ul>
                    </div>
                </div>
                <div class="col-6">
                    <div class="card shadow-sm p-2">
                        <h6 class="mt-4">Topic Modeling parameters:</h6>
                        <ul>
                            <li style="padding: 5px">The {{ config.method }} algorithm was used to generate the topic
                                model.</li>
                            <li style="padding: 5px">The topic model contains {{ config.topics }} topics</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
export default {
    name: "ModelStatistics",
    data() {
        return {
            config: {},
            showStats: false
        };
    },
    created() {
        this.$http
            .get(
                `${this.$globalConfig.apiServer}/get_config/${this.$globalConfig.databaseName}`
            )
            .then(response => {
                this.config = response.data;
            });
    },
    computed: {
        filterDescription() {
            const { minTf, maxTf } = this.config;
            if (minTf === undefined || maxTf === undefined) {
                return "";
            }
            // min_freq/max_freq are a proportion of the corpus when <= 1 and an
            // absolute document count when > 1 (see config.py). The previous
            // text assumed a proportion always, so an absolute floor of 5
            // rendered as "500%".
            const describe = (value) =>
                value <= 1
                    ? `${+(value * 100).toFixed(2)}% of documents`
                    : `${value} documents`;
            return `Tokens occurring in more than ${describe(maxTf)}, or in fewer than ${describe(
                minTf
            )}, were filtered out.`;
        },
        ngramDescription() {
            // Was hardcoded to "unigrams and bigrams" while both shipped
            // configs use ngram = 1.
            const n = this.config.ngram;
            return n > 1
                ? `Tokens include unigrams through ${n}-grams`
                : "Tokens include unigrams";
        }
    },
    methods: {
        toggleStatistics() {
            if (this.showStats) {
                this.showStats = false;
            } else {
                this.showStats = true;
            }
        }
    }
};
</script>
<style scoped>
#show-stats {
    cursor: pointer;
    font-weight: 700;
}
</style>
