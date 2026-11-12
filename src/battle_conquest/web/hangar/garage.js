// A Gameface card above visible Unicum widgets, driven by the shared Python snapshot.
const { model, report } = api;
let alive = true, state = null, encoded = null, metricsKey = null, choicesKey = null;
let lastReady = 0;
let layoutAvailable = true;
let heldChat = null;
const column = document.createElement('div');
column.className = 'BattleConquestGarage_column';
const parked = new Map();
column.addEventListener('mousedown', detachChat, true);
document.addEventListener('mouseup', releaseChat, true);
const root = document.createElement('section');
root.className = 'BattleConquestGarage';
root.setAttribute('aria-label', 'Battle-Conquest');
root.style.display = 'none';

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
action(close, () => { hideOptions(); root.style.display = 'none'; releaseColumn(); send('close'); });
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
function move(item, parent, before = null) {
    // Moving a live input can drop focus; keep Unicum's draft and keyboard use.
    const focused = item.contains(document.activeElement) ? document.activeElement : null;
    parent.insertBefore(item, before);
    if (focused && document.activeElement !== focused) focused.focus();
}
function restore(item) {
    const anchor = parked.get(item);
    if (item.parentNode === column && anchor.parentNode) move(item, anchor.parentNode, anchor);
    if (anchor.parentNode) anchor.parentNode.removeChild(anchor);
    parked.delete(item);
}
function detachChat(event) {
    // Unicum reads its viewport rectangle at mouse-down and commits the final
    // rectangle at mouse-up. Release before that sequence, even for a quick drag.
    for (const item of parked.keys()) {
        if (!item.classList.contains('UnicumTwitchPanel')) continue;
        for (const selector of ['.UnicumTwitchPanel_header', '.UnicumTwitchPanel_grip']) {
            const handle = item.querySelector(selector);
            if (handle && handle.contains(event.target)) { heldChat = item; restore(item); return; }
        }
    }
}
function releaseChat() { heldChat = null; }
function releaseColumn() {
    for (const item of Array.from(parked.keys())) restore(item);
    if (root.parentNode === column) move(root, document.body);
    if (column.parentNode) column.parentNode.removeChild(column);
}
function shareColumn(items, top, right, width, room) {
    for (const item of Array.from(parked.keys())) {
        if (!items.includes(item)) restore(item);
    }
    column.style.top = `${top}rem`;
    column.style.right = `${right}rem`;
    column.style.width = `${Math.max(width, ...items.map(item => toRem(item.getBoundingClientRect().width)))}rem`;
    column.style.maxHeight = `${room}rem`;
    if (!column.parentNode) document.body.appendChild(column);
    if (root.parentNode !== column) move(root, column, column.firstChild);
    items.forEach((item, index) => {
        if (!parked.has(item)) {
            const anchor = document.createComment('Battle-Conquest: original widget position');
            item.parentNode.insertBefore(anchor, item);
            parked.set(item, anchor);
        }
        const before = column.children[index + 1] || null;
        if (before !== item) move(item, column, before);
    });
}
function columnFloor() {
    const carousel = document.querySelector('[class*="Page_carousel"]');
    if (carousel && shown(carousel)) {
        const rect = carousel.getBoundingClientRect();
        if (rect.height > 0 && rect.top > 0) return Math.min(window.innerHeight, rect.top);
    }
    return window.innerHeight;
}
function placement() {
    if (root.style.display === 'none') { releaseColumn(); return; }
    const cards = Array.from(document.querySelectorAll('[class*="QuestCard_base"], [class*="PersonalMissionCard_base"]'))
        .filter((item) => shown(item) && item.getBoundingClientRect().height > 0 && item.getBoundingClientRect().left > window.innerWidth / 2);
    let top = 180, right = 46, width = 319;
    if (cards.length) {
        top = Math.max(...cards.map((item) => item.getBoundingClientRect().bottom)) + 8;
        const rect = cards[0].getBoundingClientRect();
        right = Math.round(toRem(window.innerWidth - rect.right));
        width = Math.round(toRem(rect.width));
        // Borrow geometry only: the game's decor can remove our dark background.
    }
    const topRem = Math.round(toRem(top));
    const room = Math.max(0, Math.floor(toRem(columnFloor() - 16) - topRem));
    // Only the shared column overrides geometry. Never write another mod's
    // inline styles or preferences; its own periodic layout keeps running.
    const items = Array.from(document.querySelectorAll('.UnicumAccountCard, .UnicumTwitchPanel:not(.UnicumTwitchPanel__windowed)')).filter(item => {
        if (!shown(item) || item === heldChat) return false;
        if (item.classList.contains('UnicumTwitchPanel')
                && (item.classList.contains('UnicumTwitchPanel__dragging') || (item.style.left && item.style.left !== 'auto'))) return false;
        const rect = item.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && toRem(rect.right) > toRem(window.innerWidth) - right - width
            && toRem(rect.left) < toRem(window.innerWidth) - right
            && (parked.has(item) || (rect.bottom > 0 && rect.top < window.innerHeight));
    }).sort((a, b) => Number(b.classList.contains('UnicumAccountCard')) - Number(a.classList.contains('UnicumAccountCard')));
    root.style.width = `${width}rem`;
    const style = getComputedStyle(root);
    const box = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
        + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
    layoutAvailable = room >= toRem(box + heading.getBoundingClientRect().height);
    root.style.visibility = layoutAvailable ? '' : 'hidden';
    if (items.length && layoutAvailable) {
        shareColumn(items, topRem, right, width, room);
        root.style.top = root.style.right = '';
    } else {
        releaseColumn();
        root.style.top = `${topRem}rem`;
        root.style.right = `${right}rem`;
    }
    const reserved = items.reduce((height, item) => height + toRem(item.getBoundingClientRect().height) + 8, 0);
    // When the cards cannot fit together, scroll the shared column rather
    // than pushing Unicum behind the carousel or out of the screen.
    const cardRoom = items.length ? Math.max(160, room - reserved) : room;
    root.style.maxHeight = `${cardRoom}rem`;
    // Keep the usual inner scroller while the controls and a useful content
    // viewport fit. In a short slot the whole card scrolls, including actions.
    let chrome = box;
    for (const item of [heading, footer, status]) {
        const part = getComputedStyle(item);
        if (part.display !== 'none') chrome += item.getBoundingClientRect().height
            + parseFloat(part.marginTop) + parseFloat(part.marginBottom);
    }
    const scrollCard = cardRoom < toRem(chrome) + 80;
    if (root.classList.contains('BattleConquestGarage__scrollCard') !== scrollCard) {
        root.classList.toggle('BattleConquestGarage__scrollCard', scrollCard);
        root.scrollTop = 0;
    }
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
    } catch (error) { report(`garage card: ${error}`); }
    try { placement(); } catch (error) {
        // A previous layout must never keep another mod displaced after a failure.
        releaseColumn();
        report(`garage card placement: ${error}`);
    }
    // A layout exception alone does not invalidate an otherwise live card.
    // A measured lack of room does: let the existing detailed fallback open.
    try {
        if (state && state.shown && layoutAvailable && root.style.display !== 'none' && Date.now() - lastReady > 1500) {
            send('ready'); lastReady = Date.now();
        }
    } catch (error) { report(`garage card: ${error}`); }
}
const timer = setInterval(poll, 250);
poll();
return { stop() {
    alive = false; clearInterval(timer);
    document.removeEventListener('mousedown', outside);
    document.removeEventListener('keydown', keyboardMode, true);
    releaseColumn();
    column.removeEventListener('mousedown', detachChat, true);
    document.removeEventListener('mouseup', releaseChat, true);
    heldChat = null;
    if (root.parentNode) root.parentNode.removeChild(root);
} };
