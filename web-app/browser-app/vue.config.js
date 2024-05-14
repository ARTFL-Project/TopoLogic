const ini = require("ini");
const fs = require("fs");

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
  let text = fs.readFileSync("/etc/topologic/global_settings.ini", "utf8");
  const globalConfig = ini.parse(text);
  const localConfig = require("./appConfig.json");
  return globalConfig.WEB_APP.server_name + "/" + localConfig.appPath;
}

function getDevServerConfig() {
  const globalConfig = require("./appConfig.json");
  if (process.env.NODE_ENV === "production") {
    return {};
  } else {
    let config = globalConfig.devServerConfig;
    return config;
  }
}
