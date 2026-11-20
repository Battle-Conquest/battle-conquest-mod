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
    for (const unicum of [false, true]) for (const language of ['en', 'fr'])
        for (const [width, height, scale] of [[1280, 720, 1], [1920, 1080, 1], [2560, 1440, 1], [2560, 1440, 2]]) {
        const page = await browser.newPage({viewport: {width, height}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.setContent(`<style>html {font-size:${scale}px} body {margin:0}
            .QuestCard_base_test {position:absolute;top:40px;right:46rem;width:319rem;height:160px}
            .UnicumAccountCard {position:absolute;top:208px;right:46rem;width:319rem;height:55rem}
            .UnicumTwitchPanel {position:absolute;top:271px;right:46rem;width:319rem;height:140rem}
            .Page_carousel_test {position:absolute;top:${height - 180}px;left:0;right:0;height:180px;z-index:100}
            ${css}</style><div class="QuestCard_base_test"></div><div class="Page_carousel_test"></div>
            ${unicum ? '<div class="UnicumAccountCard">Account</div><div class="UnicumTwitchPanel">Twitch</div>' : ''}`);
        await page.evaluate(({script, language, scale}) => {
            window.commands = []; window.wheels = 0; window.handled = 0;
            document.addEventListener('wheel', () => wheels++);
            window.viewEnv = {pxToRem: px => px / scale, setEventHandled: () => handled++};
            window.setInterval = callback => {window.tick = callback; return 1;};
            window.clearInterval = () => {};
            const title = language === 'fr' ? 'Un objectif avec un titre long et des accents' : 'An objective with a long title';
            window.payload = {scope: 'A', language, shown: true, linked: true, has_data: true,
                labels: {}, selected: {key: 'individual:0', title: 'Objective'},
                choices: Array.from({length: 6}, (_, i) => ({key: `individual:${i}`, title: i === 5 ? 'W'.repeat(120) : `${title} ${i}`})),
                criteria: [{label: 'Damage', target: 100, values: {official: '50', estimate: '30'}}], status: 'Online'};
            window.model = {model: {snapshot: JSON.stringify(payload), onAction: action => commands.push(action)}};
            window.card = new Function('api', script)({model, report: message => {throw new Error(message);}});
            window.update = patch => {Object.assign(payload, patch); model.model.snapshot = JSON.stringify(payload); tick();};
            window.rect = selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height};
            };
            window.scrolls = () => ['.BattleConquestGarage', '.BattleConquestGarage_content', '.BattleConquestGarage_column']
                .map(selector => document.querySelector(selector)?.scrollTop || 0);
        }, {script, language, scale});
        const card = page.locator('.BattleConquestGarage');
        const choose = card.locator('.BattleConquestGarage_choose');
        const options = page.getByRole('listbox');
        assert.equal(await card.locator('.BattleConquestGarage_content').evaluate(el => el.scrollHeight > el.clientHeight), false,
            'a normal objective uses available height without a nested text scroller');
        const before = await card.boundingBox();
        await choose.click();
        assert.equal(await options.evaluate(el => el.parentNode === document.body), true,
            'the popup escapes both card and shared-column clipping');
        assert.equal((await card.boundingBox()).height, before.height, 'opening the popup never resizes the card');
        const popup = await options.boundingBox();
        assert.ok(popup.x >= 0 && popup.x + popup.width <= width && popup.y >= 0 && popup.y + popup.height <= height);
        assert.equal(await options.evaluate(el => el.scrollWidth <= el.clientWidth), true, 'long titles wrap');
        const visible = await page.getByRole('option').evaluateAll(items => items.some(item => {
            const r = item.getBoundingClientRect(), menu = item.closest('[role="listbox"]').getBoundingClientRect();
            const card = document.querySelector('.BattleConquestGarage').getBoundingClientRect();
            const y = Math.max(r.top, menu.top) + Math.min(r.height, menu.bottom - Math.max(r.top, menu.top)) / 2;
            return y > card.bottom && y < menu.bottom && item.contains(document.elementFromPoint(r.left + 10, y));
        }));
        assert.equal(visible, true, 'options beyond the card remain above Unicum and the carousel');
        if (process.env.BC_GARAGE_SCREENSHOT && unicum && language === 'fr' && scale === 2) {
            await page.screenshot({path: process.env.BC_GARAGE_SCREENSHOT});
        }
        await page.getByRole('option').nth(2).click();
        assert.equal(await page.evaluate(() => commands.at(-1).selection), 'individual:1');
        assert.equal(await options.count(), 0);

        await page.evaluate(() => update({choices: Array.from({length: 50}, (_, i) =>
            ({key: `individual:${i}`, title: `Objective ${i}`}))}));
        await choose.click();
        assert.equal(await options.evaluate(el => el.scrollHeight > el.clientHeight), true);
        const scrolling = await page.evaluate(() => scrolls());
        for (const gameface of [false, true]) {
            await page.evaluate(gameface => {
                if (gameface) window.engine = {}; else delete window.engine;
                document.querySelector('[role="listbox"]').scrollTop = 0;
            }, gameface);
            await options.dispatchEvent('wheel', {deltaY: gameface ? -120 : 120, cancelable: true});
            assert.ok(await options.evaluate(el => el.scrollTop > 0), 'wheel down moves the list down');
            await options.dispatchEvent('wheel', {deltaY: gameface ? 120 : -120, cancelable: true});
            assert.equal(await options.evaluate(el => el.scrollTop), 0, 'wheel up moves the list up');
        }
        assert.deepEqual(await page.evaluate(() => scrolls()), scrolling, 'list scrolling never moves the cards');
        assert.equal(await page.evaluate(() => wheels), 0, 'wheel input never reaches the garage');
        await page.keyboard.press('ArrowUp');
        assert.equal(await page.getByRole('option').last().evaluate(el => el === document.activeElement), true);
        assert.ok(await options.evaluate(el => el.scrollTop > 0), 'keyboard navigation reveals the last choice');
        await page.keyboard.press('Escape');
        assert.equal(await choose.evaluate(el => el === document.activeElement), true);
        await choose.click();
        await page.mouse.click(1, 1);
        assert.equal(await options.count(), 0, 'outside click closes the detached menu');
        await choose.click();
        await page.keyboard.press('Tab');
        assert.equal(await options.count(), 0, 'Tab closes the menu and returns to the card tab order');
        assert.equal(await card.getByRole('button', {name: 'Details', exact: true})
            .evaluate(el => el === document.activeElement), true);

        await page.evaluate(() => {
            document.querySelector('.QuestCard_base_test').style.height = `${innerHeight - 350}px`;
            document.querySelector('.Page_carousel_test').style.display = 'none'; tick();
        });
        await choose.click();
        assert.ok(await options.evaluate(el => el.getBoundingClientRect().bottom
            <= document.querySelector('.BattleConquestGarage_choose').getBoundingClientRect().top),
            'a selector near the bottom opens upward');
        await page.keyboard.press('Escape');
        await page.evaluate(() => {
            document.querySelector('.QuestCard_base_test').style.height = '160px';
            document.querySelector('.Page_carousel_test').style.display = ''; tick();
            for (const el of document.querySelectorAll('.BattleConquestGarage, .BattleConquestGarage_content, .BattleConquestGarage_column')) el.scrollTop = 0;
        });

        await choose.click();
        await page.evaluate(() => update({busy: true}));
        assert.equal(await options.count(), 0, 'a busy snapshot closes the menu');
        await page.evaluate(() => update({busy: false}));
        await choose.click();
        await page.evaluate(() => update({scope: 'B'}));
        assert.equal(await options.count(), 0, 'an account/link scope change closes the menu');

        await page.evaluate(() => {
            delete window.engine;
            update({criteria: Array.from({length: 30}, () => payload.criteria[0])});
        });
        const content = card.locator('.BattleConquestGarage_content');
        const scrollTarget = await content.evaluate(el => el.scrollHeight > el.clientHeight) ? content : card;
        for (const gameface of [false, true]) {
            await page.evaluate(gameface => {
                if (gameface) window.engine = {}; else delete window.engine;
                for (const el of document.querySelectorAll('.BattleConquestGarage, .BattleConquestGarage_content, .BattleConquestGarage_column')) el.scrollTop = 0;
            }, gameface);
            await scrollTarget.dispatchEvent('wheel', {deltaY: gameface ? -120 : 120, cancelable: true});
            assert.ok(await page.evaluate(() => scrolls().some(top => top > 0)), 'overflowing content scrolls down naturally');
            await scrollTarget.dispatchEvent('wheel', {deltaY: gameface ? 120 : -120, cancelable: true});
            assert.deepEqual(await page.evaluate(() => scrolls()), [0, 0, 0]);
        }
        await choose.click();
        await page.evaluate(() => {card.stop(); tick();});
        assert.equal(await page.locator('.BattleConquestGarage_options').count(), 0, 'stop removes the popup');
        assert.equal(await page.locator('.BattleConquestGarage_column').count(), 0);
        assert.deepEqual(errors, []);
        scenarios++;
        await page.close();
    }
    console.log(`Garage picker: ${scenarios} resolution/language/Unicum scenarios passed, including native and Gameface wheel input`);
} finally { await browser.close(); }
