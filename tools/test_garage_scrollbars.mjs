import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {script, css} from './garage_card_sources.mjs';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.BC_PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({headless: true});
let scenarios = 0;
try {
    for (const gameface of [false, true])
        for (const [width, height, scale] of [[1280, 720, 1], [1920, 1080, 1], [2560, 1440, 1], [2560, 1440, 2]]) {
        const page = await browser.newPage({viewport: {width, height}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.setContent(`<style>html {font-size:${scale}px} body {margin:0}
            .QuestCard_base_test {position:absolute;top:40px;right:46rem;width:319rem;height:160px}
            .UnicumAccountCard {position:absolute;top:208px;right:46rem;width:319rem;height:100rem}
            .UnicumTwitchPanel {position:absolute;top:316px;right:46rem;width:319rem;height:400rem}
            .Page_carousel_test {position:absolute;top:${height - 160}px;left:0;right:0;height:160px;z-index:100}
            ${css}</style><div class="QuestCard_base_test"></div><div class="Page_carousel_test"></div>
            <div class="UnicumAccountCard">Account</div><div class="UnicumTwitchPanel">Twitch</div>`);
        await page.evaluate(({script, scale, gameface}) => {
            window.commands = []; window.handled = 0; window.wheels = 0;
            document.addEventListener('wheel', () => wheels++);
            if (gameface) window.engine = {};
            window.viewEnv = {pxToRem: px => px / scale, setEventHandled: () => handled++};
            window.setInterval = callback => {window.tick = callback; return 1;};
            window.clearInterval = () => {};
            window.payload = {scope: 'A', shown: true, linked: true, has_data: true,
                labels: {Scroll: 'Défilement'}, selected: {key: 'individual:1', title: 'Objective'},
                choices: Array.from({length: 50}, (_, i) => ({key: `individual:${i}`, title: `Objective ${i}`})),
                criteria: Array.from({length: 20}, () => ({label: 'Damage', target: 100, values: {official: '50', estimate: '30'}})),
                status: 'Online'};
            window.model = {model: {snapshot: JSON.stringify(payload), onAction: action => commands.push(action)}};
            window.start = () => {window.card = new Function('api', script)({model, report: message => {throw new Error(message);}});};
            window.update = patch => {Object.assign(payload, patch); model.model.snapshot = JSON.stringify(payload); tick();};
            window.resetScroll = () => {
                for (const item of document.querySelectorAll('.BattleConquestGarage, .BattleConquestGarage_content, .BattleConquestGarage_column')) item.scrollTop = 0;
                tick();
            };
            start();
        }, {script, scale, gameface});
        const column = page.locator('.BattleConquestGarage_column');
        const content = page.locator('.BattleConquestGarage_content');
        const card = page.locator('.BattleConquestGarage');
        const barFor = async viewport => page.locator(`[role="scrollbar"][aria-controls="${await viewport.getAttribute('id')}"]`);
        const outer = await barFor(column);
        const inner = await barFor(content);
        assert.equal(await outer.isVisible(), true, 'the shared column exposes its scroll range');
        assert.equal(await inner.isVisible(), true, 'overflowing card text has a visible scrollbar');
        if (process.env.BC_GARAGE_SCREENSHOT && gameface && scale === 2) {
            await page.screenshot({path: process.env.BC_GARAGE_SCREENSHOT});
        }
        assert.equal(await outer.getAttribute('aria-label'), 'Défilement');
        assert.ok(await outer.evaluate(el => el.getBoundingClientRect().width <= 7.1 * parseFloat(getComputedStyle(document.documentElement).fontSize)),
            'the track stays discreet at every interface scale');

        await content.dispatchEvent('wheel', {deltaY: gameface ? -120 : 120, cancelable: true});
        assert.equal(await content.evaluate(el => el.scrollTop),
            await content.evaluate(el => Math.min(240, el.scrollHeight - el.clientHeight)),
            'inner card text uses the same doubled wheel speed');
        assert.equal(await column.evaluate(el => el.scrollTop), 0);
        await page.evaluate(() => resetScroll());

        // This event originates in the column gap, outside the BC card.
        await column.dispatchEvent('wheel', {deltaY: gameface ? -120 : 120, cancelable: true});
        assert.equal(await column.evaluate(el => el.scrollTop),
            await column.evaluate(el => Math.min(240, el.scrollHeight - el.clientHeight)),
            'one wheel movement covers twice its former distance in shared space');
        assert.equal(await content.evaluate(el => el.scrollTop), 0, 'the shared wheel never moves inner text');
        assert.ok(Number(await outer.getAttribute('aria-valuenow')) > 0);
        await column.dispatchEvent('wheel', {deltaY: gameface ? 120 : -120, cancelable: true});
        assert.equal(await column.evaluate(el => el.scrollTop), 0, 'wheel up in shared space moves up');
        await page.locator('.UnicumAccountCard').dispatchEvent('wheel', {deltaY: gameface ? -120 : 120, cancelable: true});
        assert.ok(await column.evaluate(el => el.scrollTop > 0), 'non-scrolling widgets use the shared column');
        assert.equal(await page.evaluate(() => wheels), 0, 'shared wheel input never zooms the garage');
        await page.evaluate(() => resetScroll());
        await column.dispatchEvent('wheel', {deltaY: gameface ? -1 : 1, deltaMode: 1, cancelable: true});
        assert.equal(await column.evaluate(el => el.scrollTop),
            await column.evaluate((el, scale) => Math.min(64 * scale, el.scrollHeight - el.clientHeight), scale),
            'line-based wheel input is doubled after interface scaling');
        await page.evaluate(() => resetScroll());

        await outer.focus();
        await page.keyboard.press('ArrowDown');
        assert.equal(await column.evaluate(el => el.scrollTop), 32 * scale, 'keyboard scrolling retains its normal step');
        await page.keyboard.press('Home');
        await page.keyboard.press('End');
        assert.equal(await column.evaluate(el => el.scrollTop), await column.evaluate(el => el.scrollHeight - el.clientHeight));
        await page.keyboard.press('Home');
        assert.equal(await column.evaluate(el => el.scrollTop), 0);
        const thumb = outer.locator('.BattleConquestGarage_scrollThumb');
        const handle = await thumb.boundingBox(), track = await outer.boundingBox();
        await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
        await page.mouse.down();
        await page.mouse.move(track.x + track.width / 2, track.y + track.height - 1, {steps: 4});
        await page.mouse.up();
        assert.ok(await column.evaluate(el => el.scrollTop > (el.scrollHeight - el.clientHeight) * .8), 'the scrollbar thumb can be dragged');
        const released = await column.evaluate(el => el.scrollTop);
        await page.mouse.move(1, 1);
        assert.equal(await column.evaluate(el => el.scrollTop), released, 'release ends dragging outside the track');
        await page.evaluate(() => resetScroll());

        // A foreign chat viewport keeps its own native/default wheel handling.
        const foreign = await page.evaluate(delta => {
            const chat = document.querySelector('.UnicumTwitchPanel');
            const nested = document.createElement('div');
            nested.style.cssText = 'height:40px;overflow-y:auto';
            nested.innerHTML = '<div style="height:400px">Chat text</div>'; chat.appendChild(nested);
            const event = new WheelEvent('wheel', {deltaY: delta, bubbles: true, cancelable: true});
            nested.firstChild.dispatchEvent(event);
            const prevented = event.defaultPrevented; nested.remove();
            return {prevented, column: document.querySelector('.BattleConquestGarage_column').scrollTop};
        }, gameface ? -120 : 120);
        assert.deepEqual(foreign, {prevented: false, column: 0});

        await card.locator('.BattleConquestGarage_choose').click();
        await page.evaluate(() => tick());
        const options = page.getByRole('listbox');
        const popupBar = await barFor(options);
        assert.equal(await popupBar.isVisible(), true);
        assert.equal(await page.getByRole('scrollbar').count(), 1, 'only the popup scrollbar stays above the open menu');
        await popupBar.dispatchEvent('wheel', {deltaY: gameface ? -120 : 120, cancelable: true});
        assert.equal(await options.evaluate(el => el.scrollTop),
            await options.evaluate(el => Math.min(240, el.scrollHeight - el.clientHeight)),
            'the popup uses the same doubled wheel speed');
        assert.equal(await column.evaluate(el => el.scrollTop), 0);
        await popupBar.click({position: {x: 3 * scale, y: 20 * scale}});
        assert.equal(await options.isVisible(), true, 'using the popup scrollbar does not dismiss its menu');
        await page.keyboard.press('Escape');
        assert.equal(await options.count(), 0);

        await page.evaluate(() => {
            document.querySelector('.Page_carousel_test').style.display = 'none';
            document.querySelector('.QuestCard_base_test').style.height = `${innerHeight - 200}px`; tick();
        });
        const whole = await barFor(card);
        assert.equal(await whole.isVisible(), true, 'short slots expose the whole-card scrollbar');
        await card.dispatchEvent('wheel', {deltaY: gameface ? -120 : 120, cancelable: true});
        assert.equal(await card.evaluate(el => el.scrollTop),
            await card.evaluate(el => Math.min(240, el.scrollHeight - el.clientHeight)),
            'whole-card scrolling uses the same doubled speed');

        await page.evaluate(() => {
            document.querySelector('.QuestCard_base_test').style.height = '160px';
            document.querySelector('.Page_carousel_test').style.display = '';
            for (const item of document.querySelectorAll('.UnicumAccountCard, .UnicumTwitchPanel')) item.style.display = 'none';
            update({criteria: [payload.criteria[0]]}); resetScroll();
        });
        assert.equal(await page.getByRole('scrollbar').count(), 0, 'no track is shown when everything fits');
        await page.evaluate(() => {
            update({shown: false});
            window.oldRoot = document.querySelector('.BattleConquestGarage');
            card.stop(); tick();
        });
        assert.equal(await page.locator('.BattleConquestGarage_scrollbar').count(), 0, 'stop removes every scrollbar');
        const handled = await page.evaluate(() => handled);
        await page.evaluate(() => oldRoot.dispatchEvent(new WheelEvent('wheel', {deltaY: 120, bubbles: true, cancelable: true})));
        assert.equal(await page.evaluate(() => handled), handled, 'a removed card cannot retain wheel handling');
        await page.evaluate(() => {payload.shown = true; model.model.snapshot = JSON.stringify(payload); start();});
        assert.equal(await page.locator('.BattleConquestGarage_scrollbar').count(), 4, 'reload creates one track per owned viewport');
        await page.evaluate(() => card.stop());
        assert.equal(await page.locator('.BattleConquestGarage_scrollbar').count(), 0);
        assert.deepEqual(errors, []);
        scenarios++;
        await page.close();
    }
    console.log(`Garage scrollbars: ${scenarios} resolution/scale/wheel scenarios passed, including shared gaps, dragging, foreign chat and teardown`);
} finally { await browser.close(); }
