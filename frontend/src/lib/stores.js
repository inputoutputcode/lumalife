import { writable } from 'svelte/store';

export const appState = writable('upload');
// States: login, upload, processing, identify, tag, building, timeline, settings

export const currentUser = writable(null);
export const photos = writable([]);
export const clusters = writable([]);
export const targetPhotos = writable([]);
export const timelineData = writable(null);
export const stats = writable(null);
