<template>
    <b-popover :target="`${target}`" triggers="click blur" placement="top">
        <template v-slot:title>
            <span style="font-variant: small-caps">{{ word }}</span>
        </template>
        <b-list-group flush>
            <b-list-group-item>
                <router-link :to="`/word/${word}`">Explore usage in corpus</router-link>
            </b-list-group-item>
            <b-list-group-item class="px-0">
                <a :href="link" target="_blank" v-if="metadata">See all occurrences in document</a>
                <!-- TODO: This would ideally be replaced with a federated search system, maybe ranked relevance -->
                <ul style="padding-inline-start: 1.5em; margin-bottom: 0" v-else>
                    <h6 style="margin-left: -1em">See all occurrences in:</h6>
                    <li v-for="(philoUrl, philoDb) in philoUrls" :key="philoUrl" class="py-1">
                        <a :href="`${philoUrl}/query?report=concordance&q=${word}.?`" target="_blank"> {{ philoDb }}</a>
                    </li>
                </ul>
            </b-list-group-item>
        </b-list-group>
    </b-popover>
</template>
<script>
export default {
    name: "WordLink",
    props: ["target", "metadata", "word"],
    data() {
        return {
            philoUrls: this.$globalConfig.philoLogicUrls,
        };
    },
    computed: {
        link: function () {
            let philoType = `philo_${this.metadata.philo_type}_id`;
            let objectId = this.metadata[philoType];
            return `${this.philoUrls[this.metadata.philo_db]}/query?report=concordance&${philoType}=${objectId}&q=${
                this.word
            }.?`;
        },
    },
};
</script>