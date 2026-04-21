import { defineConfig, loadEnv } from "vite"
import vue from "@vitejs/plugin-vue"
import path from "path"
import fs from "fs"

export default defineConfig(({ command }) => {
    const appConfig = JSON.parse(
        fs.readFileSync(path.resolve(__dirname, "appConfig.json"), "utf-8")
    )

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
