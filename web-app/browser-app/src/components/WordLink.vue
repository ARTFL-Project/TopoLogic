<template>
    <b-popover :target="`${target}`" triggers="click blur" placement="top">
        <template v-slot:title>
            <span style="font-variant: small-caps;">{{ word }}</span>
        </template>
        <b-list-group flush>
            <b-list-group-item>
                <router-link :to="`/word/${word}`">Explore usage in corpus</router-link>
            </b-list-group-item>
            <b-list-group-item>
                <a :href="link" target="_blank" v-if="metadata">See all occurrences in document</a>
                <a
                    :href="`${philoUrl}/query?report=concordance&q=${word}.?`"
                    target="_blank"
                    v-else
                >See all occurrences</a>
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
            philoUrl: this.$globalConfig.philoLogicUrl
        };
    },
    computed: {
        link: function() {
            let philoType = `philo_${this.metadata.philo_type}_id`;
            let objectId = this.metadata[philoType];
            return `${this.philoUrl}/query?report=concordance&${philoType}=${objectId}&q=${this.word}.?`;
        }
    }
};
</script>