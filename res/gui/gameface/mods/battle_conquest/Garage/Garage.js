// Stable loader. Reloadable card resources arrive through the Python model.
import { ModelObserver } from '../../libs/model.js';
const model = ModelObserver('BattleConquestGarage');
const style = document.createElement('style');
let running = null, revision = null;
function report(message) {
    // Logs stay local; no UI command can choose a URL or execute Python code.
    if (typeof console !== 'undefined') console.warn(message);
}
function load() {
    const current = model.model;
    if (!current || current.revision === revision) return;
    revision = current.revision;
    if (running) { running.stop(); running = null; }
    style.textContent = current.revision ? current.style : '';
    if (!current.revision || !current.script) return;
    try { running = new Function('api', current.script)({ model, report }); }
    catch (error) { report(`Battle-Conquest garage load failed: ${error}`); }
}
engine.whenReady.then(() => {
    document.head.appendChild(style);
    model.onUpdate(load); model.subscribe(); load();
});
