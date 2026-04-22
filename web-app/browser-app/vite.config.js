import { defineConfig, loadEnv } from "vite"
import vue from "@vitejs/plugin-vue"
import path from "path"
import fs from "fs"

export default defineConfig(({ command }) => {
    // appConfig.json is per-deployment (written per-model at training time).
    // In the source tree it may be absent — fall back to sensible defaults
    // so `npm run build` works for local dev / CI without a deployed model.
    let appConfig = { appPath: "/", devServerConfig: {} }
    const appConfigPath = path.resolve(__dirname, "appConfig.json")
    if (fs.existsSync(appConfigPath)) {
        appConfig = JSON.parse(fs.readFileSync(appConfigPath, "utf-8"))
    }

    const base = command === "build"
        ? (appConfig.appPath.startsWith("/") ? appConfig.appPath : "/" + appConfig.appPath) + "/"
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
        server: appConfig.devServerConfig || {},
    }
})
