<template>
    <Teleport to="body">
        <div v-show="isOpen" class="popover bs-popover-top show" ref="popover" role="tooltip">
            <div class="popover-arrow"></div>
            <h3 class="popover-header">
                <span style="font-variant: small-caps">{{ word }}</span>
            </h3>
            <div class="popover-body p-0">
                <ul class="list-group list-group-flush">
                    <li class="list-group-item">
                        <router-link :to="`/word/${word}`">Explore usage in corpus</router-link>
                    </li>
                    <li class="list-group-item px-0">
                        <a :href="link" target="_blank" v-if="metadata">See all occurrences in document</a>
                        <ul style="padding-inline-start: 1.5em; margin-bottom: 0" v-else>
                            <h6 style="margin-left: -1em">See all occurrences in:</h6>
                            <li v-for="(philoUrl, philoDb) in philoUrls" :key="philoUrl" class="py-1">
                                <a :href="`${philoUrl}/query?report=concordance&q=${word}.?`" target="_blank">{{ philoDb }}</a>
                            </li>
                        </ul>
                    </li>
                </ul>
            </div>
        </div>
    </Teleport>
</template>

<script>
import { createPopper } from "@popperjs/core";

export default {
    name: "WordLink",
    props: ["target", "metadata", "word"],
    data() {
        return {
            philoUrls: this.$globalConfig.philoLogicUrls,
            isOpen: false,
            popperInstance: null,
        };
    },
    computed: {
        link() {
            let philoType = `philo_${this.metadata.philo_type}_id`;
            let objectId = this.metadata[philoType];
            return `${this.philoUrls[this.metadata.philo_db]}/query?report=concordance&${philoType}=${objectId}&q=${this.word}.?`;
        },
    },
    mounted() {
        const targetEl = document.getElementById(this.target);
        if (!targetEl) return;
        this.onTargetClick = (e) => {
            e.stopPropagation();
            this.isOpen ? this.hide() : this.show();
        };
        this.onDocumentClick = (e) => {
            if (!this.isOpen) return;
            if (targetEl.contains(e.target)) return;
            if (this.$refs.popover?.contains(e.target)) return;
            this.hide();
        };
        targetEl.addEventListener("click", this.onTargetClick);
        document.addEventListener("click", this.onDocumentClick, true);
    },
    beforeUnmount() {
        const targetEl = document.getElementById(this.target);
        if (targetEl && this.onTargetClick) targetEl.removeEventListener("click", this.onTargetClick);
        if (this.onDocumentClick) document.removeEventListener("click", this.onDocumentClick, true);
        this.popperInstance?.destroy();
    },
    methods: {
        show() {
            this.isOpen = true;
            this.$nextTick(() => {
                const targetEl = document.getElementById(this.target);
                if (!targetEl || !this.$refs.popover) return;
                this.popperInstance = createPopper(targetEl, this.$refs.popover, {
                    placement: "top",
                    modifiers: [
                        { name: "offset", options: { offset: [0, 8] } },
                        {
                            name: "arrow",
                            options: { element: this.$refs.popover.querySelector(".popover-arrow") },
                        },
                    ],
                });
            });
        },
        hide() {
            this.isOpen = false;
            this.popperInstance?.destroy();
            this.popperInstance = null;
        },
    },
};
</script>
