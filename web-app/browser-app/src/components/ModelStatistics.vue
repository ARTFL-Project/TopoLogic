<template>
    <div class="container-fluid">
        <div class="card shadow-sm">
            <div class="card-header">
                Corpus Statistics: {{ config.corpusSize }} documents with
                <router-link to="/view/word">{{ config.vocabularySize }} unique tokens</router-link>
            </div>
            <div class="card-text p-4">
                <div class="row">
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
    </div>
</template>
<script>
export default {
    name: "ModelStatistics",
    data() {
        return {
            config: {}
        };
    },
    created() {
        this.$http
            .get(
                `${this.$globalConfig.apiServer}/${this.$globalConfig.databaseName}/get_config`
            )
            .then(response => {
                this.config = response.data;
            });
    }
};
</script>

