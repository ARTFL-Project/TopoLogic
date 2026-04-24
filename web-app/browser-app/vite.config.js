import { defineConfig, loadEnv } from "vite"
import vue from "@vitejs/plugin-vue"
import path from "path"
import fs from "fs"

export default defineConfig(({ command }) => {
    // appConfig.build.json is per-deployment (written per-model at training
    // time). It holds only the handful of values that vite needs to bake into
    // the bundle — the rest of the config lives in appConfig.json and is
    // fetched at runtime so edits don't require a rebuild. In the source tree
    // this file may be absent — fall back to sensible defaults so
    // `npm run build` works for local dev / CI without a deployed model.
    let buildConfig = { appPath: "/", devServerConfig: {} }
    const buildConfigPath = path.resolve(__dirname, "appConfig.build.json")
    if (fs.existsSync(buildConfigPath)) {
        buildConfig = JSON.parse(fs.readFileSync(buildConfigPath, "utf-8"))
    }

    const base = command === "build"
        ? (buildConfig.appPath.startsWith("/") ? buildConfig.appPath : "/" + buildConfig.appPath) + "/"
        : "/"

    return {
        plugins: [vue()],
        resolve: {
            alias: { "@": path.resolve(__dirname, "src") },
        },
        base,
        build: {
            outDir: "dist",
            emptyOutDir: true,
        },
        css: {
            preprocessorOptions: {
                scss: { api: "modern-compiler" },
            },
        },
        server: buildConfig.devServerConfig || {},
    }
})
