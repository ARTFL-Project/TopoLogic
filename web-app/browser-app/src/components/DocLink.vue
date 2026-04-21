<template>
    <Teleport to="body">
        <div v-show="isOpen" class="popover bs-popover-top show" ref="popover" role="tooltip">
            <div class="popover-arrow" :style="arrowStyle"></div>
            <h3 class="popover-header">
                <span style="font-variant: small-caps;">Choose between:</span>
            </h3>
            <div class="popover-body p-0">
                <ul class="list-group list-group-flush">
                    <li class="list-group-item">
                        <router-link :to="topoLink">Explore distribution in corpus</router-link>
                    </li>
                    <li class="list-group-item">
                        <a
                            :href="philoLink"
                            target="_blank"
                            v-if="word"
                        >Explore word usage in document in PhiloLogic</a>
                        <a :href="philoLink" target="_blank" v-else>Read document in PhiloLogic</a>
                    </li>
                </ul>
            </div>
        </div>
    </Teleport>
</template>

<script>
import { createPopper } from "@popperjs/core";

export default {
    name: "DocLink",
    props: ["target", "metadata", "doc", "word"],
    data() {
        return {
            philoUrl: this.$globalConfig.philoLogicUrl,
            isOpen: false,
            popperInstance: null,
            arrowStyle: {},
        };
    },
    computed: {
        philoLink() {
            let philoType = `philo_${this.metadata.philo_type}_id`;
            if (typeof this.word != "undefined") {
                return `${this.philoUrl}/query?report=concordance&q=${this.word}&${philoType}=${this.metadata[philoType]}`;
            } else if (this.metadata.philo_type == "doc") {
                return `${this.philoUrl}/navigate/${this.metadata[philoType]}/table-of-contents/`;
            } else {
                let objectId = this.metadata[philoType].split(" ").join("/");
                return `${this.philoUrl}/navigate/${objectId}/`;
            }
        },
        topoLink() {
            let philoType = `philo_${this.metadata.philo_type}_id`;
            let objectId = this.metadata[philoType].split(" ").join("/");
            return `/document/${objectId}/`;
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
