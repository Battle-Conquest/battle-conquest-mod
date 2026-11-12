import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.BC_PLAYWRIGHT_MODULE || 'playwright');
const script = readFileSync(new URL('../src/battle_conquest/web/hangar/garage.js', import.meta.url), 'utf8');
const css = readFileSync(new URL('../src/battle_conquest/web/hangar/garage.css', import.meta.url), 'utf8');
const loader = readFileSync(new URL('../res/gui/gameface/mods/battle_conquest/Garage/Garage.js', import.meta.url), 'utf8')
    .replace(/^import .*;$/m, '');
const browser = await chromium.launch({headless: true});
let scenarios = 0;
try {
    for (const native of [false, true]) for (const [width, height] of [[1280, 720], [1920, 1080], [2560, 1440]]) {
        const page = await browser.newPage({viewport: {width, height}});
        await page.setContent(`<style>html {font-size:1px} body {margin:0}
            .QuestCard_base_test {position:absolute;top:40px;right:80px;width:290px;height:160px}
            .UnicumAccountCard {position:absolute;top:208px;right:${native ? 80 : 46}px;width:290px;height:55px}
            .UnicumTwitchPanel {position:absolute;top:271px;right:${native ? 80 : 46}px;width:290px;height:140px}
            ${css}</style>
            ${native ? '<div class="QuestCard_base_test"></div>' : ''}
            <div class="UnicumAccountCard" style="top:208rem">Account</div>
            <div class="UnicumTwitchPanel" style="top:271rem">Twitch</div>`);
        await page.evaluate(({script, css, loader}) => {
            window.commands = []; window.reports = [];
            console.warn = message => reports.push(message);
            window.setInterval = callback => {window.tick = callback; return 1;};
            window.clearInterval = () => {};
            window.payload = {scope: 'A', shown: true, linked: false, labels: {}, choices: [], criteria: [], status: 'Online'};
            window.model = {model: {snapshot: JSON.stringify(payload), revision: 1, script, style: css,
                onAction: action => commands.push(action)},
                onUpdate: callback => {window.reload = callback;}, subscribe() {}};
            window.engine = {whenReady: Promise.resolve()};
            new Function('ModelObserver', loader)(() => model);
            window.update = patch => {Object.assign(payload, patch); model.model.snapshot = JSON.stringify(payload); tick();};
            window.positions = () => ['.UnicumAccountCard', '.UnicumTwitchPanel']
                .map(selector => document.querySelector(selector).getBoundingClientRect().top);
            window.saved = () => ['.UnicumAccountCard', '.UnicumTwitchPanel']
                .map(selector => document.querySelector(selector).style.cssText);
        }, {script, css, loader});
        const card = page.locator('.BattleConquestGarage');
        await card.waitFor({state: 'visible'});
        const originalStyles = ['top: 208rem;', 'top: 271rem;'];
        const displaced = await page.evaluate(() => positions());
        assert.ok(displaced[0] > 208 && displaced[1] > 271);
        assert.deepEqual(await page.evaluate(() => saved()), originalStyles);

        // The selector releases Twitch immediately when Unicum changes mode,
        // before Battle-Conquest has had another polling opportunity.
        for (const mode of ['windowed', 'dragging']) {
            await page.evaluate(mode => document.querySelector('.UnicumTwitchPanel').classList.add('UnicumTwitchPanel__' + mode), mode);
            assert.equal((await page.evaluate(() => positions()))[1], 271);
            await page.evaluate(() => tick());
            assert.equal((await page.evaluate(() => positions()))[1], 271);
            await page.evaluate(mode => {document.querySelector('.UnicumTwitchPanel').classList.remove('UnicumTwitchPanel__' + mode); tick();}, mode);
            assert.deepEqual(await page.evaluate(() => positions()), displaced);
        }
        // A docked panel moved to a different column keeps its own position.
        await page.evaluate(() => {document.querySelector('.UnicumTwitchPanel').style.right = '600rem'; tick();});
        assert.equal((await page.evaluate(() => positions()))[1], 271);
        await page.evaluate(() => {document.querySelector('.UnicumTwitchPanel').style.right = ''; tick();});

        // Visibility, close and reloading must restore both widgets every time.
        for (let pass = 0; pass < 3; pass++) {
            await page.evaluate(() => update({shown: false}));
            assert.deepEqual(await page.evaluate(() => positions()), [208, 271]);
            await page.evaluate(() => update({shown: true}));
            assert.deepEqual(await page.evaluate(() => positions()), displaced);
        }
        await card.getByRole('button', {name: 'Close', exact: true}).click();
        assert.deepEqual(await page.evaluate(() => positions()), [208, 271]);
        await page.evaluate(() => update({status: 'Reopened'}));
        assert.deepEqual(await page.evaluate(() => positions()), displaced);

        // Do not retain a previous override if DOM geometry becomes unavailable.
        await page.evaluate(() => {
            const query = document.querySelectorAll.bind(document);
            document.querySelectorAll = () => {throw new Error('layout temporarily unavailable');};
            tick(); document.querySelectorAll = query;
        });
        assert.deepEqual(await page.evaluate(() => positions()), [208, 271]);
        assert.equal(await card.isVisible(), true);
        assert.equal(await page.evaluate(() => reports.length), 1);
        await page.evaluate(() => tick());
        assert.deepEqual(await page.evaluate(() => positions()), displaced);

        await page.evaluate(() => {model.model.revision = 2; reload();});
        assert.equal(await card.count(), 1);
        assert.deepEqual(await page.evaluate(() => positions()), displaced);
        await page.evaluate(() => {model.model.revision = 0; reload();});
        assert.equal(await card.count(), 0);
        assert.deepEqual(await page.evaluate(() => positions()), [208, 271]);
        assert.deepEqual(await page.evaluate(() => saved()), originalStyles);
        await page.evaluate(() => {model.model.revision = 3; reload();});
        assert.equal(await card.count(), 1);
        assert.deepEqual(await page.evaluate(() => positions()), displaced);

        if (native) {
            await page.evaluate(() => {document.querySelector('.QuestCard_base_test').remove(); tick();});
            assert.deepEqual(await card.evaluate(el => [el.getBoundingClientRect().width, el.style.right]), [319, '']);
        }
        await page.evaluate(() => {model.model.revision = 0; reload();});
        assert.deepEqual(await page.evaluate(() => positions()), [208, 271]);
        scenarios++;
        await page.close();
    }
    console.log(`Garage restoration: ${scenarios} viewport/mission scenarios passed, including Twitch modes, failures and loader teardown`);
} finally { await browser.close(); }
