<template>
    <table class="table table-hover">
        <thead>
            <tr>
                <th
                    v-for="field in fields"
                    :key="field.key"
                    :style="field.sortable ? 'cursor: pointer; user-select: none;' : ''"
                    @click="field.sortable && toggleSort(field.key)"
                >
                    {{ field.label }}
                    <span v-if="field.sortable && sortBy === field.key">
                        {{ sortDesc ? '▼' : '▲' }}
                    </span>
                </th>
            </tr>
        </thead>
        <tbody>
            <tr v-for="(item, idx) in sortedItems" :key="idx" @click="$emit('row-clicked', item)">
                <td v-for="field in fields" :key="field.key">
                    <slot :name="`cell(${field.key})`" :value="item[field.key]" :item="item">
                        {{ item[field.key] }}
                    </slot>
                </td>
            </tr>
        </tbody>
    </table>
</template>

<script>
export default {
    name: "SortableTable",
    props: {
        items: { type: Array, required: true },
        fields: { type: Array, required: true },
        initialSortBy: { type: String, default: null },
        initialSortDesc: { type: Boolean, default: false }
    },
    emits: ["row-clicked"],
    data() {
        return {
            sortBy: this.initialSortBy,
            sortDesc: this.initialSortDesc
        };
    },
    watch: {
        initialSortBy(v) { this.sortBy = v; },
        initialSortDesc(v) { this.sortDesc = v; }
    },
    computed: {
        sortedItems() {
            if (!this.sortBy) return this.items;
            const dir = this.sortDesc ? -1 : 1;
            return [...this.items].sort((a, b) => {
                const av = a[this.sortBy];
                const bv = b[this.sortBy];
                if (av == null) return 1;
                if (bv == null) return -1;
                if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
                return String(av).localeCompare(String(bv), undefined, { numeric: true }) * dir;
            });
        }
    },
    methods: {
        toggleSort(key) {
            if (this.sortBy === key) {
                this.sortDesc = !this.sortDesc;
            } else {
                this.sortBy = key;
                this.sortDesc = false;
            }
        }
    }
};
</script>
