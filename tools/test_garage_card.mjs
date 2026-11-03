import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.BC_PLAYWRIGHT_MODULE || 'playwright');
const script = readFileSync(new URL('../src/battle_conquest/web/hangar/garage.js', import.meta.url), 'utf8');
const css = readFileSync(new URL('../src/battle_conquest/web/hangar/garage.css', import.meta.url), 'utf8');
const browser = await chromium.launch({headless: true});
let scenarios = 0;
try {
    for (const language of ['en', 'fr']) for (const [width, height] of [[1280, 720], [1920, 1080], [2560, 1440]]) {
        const page = await browser.newPage({viewport: {width, height}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.setContent(`<style>html {font-size:1px} body {margin:0;font-size:14px}
            .QuestCard_base_a {position:absolute;top:40px;right:46px;width:319px;height:160px}
            .UnicumAccountCard {position:absolute;top:208px;right:46px;width:319px;height:55px}
            .UnicumTwitchPanel {position:absolute;top:271px;right:46px;width:319px;height:140px}
            ${css}</style><div class="QuestCard_base_a Card_ab12"><div class="Card_border_ab12"></div></div>
            <div class="UnicumAccountCard">Unicum</div><div class="UnicumTwitchPanel">Chat</div>`);
        await page.evaluate(({script, language}) => {
            window.commands = [];
            const labels = language === 'fr' ? {'Details': 'Détails', 'Close': 'Fermer', 'Settings': 'Réglages',
                'Choose a quest': 'Choisir une quête', 'Link my account': 'Lier mon compte', 'MOD ESTIMATE': 'MOD (indicatif)',
                'OFFICIAL': 'OFFICIEL', 'Reload': 'Actualiser'} : {};
            window.payload = {scope: 'A', shown: true, linked: false, running: false, labels,
                selected: null, choices: [], automatic: false, criteria: [], status: 'Online', has_data: false};
            window.model = {model: {snapshot: JSON.stringify(window.payload), onAction: action => window.commands.push(action)}};
            window.card = new Function('api', script)({model: window.model, report: message => {throw new Error(message);}});
            window.update = patch => {Object.assign(window.payload, patch); window.model.model.snapshot = JSON.stringify(window.payload);};
            window.interference = setInterval(() => {
                document.querySelector('.UnicumAccountCard').style.top = '208rem';
                document.querySelector('.UnicumTwitchPanel').style.top = '271rem';
            }, 250);
        }, {script, language});
        const card = page.locator('.BattleConquestGarage');
        await card.getByText(language === 'fr' ? 'Lier mon compte' : 'Link my account', {exact: true}).click();
        assert.equal(await page.evaluate(() => commands.at(-1).action), 'link');
        await page.evaluate(() => update({linked: true, has_data: true,
            selected: {key: 'individual:1', title: '<script>quest</script>'},
            choices: [{key: 'individual:1', title: '<script>quest</script>', status: 'active'}, {key: 'session:2', title: 'Challenge', status: 'running'}],
            criteria: Array.from({length: 6}, (_, i) => ({label: `Objective ${i}`, target: 100,
                values: {official: i === 0 ? '20 + ?' : String(i), estimate: 'Unavailable'}}))}));
        await page.waitForFunction(() => document.querySelectorAll('.BattleConquestGarage_metric').length === 6);
        assert.equal(await card.locator('script').count(), 0);
        assert.match(await card.textContent(), /20 \+ \?/);
        await page.waitForTimeout(550);
        const positions = await page.evaluate(() => {
            const rect = selector => {const r = document.querySelector(selector).getBoundingClientRect(); return {top: r.top, bottom: r.bottom};};
            return [rect('.BattleConquestGarage'), rect('.UnicumAccountCard'), rect('.UnicumTwitchPanel')];
        });
        assert.ok(positions[0].bottom + 7 <= positions[1].top, JSON.stringify(positions));
        assert.ok(positions[1].bottom + 7 <= positions[2].top, JSON.stringify(positions));
        assert.ok(positions[2].bottom <= height, JSON.stringify(positions));
        if (height === 720) {
            assert.equal(await card.locator('.BattleConquestGarage_content').evaluate(el => el.scrollHeight > el.clientHeight), true);
        }
        await card.locator('.BattleConquestGarage_choose').click();
        await page.keyboard.press('ArrowDown');
        await page.keyboard.press('ArrowDown');
        await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => commands.at(-1).selection), 'session:2');
        await card.getByText(language === 'fr' ? 'Détails' : 'Details', {exact: true}).click();
        assert.equal(await page.evaluate(() => commands.at(-1).action), 'details');
        await page.evaluate(() => update({scope: 'B', automatic: true, status: 'Offline - retained'}));
        await page.waitForFunction(() => document.querySelector('.BattleConquestGarage_choose').disabled);
        assert.equal(await card.locator('.BattleConquestGarage_choose').isDisabled(), true);
        await card.getByRole('button', {name: language === 'fr' ? 'Fermer' : 'Close', exact: true}).click();
        assert.equal(await page.evaluate(() => commands.at(-1).scope), 'B');
        assert.equal(await page.locator('.UnicumAccountCard').evaluate(el => el.getBoundingClientRect().top), 208);
        await page.evaluate(() => update({shown: true, status: 'Restored', automatic: false}));
        await card.waitFor({state: 'visible'});
        await page.evaluate(() => {card.stop(); clearInterval(interference);});
        assert.equal(await page.locator('.BattleConquestGarage').count(), 0);
        assert.equal(await page.locator('.UnicumAccountCard').evaluate(el => el.getBoundingClientRect().top), 208);
        assert.deepEqual(errors, []);
        scenarios++;
        await page.close();
    }
    console.log(`Garage card: ${scenarios} FR/EN and viewport scenarios passed`);
} finally { await browser.close(); }
