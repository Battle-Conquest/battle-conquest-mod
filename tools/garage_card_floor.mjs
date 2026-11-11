import assert from 'node:assert/strict';

export async function checkFloor(browser, script, css) {
    const page = await browser.newPage({viewport: {width: 1280, height: 720}});
    try {
        await page.setContent(`<style>html {font-size:1px} body {margin:0}
            .QuestCard_base_test {position:absolute;top:40px;right:46px;width:319px;height:160px}
            .UnicumAccountCard {position:absolute;top:208px;right:46px;width:319px;height:55px}
            .UnicumTwitchPanel {position:absolute;top:271px;right:46px;width:319px;height:140px}
            .Page_carousel_test {position:absolute;top:560px;left:0;right:0;height:160px;z-index:100}
            ${css}</style><div class="QuestCard_base_test"></div><div class="UnicumAccountCard"></div>
            <div class="UnicumTwitchPanel"></div><div class="Page_carousel_test"></div>`);
        await page.evaluate(script => {
            window.setInterval = fn => {window.tick = fn; return 1;};
            window.clearInterval = () => {};
            window.commands = [];
            window.payload = {scope: 'A', shown: true, linked: true, has_data: true, labels: {}, choices: [],
                criteria: Array.from({length: 6}, () => ({label: 'Damage', target: 100, values: {official: '50', estimate: '30'}})),
                status: 'Online'};
            window.model = {model: {snapshot: JSON.stringify(payload), onAction: action => commands.push(action)}};
            window.card = new Function('api', script)({model, report: message => {throw new Error(message);}});
        }, script);
        const card = page.locator('.BattleConquestGarage');
        assert.equal(await card.evaluate(el => el.getBoundingClientRect().top), 419);
        assert.ok(await card.evaluate(el => el.getBoundingClientRect().bottom <= 544), 'the carousel is outside the usable column');
        const reload = card.getByRole('button', {name: 'Reload', exact: true});
        await reload.scrollIntoViewIfNeeded();
        assert.equal(await reload.evaluate(el => {
            const r = el.getBoundingClientRect();
            return el.contains(document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2));
        }), true, 'the carousel cannot intercept the card actions');
        await reload.click();
        assert.equal(await page.evaluate(() => commands.at(-1).action), 'reload');
        await page.evaluate(() => {document.querySelector('.Page_carousel_test').style.display = 'none'; tick();});
        assert.ok(await card.evaluate(el => el.getBoundingClientRect().bottom > 544), 'a hidden carousel reserves no space');
        await page.evaluate(() => card.stop());
    } finally { await page.close(); }
}
