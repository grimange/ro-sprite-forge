// Run the repository's trusted MCP journey function with an isolated browser.
// Usage: node browser-run.cjs /absolute/path/to/installed/playwright
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.argv[2]);
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage();
    page.on('console', m => console.log('BROWSER', m.type(), m.text()));
    const root = path.resolve(__dirname, '../../..');
    const source = fs.readFileSync(path.join(root, 'tests/browser/rsf23-mcp.js'), 'utf8')
      .trim().replace(/;$/, '').replace('127.0.0.1:8182', '127.0.0.1:8183');
    await eval('(' + source + ')')(page);
    console.log('RSF24_CHROMIUM_TEN_JOURNEYS_PASS');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
