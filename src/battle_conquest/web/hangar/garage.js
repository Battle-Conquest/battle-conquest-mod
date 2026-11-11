// A Gameface card above other mods, driven only by the shared Python snapshot.
const { model, report } = api;
let alive = true, state = null, encoded = null, metricsKey = null, choicesKey = null;
let lastReady = 0;
const root = document.createElement('section');
root.className = 'BattleConquestGarage';
root.setAttribute('aria-label', 'Battle-Conquest');
root.style.display = 'none';
const externalStyle = document.createElement('style');
document.head.appendChild(externalStyle);

function node(tag, name, parent, text) {
    const item = document.createElement(tag);
    if (name) item.className = name;
    if (tag === 'button') {
        item.type = 'button';
        node('span', 'BattleConquestGarage_buttonText', item, text);
    } else if (text) item.textContent = text;
    parent.appendChild(item);
    return item;
}
function buttonText(button, text) { button.firstChild.textContent = text; }
const heading = node('div', 'BattleConquestGarage_heading', root);
node('strong', 'BattleConquestGarage_brand', heading, 'BC');
const title = node('strong', 'BattleConquestGarage_title', heading, 'Battle-Conquest');
const settings = node('button', 'BattleConquestGarage_settings', heading);
// The garage font does not reliably include the Unicode gear glyph.
const gear = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
gear.setAttribute('viewBox', '0 0 24 24');
gear.setAttribute('aria-hidden', 'true');
gear.setAttribute('focusable', 'false');
const gearShape = document.createElementNS('http://www.w3.org/2000/svg', 'path');
gearShape.setAttribute('d', 'M9 2h6l1 4 3-1 3 5-3 2 3 2-3 5-3-1-1 4H9l-1-4-3 1-3-5 3-2-3-2 3-5 3 1z M16 12a4 4 0 1 0-8 0 4 4 0 1 0 8 0');
// Use a literal fill: Gameface can render inherited control colours as black.
gearShape.setAttribute('fill', '#e6e2d8');
gearShape.setAttribute('fill-rule', 'evenodd');
gear.appendChild(gearShape);
settings.appendChild(gear);
const close = node('button', '', heading, '\u00d7');
const content = node('div', 'BattleConquestGarage_content', root);
const link = node('button', 'BattleConquestGarage_link', content);
const notice = node('p', '', content);
const selectedStatus = node('p', 'BattleConquestGarage_muted', content);
const picker = node('div', 'BattleConquestGarage_picker', content);
const choose = node('button', 'BattleConquestGarage_choose', picker);
choose.setAttribute('aria-haspopup', 'listbox');
choose.setAttribute('aria-expanded', 'false');
const options = node('div', 'BattleConquestGarage_options', picker);
options.setAttribute('role', 'listbox');
options.style.display = 'none';
const metrics = node('div', 'BattleConquestGarage_metrics', content);
const incomplete = node('p', 'BattleConquestGarage_muted', content);
const footer = node('div', 'BattleConquestGarage_footer', root);
const details = node('button', '', footer);
const reload = node('button', '', footer);
const status = node('p', 'BattleConquestGarage_status', root);
status.setAttribute('role', 'status');
status.setAttribute('aria-live', 'polite');
document.body.appendChild(root);

function label(key) { return state && state.labels[key] || key; }
function send(action, selection) {
    if (alive && state && model.model) {
        model.model.onAction({ action, selection: selection || '', scope: state.scope });
    }
}
function hideOptions() {
    options.style.display = 'none';
    choose.setAttribute('aria-expanded', 'false');
}
function action(button, callback) {
    button.addEventListener('click', (event) => {
        event.stopPropagation();
        if (!button.disabled) callback();
    });
}
action(close, () => { hideOptions(); root.style.display = 'none'; externalStyle.textContent = ''; send('close'); });
action(settings, () => send('settings'));
action(details, () => send('details'));
action(reload, () => send('reload'));
action(link, () => send(state.running ? 'cancel' : 'link'));
action(choose, () => {
    const open = options.style.display === 'none';
    options.style.display = open ? '' : 'none';
    choose.setAttribute('aria-expanded', String(open));
    if (open && options.firstChild) options.firstChild.focus();
});
function stop(event) { event.stopPropagation(); }
function keyboardMode() { root.classList.add('BattleConquestGarage__keyboard'); }
document.addEventListener('keydown', keyboardMode, true);
root.addEventListener('mousedown', (event) => {
    root.classList.remove('BattleConquestGarage__keyboard');
    stop(event);
});
root.addEventListener('wheel', stop);
function keyboard(event) {
    event.stopPropagation();
    if (event.key === 'Escape' || event.keyCode === 27) {
        hideOptions(); choose.focus(); event.preventDefault();
    } else if ((event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.keyCode === 38 || event.keyCode === 40)
            && picker.contains(event.target)) {
        const items = Array.from(options.children);
        let index = items.indexOf(document.activeElement);
        index = (index + ((event.key === 'ArrowUp' || event.keyCode === 38) ? -1 : 1) + items.length) % items.length;
        if (items[index]) {
            options.style.display = ''; choose.setAttribute('aria-expanded', 'true'); items[index].focus();
        }
        event.preventDefault();
    }
    if (typeof viewEnv !== 'undefined' && viewEnv.setEventHandled) viewEnv.setEventHandled();
}
root.addEventListener('keydown', keyboard);
root.addEventListener('keyup', stop);
function outside(event) { if (!root.contains(event.target)) hideOptions(); }
document.addEventListener('mousedown', outside);

function shown(item) {
    for (let current = item; current && current !== document.body; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    }
    return true;
}
const toRem = (px) => typeof viewEnv !== 'undefined' && viewEnv.pxToRem ? viewEnv.pxToRem(px) : px;
function placement() {
    if (root.style.display === 'none') { externalStyle.textContent = ''; return; }
    const cards = Array.from(document.querySelectorAll('[class*="QuestCard_base"], [class*="PersonalMissionCard_base"]'))
        .filter((item) => shown(item) && item.getBoundingClientRect().height > 0 && item.getBoundingClientRect().left > window.innerWidth / 2);
    let top = 180;
    if (cards.length) {
        top = Math.max(...cards.map((item) => item.getBoundingClientRect().bottom)) + 8;
        const rect = cards[0].getBoundingClientRect();
        root.style.right = `${Math.round(toRem(window.innerWidth - rect.right))}rem`;
        root.style.width = `${Math.round(toRem(rect.width))}rem`;
        // Borrow geometry only: the game's decor can remove our dark background.
    }
    root.style.top = `${Math.round(toRem(top))}rem`;
    const account = document.querySelector('.UnicumAccountCard');
    const chat = document.querySelector('.UnicumTwitchPanel:not(.UnicumTwitchPanel__windowed)');
    const accountHeight = account && shown(account) ? account.getBoundingClientRect().height + 8 : 0;
    const chatHeight = chat && shown(chat) ? chat.getBoundingClientRect().height + 8 : 0;
    root.style.maxHeight = `${Math.max(120, Math.floor(toRem(window.innerHeight - top - accountHeight - chatHeight - 16)))}rem`;
    const bottom = Math.round(toRem(root.getBoundingClientRect().bottom)) + 8;
    // An owned stylesheet overrides the other mod's periodic positioning;
    // removing it restores its own styles, without writing its saved settings.
    let css = account && shown(account) ? `.UnicumAccountCard { top: ${bottom}rem !important; }` : '';
    if (chat && shown(chat) && !chat.classList.contains('UnicumTwitchPanel__dragging')) {
        const aligned = Math.abs(chat.getBoundingClientRect().right - root.getBoundingClientRect().right) < 8;
        if (aligned) css += `.UnicumTwitchPanel:not(.UnicumTwitchPanel__windowed) { top: ${bottom + toRem(accountHeight)}rem !important; }`;
    }
    if (externalStyle.textContent !== css) externalStyle.textContent = css;
}

function render(data) {
    if (state && state.scope !== data.scope) { hideOptions(); metricsKey = choicesKey = null; }
    state = data;
    root.setAttribute('lang', data.language || 'en');
    root.style.display = data.shown ? '' : 'none';
    settings.setAttribute('aria-label', label('Settings')); settings.title = label('Settings');
    close.setAttribute('aria-label', label('Close')); close.title = label('Close');
    buttonText(link, label(data.running ? 'Cancel' : 'Link my account'));
    link.style.display = data.linked ? 'none' : '';
    notice.textContent = data.running ? label('Account: confirm in your browser') : '';
    notice.style.display = data.running ? '' : 'none';
    buttonText(choose, data.selected ? data.selected.title : label('Choose a quest'));
    choose.disabled = data.busy || data.blocked;
    choose.setAttribute('aria-label', label('Choose a quest'));
    picker.style.display = data.linked && data.has_data ? '' : 'none';
    selectedStatus.textContent = data.selected ? ((data.choices.find((row) => row.key === data.selected.key) || {}).status || '') : label('No active quest');
    selectedStatus.style.display = data.linked ? '' : 'none';
    buttonText(details, label('Details')); details.style.display = data.linked ? '' : 'none';
    buttonText(reload, label('Reload')); reload.disabled = data.busy;
    reload.style.display = data.linked ? '' : 'none';
    const choices = JSON.stringify([data.scope, data.choices, data.selected && data.selected.key, data.labels]);
    if (choices !== choicesKey) {
        const wasOpen = options.style.display !== 'none';
        while (options.firstChild) options.removeChild(options.firstChild);
        for (const row of [{key: '', title: label('Choose a quest')}].concat(data.choices)) {
            const button = node('button', '', options, row.title + (row.status ? ` — ${row.status}` : ''));
            button.setAttribute('role', 'option');
            button.setAttribute('aria-selected', String(Boolean(data.selected && row.key === data.selected.key)));
            action(button, () => { hideOptions(); choose.focus(); send('select', row.key); });
        }
        if (wasOpen) hideOptions();
        choicesKey = choices;
    }
    const metricKey = JSON.stringify([data.criteria, data.labels]);
    if (metricKey !== metricsKey) {
        while (metrics.firstChild) metrics.removeChild(metrics.firstChild);
        for (const criterion of data.criteria) {
            const row = node('div', 'BattleConquestGarage_metric', metrics);
            node('strong', '', row, `${criterion.label} / ${criterion.target}`);
            for (const source of ['official', 'estimate']) {
                node('div', 'BattleConquestGarage_' + source, row,
                    `${label(source === 'official' ? 'OFFICIAL' : 'MOD ESTIMATE')}: ${criterion.values[source]}`);
            }
        }
        metricsKey = metricKey;
    }
    metrics.style.display = data.linked ? '' : 'none';
    incomplete.textContent = data.incomplete ? data.incomplete_label : '';
    incomplete.style.display = data.incomplete && data.linked ? '' : 'none';
    status.textContent = data.status;
}
function poll() {
    if (!alive) return;
    try {
        const json = model.model && model.model.snapshot;
        if (json && json !== encoded) { render(JSON.parse(json)); encoded = json; }
        // Positioning beside another mod can fail independently of rendering.
        // Keep a live card's acknowledgement independent of that layout work.
        if (state && state.shown && root.style.display !== 'none' && Date.now() - lastReady > 1500) {
            send('ready'); lastReady = Date.now();
        }
    } catch (error) { report(`garage card: ${error}`); }
    try { placement(); } catch (error) { report(`garage card placement: ${error}`); }
}
const timer = setInterval(poll, 250);
poll();
return { stop() {
    alive = false; clearInterval(timer);
    document.removeEventListener('mousedown', outside);
    document.removeEventListener('keydown', keyboardMode, true);
    if (root.parentNode) root.parentNode.removeChild(root);
    if (externalStyle.parentNode) externalStyle.parentNode.removeChild(externalStyle);
} };
