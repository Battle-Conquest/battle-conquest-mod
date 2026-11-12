import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';

// Optional offline integration against an independent unicum.gg-mod checkout.
// The normal suite uses synthetic widgets; no upstream code is vendored here.
export async function checkUnicum(browser, script, css, reference) {
    const source = name => readFileSync(join(reference, 'src/unicum/web/hangar', name), 'utf8');
    const account = source('account_card.js').replace('__PANEL_ICONS__', '{}');
    const chat = source('twitch_panel.js').replace('__PANEL_ICONS__', '{}');
    const styles = source('account_card.css') + source('twitch_panel.css');
    for (const [width, height] of [[1280, 720], [1920, 1080], [2560, 1440]]) {
        const page = await browser.newPage({viewport: {width, height}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        try {
            await page.setContent(`<style>html {font-size:1px} body {margin:0}
                .QuestCard_base_test {position:absolute;top:40px;right:46px;width:319px;height:160px}
                .Page_carousel_test {position:absolute;top:${height - 160}px;left:0;right:0;height:160px;z-index:100}
                ${styles}${css}</style><div class="QuestCard_base_test"></div><div class="Page_carousel_test"></div>`);
            await page.evaluate(({script, account, chat}) => {
                const timers = new Map(), later = []; let next = 0;
                window.setInterval = fn => {timers.set(++next, fn); return next;};
                window.clearInterval = id => timers.delete(id);
                window.setTimeout = fn => {later.push(fn); return 0;};
                window.tickAll = () => {
                    for (const fn of Array.from(timers.values())) fn();
                    for (const fn of later.splice(0)) fn();
                };
                window.calls = [];
                window.data = {account: {linked: true, name: 'Tester'}, shown: true, channel: 'tester', linked: true,
                    messages: [], size: null, position: null};
                window.unicum = {model: {twitch: JSON.stringify(data), onItemClick: item => {
                    calls.push(item);
                    if (item.item === 'twitchMove') data.position = item.text ? item.text.split(',').map(Number) : null;
                    if (item.item === 'twitchResize') data.size = item.text ? item.text.split(',').map(Number) : null;
                    if (item.item === 'twitchCollapse') data.collapsed = item.text === '1';
                    unicum.model.twitch = JSON.stringify(data);
                }}};
                const report = message => {throw new Error(message);};
                window.accountCard = new Function('api', account)({model: unicum, report});
                window.chatPanel = new Function('api', chat)({model: unicum, report});
                const payload = {scope: 'A', shown: true, linked: true, has_data: true, labels: {}, choices: [], status: 'Online',
                    criteria: Array.from({length: 6}, () => ({label: 'Damage', target: 100, values: {official: '50', estimate: '30'}}))};
                window.bcModel = {model: {snapshot: JSON.stringify(payload), onAction: item => calls.push(item)}};
                window.startBC = () => {window.bc = new Function('api', script)({model: bcModel, report});};
                startBC();
                for (let i = 0; i < 50; i++) tickAll();
            }, {script, account, chat});
            const column = page.locator('.BattleConquestGarage_column');
            assert.equal(await column.count(), 1);
            assert.ok(await column.evaluate(el => el.getBoundingClientRect().bottom <= innerHeight - 176));
            await page.locator('.UnicumAccountCard_title').click();
            assert.equal(await page.evaluate(() => calls.at(-1).item), 'accountProfile');
            const input = page.locator('.UnicumTwitchPanel_input');
            await input.fill('draft to preserve');
            await page.evaluate(() => {bc.stop(); tickAll(); startBC(); tickAll();});
            assert.equal(await input.inputValue(), 'draft to preserve');
            assert.equal(await input.evaluate(el => document.activeElement === el), true);
            await input.press('Enter');
            assert.deepEqual(await page.evaluate(() => calls.filter(item => item.item === 'twitchSend').at(-1)),
                {item: 'twitchSend', text: 'draft to preserve'});
            // A complete drag between two BC polls must retain the intended
            // final coordinates; a timer-only release is too late at mouse-up.
            const header = page.locator('.UnicumTwitchPanel_heading');
            await header.scrollIntoViewIfNeeded();
            const before = await page.locator('.UnicumTwitchPanel').boundingBox();
            const handle = await header.boundingBox();
            await page.mouse.move(handle.x + 10, handle.y + 10);
            await page.mouse.down();
            await page.evaluate(() => {for (let i = 0; i < 5; i++) tickAll();});
            assert.equal(await page.locator('.UnicumTwitchPanel').evaluate(el => el.parentNode === document.body), true,
                'a held drag handle stays independent even before the first movement');
            await page.mouse.move(handle.x - 400, handle.y - 20, {steps: 4});
            await page.mouse.up();
            const moved = await page.evaluate(() => calls.filter(item => item.item === 'twitchMove').at(-1));
            assert.ok(moved, 'Unicum receives its drag command');
            assert.ok(Number(moved.text.split(',')[0]) < before.x - 100, JSON.stringify({before, moved}));
            await page.evaluate(() => tickAll());
            assert.equal(await page.locator('.UnicumTwitchPanel').evaluate(el => el.parentNode === document.body), true);
            await page.locator('.UnicumTwitchPanel_reset').click();
            await page.evaluate(() => {for (let i = 0; i < 20; i++) tickAll();});
            const grip = page.locator('.UnicumTwitchPanel_grip');
            await grip.hover();
            const sized = await page.locator('.UnicumTwitchPanel').boundingBox();
            const corner = await grip.boundingBox();
            await page.mouse.down();
            assert.equal(await page.evaluate(() => document.body.classList.contains('UnicumPanelResizing')), true);
            await page.evaluate(() => {for (let i = 0; i < 5; i++) tickAll();});
            await page.mouse.move(corner.x + 25, corner.y + 25, {steps: 4});
            await page.mouse.up();
            const resized = await page.evaluate(() => calls.filter(item => item.item === 'twitchResize' && item.text).at(-1));
            assert.ok(resized && Number(resized.text.split(',')[0]) > sized.width + 10, JSON.stringify({sized, resized}));
            await page.evaluate(() => tickAll());
            await page.evaluate(() => {bc.stop(); accountCard.stop(); chatPanel.stop(); tickAll();});
            assert.equal(await column.count(), 0);
            assert.equal(await page.locator('.UnicumAccountCard, .UnicumTwitchPanel').count(), 0);
            assert.deepEqual(errors, []);
        } finally { await page.close(); }
    }
    console.log('Unicum reference: three resolutions, timers, actions, draft/focus, held drag/resize and teardown passed');
}
