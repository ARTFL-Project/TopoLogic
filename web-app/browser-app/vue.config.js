const fs = require('fs');

module.exports = {
    devServer: {
        https: true,
        key: fs.readFileSync("/etc/letsencrypt/live/anomander.uchicago.edu/privkey.pem"),
        cert: fs.readFileSync("/etc/letsencrypt/live/anomander.uchicago.edu/fullchain.pem"),
        compress: true,
        disableHostCheck: true,
        host: "anomander.uchicago.edu",
        headers: {
            'Access-Control-Allow-Origin': '*'
        }
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