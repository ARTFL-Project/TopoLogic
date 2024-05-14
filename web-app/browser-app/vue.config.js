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
  const localConfig = require("./appConfig.json");
  if (!localConfig.appPath.startsWith("/")) {
    return "/" + localConfig.appPath;
  }
  return localConfig.appPath;
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
