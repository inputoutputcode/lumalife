<script>
	import { onMount, onDestroy } from 'svelte';
	import { api } from '$lib/api.js';
	import TimelineSection from '../components/TimelineSection.svelte';
	import MiniMap from '../components/MiniMap.svelte';

	let { onManage } = $props();
	let timelineData = $state(null);
	let loading = $state(true);
	let error = $state(null);
	let selectedPhoto = $state(null);
	let showManage = $state(false);
	let deleting = $state(false);
	let reprocessing = $state(false);
	let activeEra = $state(0);

	async function loadTimeline() {
		loading = true;
		error = null;
		try {
			timelineData = await api.getTimeline();
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		loadTimeline();
	});

	function selectPhoto(photo) {
		selectedPhoto = photo;
	}

	function closeDetail() {
		selectedPhoto = null;
	}

	async function deleteAll() {
		if (!confirm('Delete ALL data? This cannot be undone.')) return;
		deleting = true;
		try {
			await api.deleteAllData();
			onManage();
		} catch (e) {
			error = e.message;
		} finally {
			deleting = false;
		}
	}

	async function reprocess() {
		reprocessing = true;
		try {
			await api.reprocess();
			onManage();
		} catch (e) {
			error = e.message;
		} finally {
			reprocessing = false;
		}
	}

	async function exportData() {
		try {
			const data = await api.exportData();
			const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = 'lumalife-export.json';
			a.click();
			URL.revokeObjectURL(url);
		} catch (e) {
			error = e.message;
		}
	}

	function handleEraChange(index) {
		activeEra = index;
	}

	function scrollToEra(index) {
		const el = document.getElementById(`era-${index}`);
		if (el) {
			el.scrollIntoView({ behavior: 'smooth', block: 'start' });
		}
	}
</script>

<div class="timeline-page">
	{#if loading}
		<div class="loading">
			<div class="spinner"></div>
			<p>Loading your timeline...</p>
		</div>
	{:else if error}
		<div class="error-view">
			<p>{error}</p>
			<button class="btn-secondary" onclick={loadTimeline}>Retry</button>
		</div>
	{:else if timelineData && timelineData.eras && timelineData.eras.length > 0}
		<div class="timeline-header">
			<h2>Your Timeline</h2>
			<p class="timeline-subtitle">{timelineData.total_photos} photos across {timelineData.eras.length} eras</p>
		</div>
		<div class="timeline-container">
			<div class="timeline-spine-line"></div>
			{#each timelineData.eras as era, i}
				<div id="era-{i}">
					<TimelineSection
						{era}
						index={i}
						onPhotoClick={selectPhoto}
						onVisible={() => handleEraChange(i)}
					/>
				</div>
			{/each}
		</div>
	{:else}
		<div class="empty-timeline">
			<h2>No Timeline Yet</h2>
			<p>Upload photos and tag them with years to build your timeline.</p>
			<button class="btn-primary" onclick={onManage}>Upload Photos</button>
		</div>
	{/if}

	{#if selectedPhoto}
		<!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
		<div class="photo-detail-overlay" onclick={closeDetail} onkeydown={(e) => e.key === 'Escape' && closeDetail()}>
			<!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
			<div class="photo-detail-card" onclick={(e) => e.stopPropagation()}>
				<button class="close-btn" aria-label="Close" onclick={closeDetail}>
					<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
					</svg>
				</button>
				<img src={selectedPhoto.url} alt={selectedPhoto.original_filename || 'Detail view'} class="detail-image" />
				<div class="detail-info">
					<h3>
						{#if selectedPhoto.tagged_year}
							{selectedPhoto.tagged_year}
						{:else if selectedPhoto.estimated_year}
							~{selectedPhoto.estimated_year}
						{/if}
					</h3>
					<p class="detail-filename">{selectedPhoto.original_filename}</p>
					{#if selectedPhoto.estimated_year && !selectedPhoto.tagged_year}
						<p class="detail-estimate">Estimated year based on age analysis</p>
					{/if}
					{#if selectedPhoto.tagged_year}
						<p class="detail-tagged">User-confirmed year</p>
					{/if}
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.timeline-page {
		min-height: 100vh;
	}

	.loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 60vh;
	}

	.loading p {
		color: var(--text-secondary);
		margin-top: 16px;
	}

	.spinner {
		width: 40px;
		height: 40px;
		border: 3px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.error-view {
		text-align: center;
		padding: 60px 24px;
	}

	.error-view p {
		color: var(--danger);
		margin-bottom: 16px;
	}

	.timeline-header {
		text-align: center;
		padding: 60px 24px 40px;
	}

	.timeline-header h2 {
		font-size: 2.5rem;
		color: var(--accent);
		margin-bottom: 8px;
	}

	.timeline-subtitle {
		color: var(--text-secondary);
		font-size: 1rem;
		margin-bottom: 20px;
	}

	.timeline-actions {
		display: flex;
		justify-content: center;
		gap: 12px;
	}

	.manage-panel {
		max-width: 600px;
		margin: 0 auto 32px;
		padding: 20px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
	}

	.manage-actions {
		display: flex;
		gap: 12px;
		justify-content: center;
		flex-wrap: wrap;
	}

	.timeline-container {
		position: relative;
		max-width: 1200px;
		margin: 0 auto;
		padding-left: 60px;
	}

	.timeline-spine-line {
		position: absolute;
		left: 30px;
		top: -200px;
		bottom: 0;
		width: 2px;
		background: var(--accent);
		z-index: 0;
	}

	.empty-timeline {
		text-align: center;
		padding: 100px 24px;
	}

	.empty-timeline h2 {
		font-size: 2rem;
		color: var(--text-secondary);
		margin-bottom: 12px;
	}

	.empty-timeline p {
		color: var(--text-muted);
		margin-bottom: 24px;
	}

	.manage-section-empty {
		margin-top: 40px;
	}

	.manage-panel.inline {
		margin-top: 16px;
		display: flex;
		gap: 12px;
		justify-content: center;
		flex-wrap: wrap;
		padding: 16px;
	}

	.photo-detail-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.9);
		z-index: 1000;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 40px;
	}

	.photo-detail-card {
		max-width: 900px;
		max-height: 90vh;
		position: relative;
		display: flex;
		flex-direction: column;
	}

	.close-btn {
		position: absolute;
		top: -40px;
		right: 0;
		background: none;
		color: var(--text-secondary);
		padding: 8px;
	}

	.close-btn:hover {
		color: var(--text-primary);
	}

	.detail-image {
		max-width: 100%;
		max-height: 70vh;
		object-fit: contain;
		border-radius: var(--radius);
	}

	.detail-info {
		padding: 20px 0;
		text-align: center;
	}

	.detail-info h3 {
		font-size: 1.8rem;
		color: var(--accent);
		margin-bottom: 8px;
	}

	.detail-filename {
		color: var(--text-muted);
		font-size: 0.85rem;
		margin-bottom: 4px;
	}

	.detail-estimate {
		color: var(--text-secondary);
		font-size: 0.85rem;
		font-style: italic;
	}

	.detail-tagged {
		color: var(--success);
		font-size: 0.85rem;
	}
</style>
