<template>
    <div class="container-fluid">
        <div class="card shadow-sm">
            <div class="card-body">
                <h5 class="card-title">{{ totalFields }} distinct {{fieldName}}s in corpus</h5>
                <div class="card-text" style="font-size: 90%">
                    <div class="row">
                        <div
                            class="col-6"
                            v-for="(halfGroup, halfIndex) in alphaFields"
                            :key="halfIndex"
                        >
                            <b-card
                                no-body
                                :header="group.firstLetter"
                                v-for="(group, index) in halfGroup"
                                :key="index"
                                class="mb-4 shadow-sm"
                            >
                                <b-list-group flush>
                                    <b-list-group-item
                                        class="list-group-item"
                                        style="padding: .5rem 1rem"
                                        v-for="(value, valueIndex) in group.fields"
                                        :key="valueIndex"
                                    >
                                        <router-link
                                            :to="`/${fieldName}/${value}`"
                                            v-if="fieldName == 'word'"
                                        >{{ value }}</router-link>
                                        <router-link
                                            :to="`/metadata/${fieldName}/${value}`"
                                            v-if="fieldName != 'word'"
                                        >{{ value }}</router-link>
                                    </b-list-group-item>
                                </b-list-group>
                            </b-card>
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
            fieldValues: []
        };
    },
    computed: {
        totalFields: function() {
            return this.fieldValues.length;
        },
        alphaFields: function() {
            let sortedFields = [];
            if (this.fieldValues.length) {
                let firstLetter = this.fieldValues[0][0].toUpperCase();
                let currentGroup = [];
                for (let field of this.fieldValues) {
                    let currentFirstLetter = field[0].toUpperCase();
                    if (currentFirstLetter === firstLetter) {
                        currentGroup.push(field);
                    } else {
                        sortedFields.push({
                            firstLetter: firstLetter,
                            fields: currentGroup
                        });
                        firstLetter = currentFirstLetter;
                        currentGroup = [field];
                    }
                }
                let half = Math.floor(sortedFields.length / 2);
                return [
                    sortedFields.slice(0, half),
                    sortedFields.slice(half, sortedFields.length)
                ];
            }
            return [];
        }
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
                    this.fieldValues = response.data.field_values;
                });
        }
    }
};
</script>

