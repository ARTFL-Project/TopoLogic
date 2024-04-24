const fs = require('fs');

module.exports = {
    devServer: getDevServerConfig(),
    configureWebpack: {
        output: {
            globalObject: "this",
        },
    },
    publicPath: process.env.NODE_ENV === "production" ? getAppPath() : "/",
};

function getAppPath() {
    const globalConfig = require("./appConfig.json");
    return "/" + globalConfig.appPath;
}

function getDevServerConfig() {
    const globalConfig = require("./appConfig.json");
    if (process.env.NODE_ENV === "production") {
        return {}
    } else {
        let config = globalConfig.devServerConfig
        config.cert = fs.readFileSync(config.cert)
        config.key = fs.readFileSync(config.key)
        return config
    }
}