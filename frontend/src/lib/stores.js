import { writable } from 'svelte/store';

export const appState = writable('upload');
// States: upload, processing, identify, tag, building, timeline

export const photos = writable([]);
export const clusters = writable([]);
export const targetPhotos = writable([]);
export const timelineData = writable(null);
export const stats = writable(null);
