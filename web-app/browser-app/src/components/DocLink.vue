<template>
    <b-popover :target="`${target}`" triggers="click blur" placement="top">
        <template v-slot:title>
            <span style="font-variant: small-caps;">Choose between:</span>
        </template>
        <b-list-group flush>
            <b-list-group-item>
                <router-link :to="`${topoLink}`">Explore distribution in corpus</router-link>
            </b-list-group-item>
            <b-list-group-item>
                <a
                    :href="philoLink"
                    target="_blank"
                    v-if="word"
                >Explore word usage in document in PhiloLogic</a>
                <a :href="philoLink" target="_blank" v-else>Read document in PhiloLogic</a>
            </b-list-group-item>
        </b-list-group>
    </b-popover>
</template>
<script>
export default {
    name: "DocLink",
    props: ["target", "metadata", "doc", "word"],
    data() {
        return {
            philoUrl: this.$globalConfig.philoLogicUrl
        };
    },
    computed: {
        philoLink: function() {
            let philoType = `philo_${this.metadata.philo_type}_id`;
            if (typeof word == "undefined") {
                return `${this.philoUrl}/query?report=concordance&q=${this.word}&${philoType}=${this.metadata[philoType]}`;
            } else if (this.metadata.philo_type == "doc") {
                return `${this.philoUrl}/navigate/${this.metadata[philoType]}/table-of-contents/`;
            } else {
                let objectId = this.metadata[philoType].split(" ").join("/");
                return `${this.philoUrl}/navigate/${objectId}/`;
            }
        },
        topoLink: function() {
            let philoType = `philo_${this.metadata.philo_type}_id`;
            let objectId = this.metadata[philoType].split(" ").join("/");
            return `/document/${objectId}/`;
        }
    }
};
</script>