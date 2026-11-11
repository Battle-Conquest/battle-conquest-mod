import assert from 'node:assert/strict';

// Exercise the shipped script against changing DOM geometry, without depending
// on the other mod being installed or on its timer's order relative to ours.
export async function checkPlacement(browser, script, css) {
    let scenarios = 0;
    for (const native of [true, false]) for (const language of ['en', 'fr'])
        for (const [width, height, scale] of [[1280, 720, 1], [1920, 1080, 1], [2560, 1440, 2]]) {
        const page = await browser.newPage({viewport: {width, height}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.setContent(`<style>html {font-size:${scale}px} body {margin:0}
            .QuestCard_base_test {position:absolute;top:40px;right:46rem;width:319rem;height:160px}
            .UnicumAccountCard {position:absolute;top:208px;right:46rem;width:319rem;height:55px}
            .UnicumTwitchPanel {position:absolute;top:271px;right:46rem;width:319rem;height:140px}
            ${css}</style>${native ? '<div class="QuestCard_base_test"></div>' : ''}`);
        await page.evaluate(({script, scale, language}) => {
            window.commands = [];
            window.viewEnv = {pxToRem: px => px / scale};
            window.setInterval = callback => {window.tick = callback; return 1;};
            window.clearInterval = () => {};
            const title = language === 'fr' ? 'Un objectif très long avec accents et plusieurs conditions ' : 'A long objective with several conditions ';
            window.payload = {scope: 'A', language, shown: true, linked: true, running: false,
                labels: language === 'fr' ? {Details: 'Détails', Reload: 'Actualiser', Settings: 'Réglages', Close: 'Fermer'} : {},
                has_data: true, selected: {key: 'individual:1', title: title.repeat(4)},
                choices: [{key: 'individual:1', title: title.repeat(4)}],
                criteria: Array.from({length: 8}, () => ({label: title.repeat(3), target: 100,
                    values: {official: '20 + ?', estimate: 'Unavailable'}})), status: title.repeat(3)};
            window.model = {model: {snapshot: JSON.stringify(payload), onAction: action => commands.push(action)}};
            window.script = script;
            window.start = () => {window.card = new Function('api', script)({model, report: message => {throw new Error(message);}});};
            window.update = patch => {Object.assign(payload, patch); model.model.snapshot = JSON.stringify(payload); tick();};
            window.add = (name, parent = document.body) => {
                const item = document.createElement('div'); item.className = name; parent.appendChild(item); return item;
            };
            window.rect = selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width};
            };
            start();
        }, {script, scale, language});
        const geometry = () => page.evaluate(() => rect('.BattleConquestGarage'));
        const baseline = await geometry();
        assert.equal(baseline.top, native ? Math.round(208 / scale) * scale : 180);
        // Installed but disabled: a hidden ancestor and individually hidden
        // nodes must be indistinguishable from the absent mod.
        await page.evaluate(() => {
            const parent = add('disabled-mod'); parent.style.display = 'none';
            add('UnicumAccountCard', parent); add('UnicumTwitchPanel', parent); tick();
        });
        assert.deepEqual(await geometry(), baseline);
        await page.evaluate(() => document.querySelector('.disabled-mod').remove());
        await page.evaluate(() => {add('UnicumAccountCard'); add('UnicumTwitchPanel'); tick();});
        const placed = await geometry();
        assert.equal(placed.top, Math.round(411 / scale) * scale + 8 * scale);
        assert.ok(placed.bottom <= height - 16);
        assert.equal(placed.right, baseline.right);
        await page.evaluate(() => {for (let i = 0; i < 100; i++) tick();});
        assert.deepEqual(await geometry(), placed, 'placement does not drift');
        await page.evaluate(() => {document.querySelector('.UnicumAccountCard').style.display = 'none'; tick();});
        assert.deepEqual(await geometry(), placed, 'a visible chat still reserves its own space without the account card');
        await page.evaluate(() => {document.querySelector('.UnicumAccountCard').style.display = ''; tick();});
        for (const [property, value] of [['display', 'none'], ['visibility', 'hidden'], ['opacity', '0']]) {
            await page.evaluate(({property, value}) => {
                for (const item of document.querySelectorAll('.UnicumAccountCard, .UnicumTwitchPanel')) item.style[property] = value;
                tick();
            }, {property, value});
            assert.deepEqual(await geometry(), baseline);
            await page.evaluate(property => {
                for (const item of document.querySelectorAll('.UnicumAccountCard, .UnicumTwitchPanel')) item.style[property] = '';
                tick();
            }, property);
            assert.deepEqual(await geometry(), placed);
        }
        await page.evaluate(() => {document.querySelector('.UnicumTwitchPanel').style.height = '163px'; tick();});
        assert.equal((await geometry()).top, Math.round(434 / scale) * scale + 8 * scale);
        await page.setViewportSize({width: width + 100, height: height + 100});
        await page.evaluate(() => tick());
        assert.equal((await geometry()).right, placed.right + 100, 'the column follows a resized viewport');
        assert.ok((await geometry()).bottom <= height + 100 - 16);
        await page.setViewportSize({width, height});
        await page.evaluate(() => {document.querySelector('.UnicumTwitchPanel').style.height = ''; tick();});
        assert.deepEqual(await geometry(), placed);
        await page.evaluate(() => {document.querySelector('.UnicumTwitchPanel').classList.add('UnicumTwitchPanel__windowed'); tick();});
        assert.equal((await geometry()).top, Math.round(263 / scale) * scale + 8 * scale);
        await page.evaluate(() => {
            const chat = document.querySelector('.UnicumTwitchPanel'); chat.classList.remove('UnicumTwitchPanel__windowed');
            chat.style.right = 'auto'; chat.style.left = '0'; tick();
        });
        assert.equal((await geometry()).top, Math.round(263 / scale) * scale + 8 * scale, 'a chat outside the column reserves no space');
        await page.evaluate(() => {
            const chat = document.querySelector('.UnicumTwitchPanel'); chat.style.left = ''; chat.style.right = '';
            chat.style.height = '0'; tick();
        });
        assert.equal((await geometry()).top, Math.round(263 / scale) * scale + 8 * scale);
        // Leave less room than the pinned controls need, including with long
        // status text. The footer must still be reachable in the same column.
        const foreign = await page.evaluate(({height, scale}) => {
            const chat = document.querySelector('.UnicumTwitchPanel');
            chat.style.height = `${height - 90 - 8 * scale - 271}px`; tick();
            return Array.from(document.querySelectorAll('.UnicumAccountCard, .UnicumTwitchPanel'), item => item.outerHTML);
        }, {height, scale});
        const card = page.locator('.BattleConquestGarage');
        assert.equal(await card.evaluate(el => el.classList.contains('BattleConquestGarage__scrollCard')), true);
        assert.ok((await geometry()).bottom <= height - 16);
        await card.hover();
        await page.mouse.wheel(0, 5000);
        await page.waitForFunction(() => document.querySelector('.BattleConquestGarage').scrollTop > 0);
        const reload = card.getByRole('button', {name: language === 'fr' ? 'Actualiser' : 'Reload', exact: true});
        await reload.scrollIntoViewIfNeeded();
        await reload.click();
        assert.equal(await page.evaluate(() => commands.at(-1).action), 'reload');
        await reload.focus();
        await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => commands.at(-1).action), 'reload');
        await page.evaluate(() => {for (let i = 0; i < 100; i++) tick();});
        assert.deepEqual(await page.evaluate(() => Array.from(document.querySelectorAll('.UnicumAccountCard, .UnicumTwitchPanel'), item => item.outerHTML)), foreign);
        await card.getByRole('button', {name: language === 'fr' ? 'Fermer' : 'Close', exact: true}).click();
        assert.equal(await card.isVisible(), false);
        await page.evaluate(() => update({status: 'Restored', shown: true}));
        assert.equal(await card.isVisible(), true);
        await page.evaluate(() => {
            document.querySelector('.UnicumTwitchPanel').remove(); document.querySelector('.UnicumAccountCard').remove();
            update({status: 'Online'});
        });
        assert.equal((await geometry()).top, baseline.top);
        const returned = await geometry();
        await page.evaluate(() => {update({shown: false}); update({shown: true}); card.stop(); start();});
        assert.deepEqual(await geometry(), returned, 'returning to the garage and reloading do not retain offsets');
        if (native) {
            await page.evaluate(() => {document.querySelector('.QuestCard_base_test').style.width = '241rem'; tick();});
            assert.equal((await geometry()).width, 241 * scale);
            await page.evaluate(() => {document.querySelector('.QuestCard_base_test').remove(); tick();});
            assert.equal((await geometry()).width, 319 * scale, 'default geometry is restored after native cards disappear');
        }
        await page.setViewportSize({width: width + 100, height: height + 100});
        await page.evaluate(() => tick());
        assert.ok((await geometry()).bottom <= height + 100);
        await page.evaluate(() => card.stop());
        assert.equal(await card.count(), 0);
        assert.deepEqual(errors, []);
        scenarios++;
        await page.close();
    }
    return scenarios;
}
