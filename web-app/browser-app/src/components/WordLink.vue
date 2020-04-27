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
                <a
                    :href="`${philoUrl}/query?report=concordance&philo_doc_id=${objectId}&q=${word}.?`"
                    target="_blank"
                    v-if="objectId"
                >See all occurrences in document</a>
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
    props: ["target", "objectId", "word"],
    data() {
        return {
            philoUrl: this.$globalConfig.philoLogicUrl
        };
    },
    created() {
        console.log(this.target);
    }
};
</script>