import assert from 'node:assert/strict';

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
            .UnicumAccountCard, .UnicumTwitchPanel {display:flex;flex-direction:column;justify-content:flex-end}
            ${css}</style>${native ? '<div class="QuestCard_base_test"></div>' : ''}`);
        await page.evaluate(({script, scale, language}) => {
            window.commands = [];
            window.viewEnv = {pxToRem: px => px / scale};
            window.setInterval = callback => {window.tick = callback; return 1;};
            window.clearInterval = () => {};
            const title = language === 'fr' ? 'Un objectif très long avec accents et plusieurs conditions ' : 'A long objective with several conditions ';
            window.payload = {scope: 'A', language, shown: true, linked: true, has_data: true,
                labels: language === 'fr' ? {Reload: 'Actualiser', Close: 'Fermer'} : {}, choices: [],
                selected: {key: 'individual:1', title: title.repeat(4)},
                criteria: Array.from({length: 8}, () => ({label: title.repeat(3), target: 100,
                    values: {official: '20 + ?', estimate: 'Unavailable'}})), status: title.repeat(3)};
            window.model = {model: {snapshot: JSON.stringify(payload), onAction: action => commands.push(action)}};
            window.start = () => {window.card = new Function('api', script)({model, report: message => {throw new Error(message);}});};
            window.update = patch => {Object.assign(payload, patch); model.model.snapshot = JSON.stringify(payload); tick();};
            window.add = (name, parent = document.body) => {
                const item = document.createElement('div'); item.className = name;
                const button = document.createElement('button'); button.textContent = name;
                button.onclick = () => commands.push({action: name}); item.appendChild(button);
                parent.appendChild(item); return item;
            };
            window.rect = selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width};
            };
            start();
        }, {script, scale, language});
        const card = page.locator('.BattleConquestGarage');
        const geometry = () => page.evaluate(() => rect('.BattleConquestGarage'));
        const baseline = await geometry();
        assert.equal(baseline.top, native ? Math.round(208 / scale) * scale : 180);
        await page.evaluate(() => {
            const parent = add('disabled-mod'); parent.style.display = 'none';
            add('UnicumAccountCard', parent); add('UnicumTwitchPanel', parent); tick();
        });
        assert.deepEqual(await geometry(), baseline);
        assert.equal(await page.locator('.BattleConquestGarage_column').count(), 0);
        await page.evaluate(() => document.querySelector('.disabled-mod').remove());
        await page.evaluate(() => {add('UnicumAccountCard'); add('UnicumTwitchPanel'); tick();});
        const placed = await geometry();
        assert.equal(placed.top, baseline.top);
        assert.equal(placed.right, baseline.right);
        assert.equal(await page.evaluate(() => Array.from(document.querySelector('.BattleConquestGarage_column').children)
            .map(item => item.className.split(' ')[0]).join(',')), 'BattleConquestGarage,UnicumAccountCard,UnicumTwitchPanel');
        await page.evaluate(() => {for (let i = 0; i < 100; i++) tick();});
        assert.deepEqual(await geometry(), placed, 'placement does not drift');
        for (const [property, value] of [['display', 'none'], ['visibility', 'hidden'], ['opacity', '0']]) {
            await page.evaluate(({property, value}) => {
                for (const item of document.querySelectorAll('.UnicumAccountCard, .UnicumTwitchPanel')) item.style[property] = value;
                tick();
            }, {property, value});
            assert.deepEqual(await geometry(), baseline);
            assert.equal(await page.locator('.BattleConquestGarage_column').count(), 0);
            await page.evaluate(property => {
                for (const item of document.querySelectorAll('.UnicumAccountCard, .UnicumTwitchPanel')) item.style[property] = '';
                tick();
            }, property);
            assert.deepEqual(await geometry(), placed);
        }
        const styles = await page.evaluate(() => {
            document.querySelector('.UnicumAccountCard').style.top = '208rem';
            document.querySelector('.UnicumTwitchPanel').style.top = '271rem'; tick();
            return Array.from(document.querySelectorAll('.UnicumAccountCard, .UnicumTwitchPanel'), item => item.getAttribute('style'));
        });
        await page.setViewportSize({width: width + 100, height: height + 100});
        await page.evaluate(() => tick());
        assert.equal((await geometry()).right, placed.right + 100);
        await page.setViewportSize({width, height});
        await page.evaluate(() => tick());
        // Even a chat taller than the viewport stays usable in the shared column.
        await page.evaluate(({height, scale}) => {
            document.querySelector('.UnicumTwitchPanel').style.height = `${height / scale}rem`; tick();
        }, {height, scale});
        const column = page.locator('.BattleConquestGarage_column');
        assert.equal(await column.evaluate(el => el.scrollHeight > el.clientHeight), true);
        assert.ok(await column.evaluate(el => el.getBoundingClientRect().bottom <= innerHeight - 16));
        await page.getByRole('button', {name: 'UnicumTwitchPanel', exact: true}).click();
        assert.equal(await page.evaluate(() => commands.at(-1).action), 'UnicumTwitchPanel');
        await card.getByRole('button', {name: language === 'fr' ? 'Actualiser' : 'Reload', exact: true}).click();
        assert.equal(await page.evaluate(() => commands.at(-1).action), 'reload');
        await page.evaluate(() => {
            const chat = document.querySelector('.UnicumTwitchPanel');
            chat.style.height = ''; chat.classList.add('UnicumTwitchPanel__windowed'); tick();
        });
        assert.equal(await page.locator('.UnicumTwitchPanel').evaluate(el => el.parentNode === document.body), true);
        await page.evaluate(() => {
            const chat = document.querySelector('.UnicumTwitchPanel');
            chat.classList.remove('UnicumTwitchPanel__windowed'); chat.style.left = '20rem'; tick();
        });
        assert.equal(await page.locator('.UnicumTwitchPanel').evaluate(el => el.parentNode === document.body), true);
        await page.evaluate(() => {document.querySelector('.UnicumTwitchPanel').style.left = ''; tick();});
        assert.equal(await page.locator('.UnicumTwitchPanel').evaluate(el => el.parentNode.className), 'BattleConquestGarage_column');
        await card.getByRole('button', {name: language === 'fr' ? 'Fermer' : 'Close', exact: true}).click();
        assert.equal(await column.count(), 0);
        assert.equal(await card.isVisible(), false);
        assert.deepEqual(await page.evaluate(() => Array.from(document.querySelectorAll('.UnicumAccountCard, .UnicumTwitchPanel'), item => item.getAttribute('style'))), styles);
        await page.evaluate(() => update({shown: true, status: 'Restored'}));
        assert.equal(await column.count(), 1);
        // Foreign teardown must not resurrect a widget when our column stops.
        await page.evaluate(() => {document.querySelector('.UnicumAccountCard').remove(); tick(); card.stop();});
        assert.equal(await page.locator('.UnicumAccountCard').count(), 0);
        assert.equal(await page.locator('.UnicumTwitchPanel').evaluate(el => el.parentNode === document.body), true);
        assert.equal(await column.count(), 0);
        await page.evaluate(() => {document.querySelector('.UnicumTwitchPanel').remove(); start();});
        assert.equal((await geometry()).top, baseline.top);
        if (native) {
            await page.evaluate(() => {document.querySelector('.QuestCard_base_test').style.width = '241rem'; tick();});
            assert.equal((await geometry()).width, 241 * scale);
            await page.evaluate(() => {document.querySelector('.QuestCard_base_test').remove(); tick();});
            assert.equal((await geometry()).width, 319 * scale);
        }
        await page.evaluate(() => card.stop());
        assert.deepEqual(errors, []);
        scenarios++;
        await page.close();
    }
    return scenarios;
}
