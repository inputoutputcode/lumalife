<script>
	import { api } from '$lib/api.js';
	import { photos } from '$lib/stores.js';
	import PhotoGrid from '../components/PhotoGrid.svelte';

	let { onProcess } = $props();
	let fileInput = $state(null);
	let uploading = $state(false);
	let uploadResult = $state(null);
	let photoList = $state([]);
	let dragOver = $state(false);
	let error = $state(null);
	let pendingFiles = $state([]);
	let uploadProgress = $state(0);
	let uploadTotal = $state(0);

	async function loadPhotos() {
		try {
			const data = await api.listPhotos();
			photoList = data.photos;
			photos.set(data.photos);
		} catch {
			// fresh state
		}
	}

	$effect(() => {
		loadPhotos();
	});

	function createThumbnail(file) {
		return new Promise((resolve) => {
			const reader = new FileReader();
			reader.onload = (e) => resolve(e.target.result);
			reader.readAsDataURL(file);
		});
	}

	async function handleFiles(files) {
		if (!files || files.length === 0) return;

		const imageFiles = Array.from(files).filter((f) => f.type.startsWith('image/'));
		if (imageFiles.length === 0) {
			error = 'No valid image files selected';
			return;
		}

		if (imageFiles.length > 100) {
			error = 'Maximum 100 files allowed';
			return;
		}

		// Build preview thumbnails
		pendingFiles = imageFiles.map((f) => ({
			name: f.name,
			size: f.size,
			thumbnail: null,
			status: 'pending' // pending | uploading | done | error
		}));

		// Generate thumbnails in parallel
		const thumbPromises = imageFiles.map(async (f, i) => {
			const thumb = await createThumbnail(f);
			pendingFiles[i] = { ...pendingFiles[i], thumbnail: thumb };
			pendingFiles = [...pendingFiles]; // trigger reactivity
		});
		// Don't await all — start upload while thumbs load
		Promise.all(thumbPromises);

		uploading = true;
		uploadProgress = 0;
		uploadTotal = imageFiles.length;
		error = null;
		uploadResult = null;

		// Mark all as uploading
		pendingFiles = pendingFiles.map((f) => ({ ...f, status: 'uploading' }));

		try {
			const result = await api.uploadPhotos(imageFiles);
			uploadResult = result;
			uploadProgress = imageFiles.length;
			pendingFiles = pendingFiles.map((f) => ({ ...f, status: 'done' }));
			await loadPhotos();
		} catch (e) {
			error = e.message;
			pendingFiles = pendingFiles.map((f) =>
				f.status === 'uploading' ? { ...f, status: 'error' } : f
			);
		} finally {
			uploading = false;
		}
	}

	function onFileSelect(e) {
		handleFiles(e.target.files);
	}

	function onDrop(e) {
		e.preventDefault();
		dragOver = false;
		handleFiles(e.dataTransfer.files);
	}

	function onDragOver(e) {
		e.preventDefault();
		dragOver = true;
	}

	function onDragLeave() {
		dragOver = false;
	}

	async function deleteAll() {
		if (!confirm('Delete all photos and data? This cannot be undone.')) return;
		try {
			await api.deleteAllData();
			photoList = [];
			photos.set([]);
			uploadResult = null;
			pendingFiles = [];
			error = null;
		} catch (e) {
			error = e.message;
		}
	}
</script>

<div class="upload-page">
	<div class="upload-hero">
		<h2>Your Life, Illuminated</h2>
		<p class="subtitle">Upload your photos and we'll build a timeline of your journey through time.</p>
	</div>

	<div
		class="drop-zone"
		class:drag-over={dragOver}
		class:has-photos={photoList.length > 0}
		ondrop={onDrop}
		ondragover={onDragOver}
		ondragleave={onDragLeave}
		role="button"
		tabindex="0"
		onclick={() => fileInput?.click()}
		onkeydown={(e) => e.key === 'Enter' && fileInput?.click()}
	>
		{#if uploading}
			<div class="upload-progress-info">
				<div class="upload-spinner"></div>
				<p class="upload-status-text">Uploading {uploadTotal} photo{uploadTotal !== 1 ? 's' : ''}...</p>
				<div class="progress-bar-track">
					<div class="progress-bar-fill" style="width: {uploadTotal > 0 ? (uploadProgress / uploadTotal) * 100 : 0}%"></div>
				</div>
			</div>
		{:else if photoList.length > 0}
			<div class="drop-compact">
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
					<polyline points="17 8 12 3 7 8" />
					<line x1="12" y1="3" x2="12" y2="15" />
				</svg>
				<span>Drop photos here or click to add more</span>
			</div>
		{:else}
			<div class="drop-icon">
				<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
					<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
					<polyline points="17 8 12 3 7 8" />
					<line x1="12" y1="3" x2="12" y2="15" />
				</svg>
			</div>
			<p class="drop-text">Drop photos here or click to browse</p>
			<p class="drop-hint">Up to 100 photos, 20MB each. JPEG, PNG, WebP, HEIC.</p>
		{/if}
	</div>

	<input
		bind:this={fileInput}
		type="file"
		accept="image/*"
		multiple
		onchange={onFileSelect}
		style="display: none"
	/>

	{#if pendingFiles.length > 0 && (uploading || !uploadResult)}
		<div class="pending-grid">
			{#each pendingFiles as file}
				<div class="pending-thumb" class:done={file.status === 'done'} class:error={file.status === 'error'}>
					{#if file.thumbnail}
						<img src={file.thumbnail} alt={file.name} />
					{:else}
						<div class="thumb-placeholder"></div>
					{/if}
					<div class="thumb-overlay">
						{#if file.status === 'uploading'}
							<div class="mini-spinner"></div>
						{:else if file.status === 'done'}
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2ecc71" stroke-width="2.5"><polyline points="20 6 9 17 4 12" /></svg>
						{:else if file.status === 'error'}
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#e74c3c" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
						{/if}
					</div>
					<p class="thumb-name">{file.name.length > 12 ? file.name.slice(0, 10) + '…' : file.name}</p>
				</div>
			{/each}
		</div>
	{/if}

	{#if error}
		<div class="upload-error">
			<p>{error}</p>
		</div>
	{/if}

	{#if uploadResult}
		<div class="upload-result">
			<p>
				Uploaded <strong>{uploadResult.uploaded}</strong> photo{uploadResult.uploaded !== 1 ? 's' : ''}
				{#if uploadResult.errors > 0}
					<span class="error-count">({uploadResult.errors} failed)</span>
				{/if}
			</p>
		</div>
	{/if}

	{#if photoList.length > 0}
		<div class="photo-section">
			<div class="section-header">
				<h3>{photoList.length} photo{photoList.length !== 1 ? 's' : ''} uploaded</h3>
				<button class="btn-primary" onclick={onProcess} disabled={uploading}>
					Process Photos
				</button>
			</div>
			<PhotoGrid photos={photoList} onUpdate={loadPhotos} />
		</div>
	{/if}
</div>

<style>
	.upload-page {
		max-width: 1000px;
		margin: 0 auto;
		padding: 40px 24px 80px;
	}

	.upload-hero {
		text-align: center;
		margin-bottom: 40px;
	}

	.upload-hero h2 {
		font-size: 2.5rem;
		color: var(--accent);
		margin-bottom: 12px;
	}

	.subtitle {
		color: var(--text-secondary);
		font-size: 1.1rem;
		max-width: 500px;
		margin: 0 auto;
	}

	.drop-zone {
		border: 2px dashed var(--border);
		border-radius: var(--radius-lg);
		padding: 60px 40px;
		text-align: center;
		cursor: pointer;
		transition: all var(--transition);
		background: var(--bg-secondary);
	}

	.drop-zone.has-photos {
		padding: 12px 20px;
	}

	.drop-compact {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		color: var(--text-muted);
		font-size: 0.9rem;
	}

	.drop-zone:hover,
	.drop-zone.drag-over {
		border-color: var(--accent);
		background: var(--accent-glow);
	}

	.drop-icon {
		color: var(--text-muted);
		margin-bottom: 16px;
	}

	.drop-text {
		font-size: 1.1rem;
		margin-bottom: 8px;
	}

	.drop-hint {
		color: var(--text-muted);
		font-size: 0.85rem;
	}

	.upload-spinner {
		width: 32px;
		height: 32px;
		border: 3px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		margin: 0 auto 16px;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.upload-error {
		margin-top: 16px;
		padding: 12px 20px;
		background: rgba(231, 76, 60, 0.1);
		border: 1px solid var(--danger);
		border-radius: var(--radius);
	}

	.upload-error p {
		color: var(--danger);
		font-size: 0.9rem;
	}

	.upload-result {
		margin-top: 16px;
		padding: 12px 20px;
		background: rgba(46, 204, 113, 0.1);
		border: 1px solid var(--success);
		border-radius: var(--radius);
	}

	.upload-result p {
		color: var(--success);
		font-size: 0.9rem;
	}

	.error-count {
		color: var(--danger);
	}

	.photo-section {
		margin-top: 48px;
	}

	.section-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 24px;
	}

	.section-actions {
		display: flex;
		gap: 10px;
		align-items: center;
	}

	.section-header h3 {
		font-family: var(--font-sans);
		font-size: 1rem;
		color: var(--text-secondary);
		font-weight: 500;
	}

	.upload-progress-info {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
	}

	.upload-status-text {
		font-weight: 500;
		color: var(--text-primary);
	}

	.progress-bar-track {
		width: 240px;
		height: 6px;
		background: var(--border);
		border-radius: 3px;
		overflow: hidden;
	}

	.progress-bar-fill {
		height: 100%;
		background: var(--accent);
		border-radius: 3px;
		transition: width 0.3s ease;
	}

	.pending-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
		gap: 10px;
		margin-top: 24px;
		padding: 0 4px;
	}

	.pending-thumb {
		position: relative;
		aspect-ratio: 1;
		border-radius: var(--radius);
		overflow: hidden;
		background: var(--bg-secondary);
		border: 2px solid var(--border);
		transition: border-color 0.3s ease;
	}

	.pending-thumb.done {
		border-color: var(--success);
	}

	.pending-thumb.error {
		border-color: var(--danger);
	}

	.pending-thumb img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.thumb-placeholder {
		width: 100%;
		height: 100%;
		background: var(--bg-hover);
		animation: pulse 1.2s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 0.5; }
		50% { opacity: 1; }
	}

	.thumb-overlay {
		position: absolute;
		top: 4px;
		right: 4px;
		width: 24px;
		height: 24px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(255, 255, 255, 0.85);
		border-radius: 50%;
	}

	.mini-spinner {
		width: 14px;
		height: 14px;
		border: 2px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.thumb-name {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		padding: 2px 4px;
		font-size: 0.65rem;
		color: #fff;
		background: rgba(0, 0, 0, 0.55);
		text-align: center;
		white-space: nowrap;
		overflow: hidden;
	}
</style>
