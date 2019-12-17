<template>
    <div class="container-fluid">
        <div class="card shadow-sm">
            <div class="card-header">
                <a id="show-stats" v-if="!showStats" @click="toggleStatistics">Show</a>
                Corpus Statistics
                <span v-if="showStats">
                    :
                    {{ config.corpus_size }} documents with
                    <router-link to="/view/word">{{ config.vocabularySize }} unique tokens</router-link>
                </span>
            </div>
            <div class="row p-4" v-if="showStats">
                <div class="col-6">
                    <div class="card shadow-sm p-4">
                        <h6>Vectorization parameters:</h6>
                        <ul>
                            <li
                                style="padding: 5px"
                            >Corpus using {{ config.vectorization }} weighting.</li>
                            <li style="padding: 5px">Tokens include unigrams and bigrams</li>
                            <li
                                style="padding: 5px"
                            >Tokens occurring in more than {{ 100 - config.maxTf * 100 }}% and less than {{ config.minTf*100 }}% of documents were filtered out.</li>
                        </ul>
                    </div>
                </div>
                <div class="col-6">
                    <div class="card shadow-sm p-4">
                        <h6 class="mt-4">Topic Modeling parameters:</h6>
                        <ul>
                            <li
                                style="padding: 5px"
                            >The {{ config.method }} algorithm was used to generate the topic model.</li>
                            <li
                                style="padding: 5px"
                            >The topic model contains {{config.topics}} topics</li>
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
