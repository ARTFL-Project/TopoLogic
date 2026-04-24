<template>
    <div id="app">
        <nav class="navbar navbar-expand-lg navbar-light bg-light shadow-sm mb-4">
            <div class="container-fluid">
                <router-link class="navbar-brand" to="/">TopoLogic</router-link>
                <button
                    class="navbar-toggler"
                    type="button"
                    data-bs-toggle="collapse"
                    data-bs-target="#nav-collapse"
                    aria-controls="nav-collapse"
                    aria-expanded="false"
                    aria-label="Toggle navigation"
                >
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="nav-collapse">
                    <ul class="navbar-nav me-auto">
                        <li class="nav-item dropdown" id="vocab-list">
                            <a
                                class="nav-link dropdown-toggle"
                                href="#"
                                role="button"
                                data-bs-toggle="dropdown"
                                aria-expanded="false"
                            >Navigate Topics</a>
                            <ul class="dropdown-menu">
                                <li v-for="topic in topicData" :key="topic.name">
                                    <router-link class="dropdown-item" :to="`/topic/${topic.name}`">
                                        Topic {{ topic.name }}: {{ topic.label || topic.description }}
                                    </router-link>
                                </li>
                            </ul>
                        </li>
                        <li class="nav-item">
                            <router-link class="nav-link" to="/view/word">Vocabulary</router-link>
                        </li>
                        <li class="nav-item dropdown" v-if="profiledFields.length">
                            <a
                                class="nav-link dropdown-toggle"
                                href="#"
                                role="button"
                                data-bs-toggle="dropdown"
                                aria-expanded="false"
                            >Metadata Explorer</a>
                            <ul class="dropdown-menu">
                                <li v-for="field in profiledFields" :key="field.field">
                                    <router-link
                                        class="dropdown-item"
                                        :to="`/explorer/${encodeURIComponent(field.field)}`"
                                    >
                                        {{ fieldLabel(field.field) }}
                                        <span class="text-muted small ms-1">({{ field.value_count }})</span>
                                    </router-link>
                                </li>
                            </ul>
                        </li>
                        <li class="nav-item" v-if="timeSeriesEnabled">
                            <router-link class="nav-link" to="/time">Topics across Time</router-link>
                        </li>
                    </ul>
                    <form class="d-flex ms-auto" @submit.stop.prevent="searchVocab()">
                        <div class="input-group input-group-sm">
                            <input
                                class="form-control"
                                type="text"
                                placeholder="Search for tokens"
                                v-model="wordSelected"
                            >
                            <button class="btn btn-outline-secondary" type="submit">Search</button>
                        </div>
                    </form>
                </div>
            </div>
        </nav>
        <model-statistics v-if="$route.name == 'home'"></model-statistics>
        <corpus-overview v-if="$route.name == 'home'"></corpus-overview>
        <topic-distributions v-if="$route.name == 'home'"></topic-distributions>
        <router-view></router-view>
    </div>
</template>

<script>
import topics from "../topic_words.json";
import ModelStatistics from "./components/ModelStatistics.vue";
import CorpusOverview from "./components/CorpusOverview.vue";
import TopicDistributions from "./components/TopicDistributions.vue";

const FIELD_LABELS = {
    author: "Author",
    text_genre: "Genre",
    publisher: "Publisher",
    pub_place: "Place of publication",
    collection: "Collection",
    editor: "Editor",
    keywords: "Keywords",
    pub_date: "Publication date",
    create_date: "Creation date",
    title: "Title",
    notes: "Notes",
    text_form: "Form",
    auth_gender: "Author gender",
};

export default {
    name: "app",
    components: { ModelStatistics, CorpusOverview, TopicDistributions },
    data() {
        return {
            topicData: topics,
            topicIds: [],
            timeSeriesEnabled: this.$globalConfig.timeSeriesConfig.enabled !== false,
            wordSelected: "",
            profiledFields: [],
        };
    },
    created() {
        this.$http
            .get(`${this.$globalConfig.apiServer}/get_profiled_fields/${this.$globalConfig.databaseName}`)
            .then((response) => {
                this.profiledFields = response.data.fields || [];
            })
            .catch(() => {
                this.profiledFields = [];
            });
    },
    methods: {
        searchVocab() {
            this.$router.push(`/word/${this.wordSelected}`);
            this.wordSelected = "";
        },
        fieldLabel(field) {
            return FIELD_LABELS[field] || field;
        },
    },
};
</script>

<style lang="scss">
@use "./assets/styles/theme.module.scss" as theme;

// Lift every navbar dropdown off the page with a soft shadow.
.dropdown-menu {
    box-shadow: 0 0.5rem 1.5rem rgba(0, 0, 0, 0.18);
    border: 1px solid rgba(0, 0, 0, 0.08);
}

#vocab-list .dropdown-menu {
    overflow-y: auto;
    max-height: 440px;
    padding: 0 !important;   // Bootstrap's default 0.5rem top/bottom leaves blank strips

    // Themed scrollbar (shows when scrolling on macOS, always on Win/Linux).
    scrollbar-width: thin;
    scrollbar-color: theme.$link-color rgba(theme.$link-color, 0.12);
    &::-webkit-scrollbar {
        width: 10px;
    }
    &::-webkit-scrollbar-track {
        background-color: rgba(theme.$link-color, 0.12);
    }
    &::-webkit-scrollbar-thumb {
        background-color: theme.$link-color;
        border-radius: 5px;
    }
}


a {
    text-decoration: none !important;
    transition: all 0.2s ease;
    border-radius: 2px;
}

// Slightly larger numeric values for accessibility (scores, percentages).
.frequency-value {
    font-weight: 600;
}
.badge.rounded-pill {
    font-size: 0.85rem !important;
    padding: 0.4em 0.65em !important;
}

// Kill the default Bootstrap table bottom-margin when the table is the
// last child of a card — the margin renders as an empty trailing row.
.card > .table:last-child,
.card > div > .table:last-child {
    margin-bottom: 0;
}

a:hover,
a:focus {
    background-color: rgba(theme.$link-color, 0.08);
    box-shadow: 0 0 0 3px rgba(theme.$link-color, 0.1);
}
</style>
