module.exports = {
    devServer: {
        compress: true,
        disableHostCheck: true,
        host: "anomander.uchicago.edu",
        https: true,
        headers: {
            "Access-Control-Allow-Origin": "*",
        },
    },
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