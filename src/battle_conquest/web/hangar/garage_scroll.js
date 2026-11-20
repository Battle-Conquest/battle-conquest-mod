// Gameface scrolls overflow but does not draw native scrollbars.
function createGarageScrolling({root, content, column, options, toRem, shown, placeOptions, label, dismissOptions}) {
    let alive = true, drag = null;
    const sources = [root, content, column, options];
    const wheelSources = [root, column, options];
    const pixels = rem => rem / toRem(1);
    const entries = sources.map((viewport, index) => {
        if (!viewport.id) viewport.id = `BattleConquestGarage_scroll_${index}`;
        const track = document.createElement('div');
        track.className = 'BattleConquestGarage_scrollbar';
        track.style.display = 'none'; track.tabIndex = 0;
        track.setAttribute('role', 'scrollbar');
        track.setAttribute('aria-controls', viewport.id);
        track.setAttribute('aria-orientation', 'vertical');
        track.setAttribute('aria-valuemin', '0');
        const thumb = document.createElement('div');
        thumb.className = 'BattleConquestGarage_scrollThumb';
        track.appendChild(thumb); document.body.appendChild(track);
        const entry = {viewport, track, thumb};
        track.addEventListener('mousedown', event => startDrag(event, entry));
        track.addEventListener('wheel', event => wheel(event, viewport), {passive: false});
        track.addEventListener('keydown', event => keyboard(event, entry));
        return entry;
    });

    function scrollable(item) {
        const overflow = getComputedStyle(item).overflowY;
        return (overflow === 'auto' || overflow === 'scroll') && item.scrollHeight > item.clientHeight + 1;
    }
    function refresh() {
        if (!alive) return;
        const menu = options.style.display !== 'none';
        for (const entry of entries) {
            const {viewport, track, thumb} = entry;
            let visible = document.body.contains(viewport) && shown(viewport) && scrollable(viewport)
                && (!menu || viewport === options);
            if (visible) {
                const rect = viewport.getBoundingClientRect();
                let top = Math.max(0, rect.top), bottom = Math.min(innerHeight, rect.bottom);
                for (let parent = viewport.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
                    if (getComputedStyle(parent).overflowY === 'visible') continue;
                    const clip = parent.getBoundingClientRect();
                    top = Math.max(top, clip.top); bottom = Math.min(bottom, clip.bottom);
                }
                const height = bottom - top - pixels(4);
                visible = height >= pixels(12) && rect.width > 0;
                if (visible) {
                    const left = rect.right + pixels(viewport === column ? 2 : viewport === content ? 2 : -8);
                    const range = viewport.scrollHeight - viewport.clientHeight;
                    const size = Math.min(height * .8, Math.max(pixels(18), height * viewport.clientHeight / viewport.scrollHeight));
                    track.style.left = `${toRem(left)}rem`; track.style.top = `${toRem(top + pixels(2))}rem`;
                    track.style.height = `${toRem(height)}rem`;
                    thumb.style.height = `${toRem(size)}rem`;
                    thumb.style.top = `${toRem((height - size) * viewport.scrollTop / range)}rem`;
                    track.setAttribute('aria-label', label('Scroll'));
                    track.setAttribute('aria-valuemax', String(range));
                    track.setAttribute('aria-valuenow', String(Math.round(viewport.scrollTop)));
                }
            }
            track.style.display = visible ? '' : 'none';
            if (!visible && drag && drag.entry === entry) endDrag();
        }
    }
    function changed() { if (alive) { placeOptions(); refresh(); } }
    function handled(event) {
        event.stopPropagation(); event.preventDefault();
        if (typeof viewEnv !== 'undefined' && viewEnv.setEventHandled) viewEnv.setEventHandled();
    }
    function wheel(event, start = event.target) {
        if (!alive || event.defaultPrevented) return;
        // Foreign chat scrollers keep their own input. Bare column space and
        // non-scrolling widgets use the owned column, like the card does.
        for (let item = start; item && item !== document.body; item = item.parentElement) {
            if (sources.includes(item)) break;
            if (item.nodeType === 1 && scrollable(item)) return;
        }
        handled(event);
        let delta = Number(event.deltaY) || 0;
        if (typeof engine !== 'undefined') delta = -delta;
        if (!delta) delta = -(Number(event.wheelDelta) || 0);
        if (event.deltaMode === 1 || (typeof engine !== 'undefined' && Math.abs(delta) <= 1)) delta *= pixels(32);
        else if (event.deltaMode === 2) delta *= root.clientHeight;
        delta *= 2;
        for (let item = start; item && item !== document.body; item = item.parentElement) {
            if (!sources.includes(item) || !scrollable(item)) continue;
            const before = item.scrollTop;
            item.scrollTop = Math.max(0, Math.min(item.scrollHeight - item.clientHeight, before + delta));
            if (item.scrollTop !== before || item === options) break;
        }
        changed();
    }
    function startDrag(event, entry) {
        if (!alive || event.button !== 0) return;
        handled(event); entry.track.focus();
        const thumb = entry.thumb.getBoundingClientRect();
        drag = {entry, offset: event.target === entry.thumb ? event.clientY - thumb.top : thumb.height / 2};
        entry.track.classList.add('BattleConquestGarage_scrollbar__dragging');
        moveDrag(event);
    }
    function moveDrag(event) {
        if (!alive || !drag) return;
        handled(event);
        const {viewport, track, thumb} = drag.entry;
        const rect = track.getBoundingClientRect(), travel = rect.height - thumb.getBoundingClientRect().height;
        if (travel > 0) viewport.scrollTop = Math.max(0, Math.min(1, (event.clientY - rect.top - drag.offset) / travel))
            * (viewport.scrollHeight - viewport.clientHeight);
        changed();
    }
    function endDrag() {
        if (drag) drag.entry.track.classList.remove('BattleConquestGarage_scrollbar__dragging');
        drag = null;
    }
    function keyboard(event, {viewport}) {
        if (!alive) return;
        if (viewport === options && ['Escape', 'Tab'].includes(event.key)) {
            dismissOptions(); refresh();
            if (event.key === 'Escape') handled(event);
            return;
        }
        const range = viewport.scrollHeight - viewport.clientHeight;
        const positions = {ArrowDown: viewport.scrollTop + pixels(32), ArrowUp: viewport.scrollTop - pixels(32),
            PageDown: viewport.scrollTop + viewport.clientHeight, PageUp: viewport.scrollTop - viewport.clientHeight,
            Home: 0, End: range};
        if (!(event.key in positions)) return;
        handled(event); viewport.scrollTop = Math.max(0, Math.min(range, positions[event.key])); changed();
    }
    for (const viewport of sources) viewport.addEventListener('scroll', changed);
    for (const viewport of wheelSources) viewport.addEventListener('wheel', wheel, {passive: false});
    document.addEventListener('mousemove', moveDrag, true);
    document.addEventListener('mouseup', endDrag, true);
    return {refresh, stop() {
        alive = false; endDrag();
        for (const viewport of sources) viewport.removeEventListener('scroll', changed);
        for (const viewport of wheelSources) viewport.removeEventListener('wheel', wheel);
        document.removeEventListener('mousemove', moveDrag, true);
        document.removeEventListener('mouseup', endDrag, true);
        for (const {track} of entries) if (track.parentNode) track.parentNode.removeChild(track);
    }};
}
