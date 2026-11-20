import assert from 'node:assert/strict';
import {script, css} from './garage_card_sources.mjs';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.BC_PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({headless: true});
try {
    for (const language of ['en', 'fr']) for (const height of [720, 1080]) {
        const page = await browser.newPage({viewport: {width: 1280, height}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.setContent(`<style>html {font-size:1px} body {margin:0;background:#252525}${css}</style>`);
        await page.evaluate(({script, language}) => {
            window.commands = [];
            const kinds = ['individual', 'session', 'bffa', 'event', 'tile'];
            const choices = kinds.flatMap(kind => Array.from({length: 8}, (_, index) => ({
                key: `${kind}:${index + 1}`, kind, title: `${kind} <title> ${index + 1}`, status: 'active', game_mode: 'random'})));
            const labels = language === 'fr' ? {'Quests': 'Quêtes', 'Challenges': 'Défis', 'Map': 'Carte', 'Tournaments': 'Tournois',
                'Choose an objective': 'Choisir un objectif'} : {};
            window.payload = {scope: 'account-a', language, shown: true, linked: true, running: false, has_data: true,
                busy: false, blocked: false, selected: choices[16], choices, criteria: [], labels,
                tracking: ['OFFICIAL', 'Score: 0', 'Rank: Unavailable', 'Opponent: <rival>'], status: 'Online'};
            window.model = {model: {snapshot: JSON.stringify(window.payload), onAction: action => commands.push(action)}};
            window.card = new Function('api', script)({model: window.model, report: message => {throw new Error(message);}});
            window.update = patch => {Object.assign(payload, patch); model.model.snapshot = JSON.stringify(payload);};
        }, {script, language});
        const card = page.locator('.BattleConquestGarage');
        await card.waitFor({state: 'visible'});
        assert.equal(await card.locator('script').count(), 0);
        assert.match(await card.locator('.BattleConquestGarage_tournament').innerText(), /Score: 0/);
        assert.match(await card.locator('.BattleConquestGarage_tournament').innerText(), /<rival>/);
        const choose = card.locator('.BattleConquestGarage_choose');
        await choose.click();
        assert.equal(await page.getByRole('group').count(), 5);
        assert.equal(await page.getByRole('option').count(), 41, 'every participation remains reachable');
        const options = page.locator('.BattleConquestGarage_options');
        assert(await options.evaluate(el => el.scrollHeight > el.clientHeight));
        assert(await options.evaluate(el => {
            const rect = el.getBoundingClientRect();
            return rect.top >= 0 && rect.bottom <= innerHeight;
        }));
        await page.keyboard.press('ArrowDown');
        assert.equal(await page.getByRole('option').nth(1).evaluate(el => el === document.activeElement), true);
        for (let index = 0; index < 39; index++) await page.keyboard.press('ArrowDown');
        assert.equal(await page.getByRole('option').last().evaluate(el => el === document.activeElement), true);
        await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => commands.at(-1).selection), 'tile:8');
        assert.equal(await choose.getAttribute('aria-expanded'), 'false');
        await choose.click();
        if (process.env.BC_GARAGE_SCREENSHOT && language === 'fr' && height === 1080) {
            await options.evaluate(el => {el.scrollTop = 0;});
            await page.screenshot({path: process.env.BC_GARAGE_SCREENSHOT});
        }
        await page.keyboard.press('Escape');
        assert.equal(await choose.evaluate(el => el === document.activeElement), true);
        await page.evaluate(() => update({scope: 'account-b', selected: null, choices: [], tracking: [], criteria: []}));
        await page.waitForFunction(() => document.querySelector('.BattleConquestGarage_tournament').style.display === 'none');
        assert.equal(await page.getByRole('group').count(), 0, 'account change removes previous participations');
        await page.evaluate(() => card.stop());
        assert.equal(await page.locator('.BattleConquestGarage').count(), 0, 'stop removes the owned UI');
        assert.deepEqual(errors, []);
        await page.close();
    }
    console.log('garage tournaments: 4 scenarios passed');
} finally {
    await browser.close();
}
