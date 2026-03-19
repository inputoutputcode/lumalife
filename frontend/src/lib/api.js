const API_BASE = '/api';

async function request(method, path, body = null) {
	const opts = {
		method,
		headers: {},
	};

	if (body && !(body instanceof FormData)) {
		opts.headers['Content-Type'] = 'application/json';
		opts.body = JSON.stringify(body);
	} else if (body instanceof FormData) {
		opts.body = body;
	}

	const res = await fetch(`${API_BASE}${path}`, opts);
	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: res.statusText }));
		throw new Error(err.detail || `Request failed: ${res.status}`);
	}
	return res.json();
}

export const api = {
	// Upload
	uploadPhotos(files) {
		const formData = new FormData();
		for (const file of files) {
			formData.append('files', file);
		}
		return request('POST', '/photos/upload', formData);
	},

	listPhotos() {
		return request('GET', '/photos/list');
	},

	// Processing
	startProcessing() {
		return request('POST', '/photos/process');
	},

	processStream() {
		return new EventSource(`${API_BASE}/photos/process/stream`);
	},

	getClusters() {
		return request('GET', '/photos/clusters');
	},

	confirmCluster(clusterId) {
		return request('POST', `/photos/clusters/${clusterId}/confirm`);
	},

	estimateAges() {
		return request('POST', '/photos/estimate-ages');
	},

	// Tagging
	getTargetPhotos() {
		return request('GET', '/photos/target-photos');
	},

	tagPhoto(photoId, year) {
		return request('POST', `/photos/${photoId}/tag`, { year });
	},

	untagPhoto(photoId) {
		return request('DELETE', `/photos/${photoId}/tag`);
	},

	// Timeline
	getTimeline() {
		return request('GET', '/timeline');
	},

	rebuildTimeline() {
		return request('POST', '/timeline/rebuild');
	},

	// Data management
	deleteAllData() {
		return request('DELETE', '/data/all');
	},

	reprocess() {
		return request('POST', '/data/reprocess');
	},

	exportData() {
		return request('GET', '/data/export');
	},

	getStats() {
		return request('GET', '/data/stats');
	},

	health() {
		return request('GET', '/health');
	},
};
