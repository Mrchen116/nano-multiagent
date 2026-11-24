const { createRequire } = require('node:module');
const { join } = require('node:path');
const { readFileSync } = require('node:fs');
const yaml = createRequire(join(__dirname, 'apps/node/lib/cli.js'))('js-yaml');
const config = yaml.load(readFileSync(process.argv[2], 'utf8'));
console.log(config.node.node_name + ' · ' + new URL(config.im_service.url).host);
