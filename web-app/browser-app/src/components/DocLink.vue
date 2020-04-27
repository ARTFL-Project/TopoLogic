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
                <a :href="philoLink" target="_blank">Read document in PhiloLogic</a>
            </b-list-group-item>
        </b-list-group>
    </b-popover>
</template>
<script>
export default {
    name: "DocLink",
    props: ["target", "metadata", "doc"],
    data() {
        return {
            philoUrl: this.$globalConfig.philoLogicUrl
        };
    },
    computed: {
        philoLink: function() {
            let philoType = `philo_${this.metadata.philo_type}_id`;
            if (this.metadata.philo_type == "doc") {
                return `${this.philoUrl}/navigate/${this.metadata[philoType]}/table-of-contents/`;
            }
            let objectId = this.metadata[philoType].split(" ").join("/");
            return `${this.philoUrl}/navigate/${objectId}/`;
        },
        topoLink: function() {
            let philoType = `philo_${this.metadata.philo_type}_id`;
            let objectId = this.metadata[philoType].split(" ").join("/");
            return `/document/${objectId}/`;
        }
    }
};
</script>