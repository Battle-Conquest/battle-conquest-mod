import {readFileSync} from 'node:fs';

const source = name => readFileSync(new URL(`../src/battle_conquest/web/hangar/${name}`, import.meta.url), 'utf8');
// Match Bridge.refresh: one reloadable script, with its scrolling helper first.
export const script = ['garage_scroll.js', 'garage.js'].map(source).join('\n');
export const css = source('garage.css');
