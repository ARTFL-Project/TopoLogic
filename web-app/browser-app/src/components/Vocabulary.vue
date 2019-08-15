<template>
    <div class="card shadow-sm">
        <div class="card-header">
            <h5>Vocabulary</h5>
        </div>
        <div class="card-body">
            <h5 class="card-title">Number of tokens : {{ vocabularySize }}</h5>
            <div class="card-text" style="font-size: 90%">
                <div class="row">
                    <div class="col" v-for="(vocabulary, index) in splittedVocabulary" :key="index">
                        <ul class="list-group">
                            <li
                                class="list-group-item"
                                style="padding: .5rem 1rem"
                                v-for="indexedWord in vocabulary"
                                :key="indexedWord[0]"
                            >
                                <router-link :to="`word/${indexedWord[1]}`">{{ indexedWord[1] }}</router-link>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
<script>
export default {
    name: "Vocabulary",
    data() {
        return {
            vocabularySize: 0,
            splittedVocabulary: []
        };
    },
    created() {
        this.$http
            .get(
                `${this.$globalConfig.apiServer}/get_vocabulary?db_path=${this.$globalConfig.appPath}`
            )
            .then(response => {
                this.vocabularySize = response.data.vocabulary_size;
                this.splittedVocabulary = response.data.splitted_vocabulary;
            });
    }
};
</script>