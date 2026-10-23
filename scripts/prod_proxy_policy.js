// Clash Verge global extension: public traffic uses the existing selected proxy.
function main(config) {
  const privateV4 = [
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "169.254.0.0/16", "100.64.0.0/10", "224.0.0.0/4",
  ];
  const privateV6 = ["::1/128", "fc00::/7", "fe80::/10", "ff00::/8"];
  config.mode = "rule";
  config["find-process-mode"] = "always";
  config.tun = {
    ...config.tun,
    enable: true,
    "auto-route": true,
    "auto-detect-interface": true,
    "route-exclude-address": [...privateV4, ...privateV6],
  };
  config.rules = [
    ...["local", "lan", "home.arpa", "ts.net"].map((s) => `DOMAIN-SUFFIX,${s},DIRECT`),
    ...privateV4.map((s) => `IP-CIDR,${s},DIRECT,no-resolve`),
    ...privateV6.map((s) => `IP-CIDR6,${s},DIRECT,no-resolve`),
    "MATCH,🔰 选择节点",
  ];
  return config;
}
