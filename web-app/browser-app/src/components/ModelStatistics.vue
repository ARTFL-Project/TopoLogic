<template>
    <div class="container-fluid">
        <div class="card shadow-sm">
            <div class="card-header model-config-toggle" role="button" tabindex="0" :aria-expanded="showStats"
                @click="toggleStatistics" @keydown.enter="toggleStatistics" @keydown.space.prevent="toggleStatistics">
                <span class="chevron" :class="{ open: showStats }" aria-hidden="true">&rsaquo;</span>
                <span class="fw-bold">Model configuration</span>
                <span v-if="showStats">
                    :
                    {{ config.corpus_size }} documents with
                    <router-link to="/view/word" @click.stop>{{ config.vocabularySize }} unique tokens</router-link>
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
            this.showStats = !this.showStats;
        }
    }
};
</script>
<style scoped>
/* The whole header is the control: a bare "Show" link was not recognizable as
   one, so the pane read as permanently empty. */
.model-config-toggle {
    cursor: pointer;
    user-select: none;
}

.model-config-toggle:hover {
    background-color: rgba(0, 0, 0, 0.05);
}

.model-config-toggle:focus-visible {
    outline: 2px solid #0d6efd;
    outline-offset: -2px;
}

.chevron {
    display: inline-block;
    font-size: 1.2rem;
    line-height: 1;
    transition: transform 0.15s ease-in-out;
    margin-right: 0.35rem;
}

.chevron.open {
    transform: rotate(90deg);
}
</style>
