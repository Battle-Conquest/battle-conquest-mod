import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {checkPlacement} from './garage_card_placement.mjs';
import {checkFloor} from './garage_card_floor.mjs';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.BC_PLAYWRIGHT_MODULE || 'playwright');
const script = readFileSync(new URL('../src/battle_conquest/web/hangar/garage.js', import.meta.url), 'utf8');
// Gameface ignores outline properties; Chromium must not hide that limitation.
const css = readFileSync(new URL('../src/battle_conquest/web/hangar/garage.css', import.meta.url), 'utf8')
    .replace(/\boutline(?:-[a-z]+)?\s*:[^;}]+;?/g, '');
const browser = await chromium.launch({headless: true});
let scenarios = 0;
try {
    for (const native of [true, false]) for (const language of ['en', 'fr']) for (const [width, height] of [[1280, 720], [1920, 1080], [2560, 1440]]) {
        const page = await browser.newPage({viewport: {width, height}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.setContent(`<style>html {font-size:1px} body {margin:0;font-size:14px}
            .QuestCard_base_a {position:absolute;top:40px;right:46px;width:319px;height:160px}
            .UnicumAccountCard {position:absolute;top:208px;right:46px;width:319px;height:55px}
            .UnicumTwitchPanel {position:absolute;top:271px;right:46px;width:319px;height:140px}
            .Card_ab12 {background:transparent;font-weight:bold}
            /* Reproduce native control text staying black despite button CSS. */
            button {color:black !important}
            ${css}</style>${native ? '<div class="QuestCard_base_a Card_ab12"><div class="Card_border_ab12"></div></div>' : ''}
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
        await card.waitFor({state: 'visible'});
        assert.deepEqual(await card.evaluate(el => {
            const style = getComputedStyle(el);
            return [style.backgroundColor, style.fontSize, style.fontWeight, el.classList.contains('Card_ab12')];
        }), ['rgba(23, 23, 23, 0.95)', '16px', '400', false]);
        const settings = card.getByRole('button', {name: language === 'fr' ? 'Réglages' : 'Settings', exact: true});
        assert.equal(await settings.locator('svg[aria-hidden="true"] path').count(), 1);
        const titleColor = await card.locator('.BattleConquestGarage_title').evaluate(el => getComputedStyle(el).color);
        assert.equal(titleColor, 'rgb(230, 226, 216)');
        assert.equal(await settings.locator('svg path').evaluate(el => getComputedStyle(el).fill), titleColor);
        await settings.click();
        assert.equal(await page.evaluate(() => commands.at(-1).action), 'settings');
        await card.getByText(language === 'fr' ? 'Lier mon compte' : 'Link my account', {exact: true}).click();
        assert.equal(await page.evaluate(() => commands.at(-1).action), 'link');
        await page.evaluate(() => update({linked: true, has_data: true,
            selected: {key: 'individual:1', title: '<script>quest</script>'},
            choices: [{key: 'individual:1', title: '<script>quest</script>', status: 'active'}, {key: 'session:2', title: 'Finished challenge', status: 'settled'}],
            criteria: Array.from({length: 6}, (_, i) => ({label: `Objective ${i}`, target: 100,
                values: {official: i === 0 ? '20 + ?' : String(i), estimate: 'Unavailable'}}))}));
        await page.waitForFunction(() => document.querySelectorAll('.BattleConquestGarage_metric').length === 6);
        assert.equal(await card.locator('script').count(), 0);
        assert.match(await card.textContent(), /20 \+ \?/);
        assert.deepEqual(await card.locator('.BattleConquestGarage_metric strong').evaluateAll(items =>
            items.map(el => getComputedStyle(el).fontWeight)), Array(6).fill('400'));
        for (const button of await card.getByRole('button').all()) {
            if (await button.isVisible()) assert.equal(await button.locator('.BattleConquestGarage_buttonText')
                .evaluate(el => getComputedStyle(el).color), titleColor);
        }
        await page.waitForTimeout(550);
        const positions = await page.evaluate(() => {
            const rect = selector => {const r = document.querySelector(selector).getBoundingClientRect(); return {top: r.top, bottom: r.bottom};};
            return [rect('.BattleConquestGarage'), rect('.UnicumAccountCard'), rect('.UnicumTwitchPanel')];
        });
        assert.ok(positions[1].bottom + 7 <= positions[2].top, JSON.stringify(positions));
        assert.ok(positions[2].bottom + 7 <= positions[0].top, JSON.stringify(positions));
        assert.ok(positions[0].bottom <= height, JSON.stringify(positions));
        assert.equal(positions[1].top, 208, 'Unicum keeps its own account-card placement');
        assert.equal(positions[2].top, 271, 'Unicum keeps its own chat placement');
        if (height === 720) {
            assert.equal(await card.locator('.BattleConquestGarage_content').evaluate(el => el.scrollHeight > el.clientHeight), true);
        }
        await card.locator('.BattleConquestGarage_choose').click();
        assert.deepEqual(await card.getByRole('option').locator('.BattleConquestGarage_buttonText')
            .evaluateAll(items => items.map(el => getComputedStyle(el).color)),
            Array(3).fill(titleColor));
        await page.keyboard.press('ArrowDown');
        await page.keyboard.press('ArrowDown');
        await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => commands.at(-1).selection), 'session:2');
        for (const [name, action] of [[language === 'fr' ? 'Détails' : 'Details', 'details'],
                                      [language === 'fr' ? 'Actualiser' : 'Reload', 'reload']]) {
            const button = card.getByRole('button', {name, exact: true});
            await button.hover();
            const hovered = await button.evaluate(el => getComputedStyle(el).backgroundColor);
            assert.equal(await button.locator('.BattleConquestGarage_buttonText').evaluate(el => getComputedStyle(el).color), titleColor);
            assert.equal(hovered, 'rgb(57, 56, 50)');
            const before = await page.evaluate(action => commands.filter(item => item.action === action).length, action);
            for (let click = 0; click < 2; click++) {
                await page.mouse.down();
                assert.equal(await button.evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(81, 75, 59)');
                assert.equal(await button.locator('.BattleConquestGarage_buttonText').evaluate(el => getComputedStyle(el).color), titleColor);
                await page.mouse.up();
                assert.equal(await button.evaluate(el => getComputedStyle(el).backgroundColor), hovered);
            }
            assert.equal(await page.evaluate(action => commands.filter(item => item.action === action).length, action), before + 2);
        }
        await page.mouse.move(0, 0);
        await card.getByRole('button', {name: language === 'fr' ? 'Détails' : 'Details', exact: true}).focus();
        await page.keyboard.press('Tab');
        const reload = card.getByRole('button', {name: language === 'fr' ? 'Actualiser' : 'Reload', exact: true});
        assert.equal(await reload.evaluate(el => document.activeElement === el), true);
        assert.deepEqual(await reload.evaluate(el => {
            const style = getComputedStyle(el);
            return [style.borderTopColor, style.boxShadow, style.backgroundColor];
        }), ['rgb(234, 197, 110)', 'rgb(234, 197, 110) 0px 0px 0px 1px inset', 'rgb(36, 35, 31)']);
        for (const key of ['Enter', 'Space']) {
            const before = await page.evaluate(() => commands.filter(item => item.action === 'reload').length);
            await page.keyboard.press(key);
            assert.equal(await page.evaluate(() => commands.filter(item => item.action === 'reload').length), before + 1);
            assert.equal(await reload.evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(36, 35, 31)');
        }
        if (native && language === 'fr' && height === 720) await page.screenshot({path: '/tmp/bc-mod-55-card.png'});
        await page.evaluate(() => update({scope: 'B', automatic: true, status: 'Ready to choose'}));
        await page.waitForFunction(() => document.querySelector('.BattleConquestGarage_status').textContent === 'Ready to choose');
        assert.equal(await card.locator('.BattleConquestGarage_choose').isEnabled(), true, 'a sole active objective must not lock manual choices');
        await card.locator('.BattleConquestGarage_choose').click();
        await card.getByRole('option', {name: 'Finished challenge — settled'}).click();
        assert.equal(await page.evaluate(() => commands.at(-1).selection), 'session:2');
        await page.evaluate(() => update({selected: {key: 'session:2', title: 'Finished challenge'}, automatic: false,
            criteria: [{label: 'Final damage', target: 100, values: {official: '75', estimate: 'Unavailable'}}]}));
        await page.waitForFunction(() => document.querySelector('.BattleConquestGarage_choose').textContent === 'Finished challenge');
        assert.match(await card.textContent(), /75/);
        for (const patch of [{busy: true}, {busy: false, blocked: true}]) {
            await page.evaluate(patch => update(patch), patch);
            await page.waitForFunction(() => document.querySelector('.BattleConquestGarage_choose').disabled);
            assert.equal(await card.locator('.BattleConquestGarage_choose').isDisabled(), true);
            assert.equal(await card.locator('.BattleConquestGarage_choose .BattleConquestGarage_buttonText')
                .evaluate(el => getComputedStyle(el).color), 'rgb(140, 137, 129)');
            if (patch.busy) {
                assert.equal(await reload.isDisabled(), true);
                const before = await page.evaluate(() => commands.filter(item => item.action === 'reload').length);
                await reload.evaluate(el => el.click());
                // Gameface buttons do not provide all native browser behaviour.
                await reload.dispatchEvent('click');
                assert.equal(await page.evaluate(() => commands.filter(item => item.action === 'reload').length), before);
            }
        }
        await page.evaluate(() => update({blocked: false}));
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
    const page = await browser.newPage();
    await page.setContent(`<style>${css}</style>`);
    await page.evaluate(script => {
        window.commands = []; window.reports = []; window.now = 2000;
        Date.now = () => window.now;
        window.setInterval = callback => {window.tick = callback; return 1;};
        window.clearInterval = () => {};
        const query = document.querySelectorAll.bind(document);
        document.querySelectorAll = selector => {
            if (selector.includes('QuestCard_base')) throw new Error('other card layout unavailable');
            return query(selector);
        };
        window.payload = {scope: 'A', shown: true, linked: false, labels: {}, choices: [], criteria: []};
        window.model = {model: {snapshot: JSON.stringify(payload), onAction: action => commands.push(action)}};
        window.card = new Function('api', script)({model, report: message => reports.push(message)});
        for (let i = 0; i < 20; i++) {window.now += 2000; tick();}
    }, script);
    assert.equal(await page.locator('.BattleConquestGarage').isVisible(), true);
    assert.equal(await page.evaluate(() => commands.filter(row => row.action === 'ready').length), 21,
        'a rendered card keeps acknowledging beyond 30 seconds even when placement fails');
    assert.equal(await page.evaluate(() => reports.length), 21, 'placement failures stay diagnostic');
    await page.evaluate(() => {
        payload.scope = 'B'; model.model.snapshot = JSON.stringify(payload); now += 2000; tick();
    });
    assert.equal(await page.evaluate(() => commands.at(-1).scope), 'B');
    const count = await page.evaluate(() => commands.length);
    await page.evaluate(() => {
        payload.shown = false; model.model.snapshot = JSON.stringify(payload); now += 2000; tick();
    });
    assert.equal(await page.evaluate(() => commands.length), count, 'a hidden card does not acknowledge rendering');
    await page.evaluate(() => {card.stop(); now += 2000; tick();});
    assert.equal(await page.evaluate(() => commands.length), count, 'a stopped card cannot acknowledge rendering');
    await page.close();
    const placementScenarios = await checkPlacement(browser, script, css);
    await checkFloor(browser, script, css);
    console.log(`Garage card: ${scenarios} FR/EN and viewport scenarios, ${placementScenarios} placement scenarios plus placement-failure heartbeat passed`);
} finally { await browser.close(); }
