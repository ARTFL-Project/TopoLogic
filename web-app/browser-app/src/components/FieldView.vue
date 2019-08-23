<template>
    <div class="container-fluid">
        <div class="card shadow-sm">
            <div class="card-body">
                <h5
                    class="card-title"
                >Number of distinct {{fieldName}}s in corpus : {{ splitted_fields.length }}</h5>
                <div class="card-text" style="font-size: 90%">
                    <div class="row">
                        <div class="col" v-for="(values, index) in splitted_fields" :key="index">
                            <ul class="list-group">
                                <li
                                    class="list-group-item"
                                    style="padding: .5rem 1rem"
                                    v-for="value in values"
                                    :key="value"
                                >
                                    <router-link
                                        :to="`/${fieldName}/${value}`"
                                        v-if="fieldName == 'word'"
                                    >{{ value }}</router-link>
                                    <router-link
                                        :to="`/metadata/${fieldName}/${value}`"
                                        v-if="fieldName != 'word'"
                                    >{{ value }}</router-link>
                                </li>
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
    name: "FieldView",
    data() {
        return {
            fieldName: this.$route.params.fieldName,
            splitted_fields: {}
        };
    },
    created() {
        this.fetchData();
    },
    watch: {
        // call again the method if the route changes
        $route: "fetchData"
    },
    methods: {
        fetchData() {
            this.fieldName = this.$route.params.fieldName;
            this.splitted_fields = [];
            this.$http
                .get(
                    `${this.$globalConfig.apiServer}/get_all_field_values?table=${this.$globalConfig.databaseName}&field=${this.$route.params.fieldName}`
                )
                .then(response => {
                    this.splitted_fields = response.data.splitted_fields;
                });
        }
    }
};
</script>

