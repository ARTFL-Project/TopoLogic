<template>
    <div class="container-fluid">
        <div class="card shadow-sm">
            <div class="card-header">
                <h5>
                    Corpus Statistics: {{ config.corpusSize }} documents with
                    <router-link to="/vocabulary">{{ config.vocabularySize }} unique tokens</router-link>
                </h5>
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
                                >The top {{ config.maxTf * 100 }}% and bottom {{ config.minTf*100 }}% of tokens were filtered out.</li>
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
                `${this.$globalConfig.apiServer}/get_config?table=${this.$globalConfig.databaseName}`
            )
            .then(response => {
                this.config = response.data;
            });
    }
};
</script>

