<script>
	import { api } from '$lib/api.js';
	import { onMount } from 'svelte';
	import AccuracyMeter from '../components/AccuracyMeter.svelte';

	let { onNext } = $props();
	let targetData = $state(null);
	let loading = $state(true);
	let error = $state(null);
	let estimatingAges = $state(false);
	let buildingTimeline = $state(false);
	let editingPhotoId = $state(null);
	let yearInput = $state('');
	let monthInput = $state('');
	let lightboxPhoto = $state(null);
	let selectedIds = $state(new Set());
	let bulkYear = $state('');
	let bulkMonth = $state('');
	let bulkMode = $state(false);
	let showBuildDialog = $state(false);

	async function loadTargetPhotos() {
		loading = true;
		try {
			targetData = await api.getTargetPhotos();
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadTargetPhotos();
	});

	async function tagPhoto(photoId) {
		const year = parseInt(yearInput, 10);
		if (isNaN(year) || year < 1900 || year > 2030) return;
		const month = monthInput ? parseInt(monthInput, 10) : null;
		try {
			await api.tagPhoto(photoId, year, month);
			if (targetData) {
				const photo = targetData.photos.find(p => p.id === photoId);
				if (photo) {
					const wasUntagged = !photo.tagged_year;
					photo.tagged_year = year;
					photo.tagged_month = month;
					if (wasUntagged) targetData.tagged_count = (targetData.tagged_count || 0) + 1;
					targetData = { ...targetData };
				}
			}
			editingPhotoId = null;
			yearInput = '';
			monthInput = '';
		} catch (e) {
			error = e.message;
		}
	}

	async function bulkTag() {
		const year = parseInt(bulkYear, 10);
		if (isNaN(year) || year < 1900 || year > 2030 || selectedIds.size === 0) return;
		const month = bulkMonth ? parseInt(bulkMonth, 10) : null;
		try {
			for (const id of selectedIds) {
				await api.tagPhoto(id, year, month);
				if (targetData) {
					const photo = targetData.photos.find(p => p.id === id);
					if (photo) {
						const wasUntagged = !photo.tagged_year;
						photo.tagged_year = year;
						photo.tagged_month = month;
						if (wasUntagged) targetData.tagged_count = (targetData.tagged_count || 0) + 1;
					}
				}
			}
			targetData = { ...targetData };
			selectedIds = new Set();
			bulkYear = '';
			bulkMonth = '';
			bulkMode = false;
		} catch (e) {
			error = e.message;
		}
	}

	function toggleSelect(photoId) {
		const next = new Set(selectedIds);
		if (next.has(photoId)) next.delete(photoId);
		else next.add(photoId);
		selectedIds = next;
	}

	function startEditing(photoId, existingYear, existingMonth) {
		editingPhotoId = photoId;
		yearInput = existingYear ? String(existingYear) : '';
		monthInput = existingMonth ? String(existingMonth) : '';
		setTimeout(() => {
			const el = document.querySelector('.year-input');
			if (el) el.focus();
		}, 0);
	}

	function handleClickOutside(e) {
		if (editingPhotoId && !e.target.closest('.tag-input-row') && !e.target.closest('.btn-secondary') && !e.target.closest('.btn-edit')) {
			editingPhotoId = null;
			yearInput = '';
			monthInput = '';
		}
	}

	// Lightbox
	let lightboxIndex = $derived(
		lightboxPhoto && targetData ? targetData.photos.findIndex(p => p.id === lightboxPhoto.id) : -1
	);

	function openLightbox(photo) {
		if (bulkMode) {
			toggleSelect(photo.id);
			return;
		}
		lightboxPhoto = photo;
	}

	function closeLightbox() { lightboxPhoto = null; }

	function navigateLightbox(dir) {
		if (!targetData || lightboxIndex < 0) return;
		const next = lightboxIndex + dir;
		if (next >= 0 && next < targetData.photos.length) {
			lightboxPhoto = targetData.photos[next];
		}
	}

	function handleKeys(e) {
		if (lightboxPhoto) {
			if (e.key === 'Escape') closeLightbox();
			else if (e.key === 'ArrowLeft') navigateLightbox(-1);
			else if (e.key === 'ArrowRight') navigateLightbox(1);
		}
	}

	onMount(() => {
		document.addEventListener('click', handleClickOutside);
		document.addEventListener('keydown', handleKeys);
		return () => {
			document.removeEventListener('click', handleClickOutside);
			document.removeEventListener('keydown', handleKeys);
		};
	});

	function getUntaggedCount() {
		if (!targetData) return 0;
		return targetData.photos.filter(p => !p.tagged_year).length;
	}

	function requestBuildTimeline() {
		const untagged = getUntaggedCount();
		if (untagged > 0) {
			showBuildDialog = true;
		} else {
			buildTimeline();
		}
	}

	async function buildTimeline() {
		showBuildDialog = false;
		error = null;
		estimatingAges = true;
		try {
			await api.estimateAges();
			estimatingAges = false;
			buildingTimeline = true;
			await api.rebuildTimeline();
			buildingTimeline = false;
			onNext();
		} catch (e) {
			error = e.message;
			estimatingAges = false;
			buildingTimeline = false;
		}
	}

	function getTaggedCount() {
		return targetData?.tagged_count || 0;
	}
</script>

<div class="tag-page">
	<div class="tag-hero">
		<h2>Tag Your Photos</h2>
		<p class="subtitle">
			Tell us when each photo was taken. The more you tag, the more accurate the timeline.
		</p>
	</div>

	{#if loading}
		<div class="loading">
			<div class="spinner"></div>
			<p>Loading photos...</p>
		</div>
	{:else if error}
		<div class="error-card">
			<p>{error}</p>
			<button class="btn-secondary" onclick={loadTargetPhotos}>Retry</button>
		</div>
	{:else if targetData && targetData.total === 0}
		<div class="empty-state">
			<p>No photos uploaded yet. <button class="link-btn" onclick={() => { import('$lib/stores.js').then(m => m.appState.set('upload')); }}>Upload photos</button> to get started.</p>
		</div>
	{:else if targetData}
		<div class="accuracy-section">
			<AccuracyMeter
				tagged={getTaggedCount()}
				total={targetData.total}
				minRequired={targetData.min_required}
				recommended={targetData.recommended}
			/>
		</div>

		<div class="toolbar">
			<button
				class="btn-secondary btn-small"
				class:active={bulkMode}
				onclick={() => { bulkMode = !bulkMode; if (!bulkMode) selectedIds = new Set(); }}
			>
				{bulkMode ? `Cancel (${selectedIds.size} selected)` : 'Bulk Tag'}
			</button>

			{#if bulkMode && selectedIds.size > 0}
				<div class="bulk-inputs">
					<input type="number" min="1900" max="2030" placeholder="Year" bind:value={bulkYear} class="year-input" />
					<input type="number" min="1" max="12" placeholder="Month" bind:value={bulkMonth} class="month-input" />
					<button class="btn-primary btn-small" onclick={bulkTag}>
						Tag {selectedIds.size} photo{selectedIds.size !== 1 ? 's' : ''}
					</button>
				</div>
			{/if}
		</div>

		{#if getTaggedCount() >= targetData.min_required}
			<div class="build-section">
				<button
					class="btn-primary build-btn"
					onclick={requestBuildTimeline}
					disabled={estimatingAges || buildingTimeline}
				>
					{#if estimatingAges}
						Estimating ages...
					{:else if buildingTimeline}
						Building timeline...
					{:else}
						Build Timeline
					{/if}
				</button>
				{#if getTaggedCount() < targetData.recommended}
					<p class="build-hint">
						You can build now, but tagging {targetData.recommended - getTaggedCount()} more will improve accuracy.
					</p>
				{/if}
			</div>
		{/if}

		<div class="photo-grid">
			{#each targetData.photos as photo}
				<div class="photo-card" class:tagged={photo.tagged_year} class:selected={selectedIds.has(photo.id)}>
					<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
					<div class="photo-image-container" onclick={() => openLightbox(photo)}>
						<img src={photo.url} alt={photo.original_filename} loading="lazy" />
						{#if bulkMode}
							<div class="select-checkbox" class:checked={selectedIds.has(photo.id)}>
								{#if selectedIds.has(photo.id)}✓{/if}
							</div>
						{/if}
					</div>

					<div class="photo-info">
						{#if editingPhotoId === photo.id}
							<div class="tag-input-row">
								<input type="number" min="1" max="12" placeholder="Month" bind:value={monthInput} onkeydown={(e) => e.key === 'Enter' && tagPhoto(photo.id)} class="month-input" />
								<input type="number" min="1900" max="2030" placeholder="Year" bind:value={yearInput} onkeydown={(e) => e.key === 'Enter' && tagPhoto(photo.id)} class="year-input" />
								<button class="btn-primary btn-small" onclick={() => tagPhoto(photo.id)}>Save</button>
							</div>
						{:else if photo.tagged_year}
							<div class="tagged-row">
								<span class="year-badge">{photo.tagged_month ? `${photo.tagged_month}/${photo.tagged_year}` : photo.tagged_year}</span>
								<button class="btn-edit" onclick={() => startEditing(photo.id, photo.tagged_year, photo.tagged_month)}>Edit</button>
							</div>
							{#if photo.estimated_age}
								<p class="estimated-hint">AI thinks ~{Math.round(photo.estimated_age)} yrs old</p>
							{/if}
						{:else}
							<div class="tag-actions">
								<button class="btn-secondary btn-small" onclick={() => startEditing(photo.id, null, null)}>Tag</button>
								{#if photo.exif_date}
									<button
										class="btn-exif btn-small"
										title="Use EXIF date: {photo.exif_date.slice(0, 10)}"
										onclick={() => {
											const dt = new Date(photo.exif_date);
											startEditing(photo.id, dt.getFullYear(), dt.getMonth() + 1);
										}}
									>
										📅 {photo.exif_date.slice(0, 4)}
									</button>
								{/if}
							</div>
							{#if photo.estimated_age}
								<p class="estimated-hint">AI thinks ~{Math.round(photo.estimated_age)} yrs old</p>
							{/if}
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

{#if showBuildDialog}
	<!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
	<div class="dialog-overlay" onclick={() => showBuildDialog = false}>
		<!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
		<div class="dialog-card" onclick={(e) => e.stopPropagation()}>
			<h3>Build Timeline</h3>
			<p><strong>{getUntaggedCount()}</strong> of {targetData.total} photos are missing a date.</p>
			<p class="dialog-hint">Photos without a year will be grouped under "Undated" at the end of your timeline. You can always come back and add dates later.</p>
			<div class="dialog-actions">
				<button class="btn-secondary" onclick={() => showBuildDialog = false}>Keep tagging</button>
				<button class="btn-primary" onclick={buildTimeline}>Build timeline</button>
			</div>
		</div>
	</div>
{/if}

{#if lightboxPhoto}
	<!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
	<div class="lightbox-overlay" onclick={closeLightbox}>
		{#if lightboxIndex > 0}
			<button class="nav-btn nav-prev" onclick={(e) => { e.stopPropagation(); navigateLightbox(-1); }}>
				<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6" /></svg>
			</button>
		{/if}
		{#if lightboxIndex < targetData.photos.length - 1}
			<button class="nav-btn nav-next" onclick={(e) => { e.stopPropagation(); navigateLightbox(1); }}>
				<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6" /></svg>
			</button>
		{/if}
		<!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
		<div class="lightbox-content" onclick={(e) => e.stopPropagation()}>
			<button class="close-btn" onclick={closeLightbox}>
				<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
			</button>
			<img src={lightboxPhoto.url} alt={lightboxPhoto.original_filename} class="lightbox-image" />
			<div class="lightbox-info">
				<p>{lightboxPhoto.original_filename}</p>
				<p class="lightbox-counter">{lightboxIndex + 1} / {targetData.photos.length}</p>
				{#if lightboxPhoto.tagged_year}
					<span class="year-badge">{lightboxPhoto.tagged_month ? `${lightboxPhoto.tagged_month}/${lightboxPhoto.tagged_year}` : lightboxPhoto.tagged_year}</span>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.tag-page { max-width: 1100px; margin: 0 auto; padding: 40px 24px 80px; }
	.tag-hero { text-align: center; margin-bottom: 32px; }
	.tag-hero h2 { font-size: 2rem; color: var(--accent); margin-bottom: 12px; }
	.subtitle { color: var(--text-secondary); max-width: 500px; margin: 0 auto; }
	.loading { text-align: center; padding: 60px 0; }
	.loading p { color: var(--text-secondary); margin-top: 16px; }
	.spinner { width: 40px; height: 40px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
	@keyframes spin { to { transform: rotate(360deg); } }
	.error-card { text-align: center; padding: 40px; background: var(--bg-card); border-radius: var(--radius-lg); }
	.error-card p { color: var(--danger); margin-bottom: 16px; }
	.accuracy-section { margin-bottom: 24px; }
	.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
	.toolbar .active { background: var(--accent); color: white; }
	.bulk-inputs { display: flex; gap: 8px; align-items: center; }
	.build-section { text-align: center; margin-bottom: 32px; padding: 24px; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px solid var(--border); }
	.build-btn { font-size: 1rem; padding: 14px 40px; }
	.build-hint { color: var(--text-muted); font-size: 0.85rem; margin-top: 12px; }
	.photo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
	.photo-card { background: var(--bg-card); border-radius: var(--radius); overflow: hidden; border: 2px solid transparent; transition: all var(--transition); }
	.photo-card.tagged { border-color: var(--accent-dim); }
	.photo-card.selected { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent); }
	.photo-image-container { position: relative; aspect-ratio: 1; overflow: hidden; cursor: pointer; }
	.photo-image-container img { width: 100%; height: 100%; object-fit: cover; transition: transform 200ms ease; }
	.photo-image-container:hover img { transform: scale(1.05); }
	.select-checkbox { position: absolute; top: 8px; left: 8px; width: 24px; height: 24px; border-radius: 50%; background: rgba(255,255,255,0.8); border: 2px solid var(--accent); display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: bold; color: var(--accent); }
	.select-checkbox.checked { background: var(--accent); color: white; }
	.photo-info { padding: 10px; }
	.tag-input-row { display: flex; gap: 6px; align-items: center; }
	.tag-input-row input { flex: 1; padding: 6px 10px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: var(--radius); color: var(--text-primary); font-size: 0.85rem; font-family: var(--font-sans); }
	.tag-input-row input:focus { outline: none; border-color: var(--accent); }
	.tagged-row { display: flex; align-items: center; gap: 8px; }
	.year-badge { background: var(--accent); color: var(--bg-primary); padding: 4px 12px; border-radius: var(--radius); font-weight: 600; font-size: 0.85rem; }
	.btn-edit { background: none; color: var(--text-muted); font-size: 0.8rem; padding: 4px 8px; border-radius: var(--radius); }
	.btn-edit:hover { color: var(--text-primary); background: var(--bg-hover); }
	.year-input { width: 65px; }
	.month-input { width: 55px; }
	.year-input::-webkit-inner-spin-button, .year-input::-webkit-outer-spin-button, .month-input::-webkit-inner-spin-button, .month-input::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
	.year-input, .month-input { -moz-appearance: textfield; }
	.btn-small { padding: 4px 10px; font-size: 0.8rem; }
	.full-width { width: 100%; }
	.tag-actions { display: flex; gap: 6px; }
	.tag-actions .btn-secondary { flex: 1; }
	.btn-exif { background: var(--bg-secondary); border: 1px solid var(--border); color: var(--text-secondary); white-space: nowrap; cursor: pointer; border-radius: var(--radius); }
	.btn-exif:hover { border-color: var(--accent); color: var(--accent); }
	.estimated-hint { color: var(--text-muted); font-size: 0.7rem; margin-top: 4px; font-style: italic; }
	.empty-state { text-align: center; padding: 60px 0; color: var(--text-secondary); }
	.link-btn { background: none; color: var(--accent); font-weight: 600; font-size: inherit; text-decoration: underline; padding: 0; cursor: pointer; }

	/* Dialog */
	.dialog-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 900; display: flex; align-items: center; justify-content: center; padding: 20px; }
	.dialog-card { background: var(--bg-card); border-radius: var(--radius-lg); padding: 32px; max-width: 480px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
	.dialog-card h3 { font-size: 1.3rem; margin-bottom: 12px; color: var(--text-primary); }
	.dialog-card p { color: var(--text-secondary); margin-bottom: 8px; line-height: 1.5; }
	.dialog-hint { font-size: 0.85rem; color: var(--text-muted); }
	.dialog-actions { display: flex; gap: 12px; margin-top: 20px; justify-content: flex-end; }

	/* Lightbox */
	.lightbox-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.9); z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 40px; }
	.lightbox-content { max-width: 900px; max-height: 90vh; position: relative; display: flex; flex-direction: column; }
	.lightbox-image { max-width: 100%; max-height: 70vh; object-fit: contain; border-radius: var(--radius); }
	.lightbox-info { padding: 16px 0; text-align: center; color: white; }
	.lightbox-counter { color: rgba(255,255,255,0.5); font-size: 0.8rem; margin-top: 4px; }
	.close-btn { position: absolute; top: -40px; right: 0; background: none; color: rgba(255,255,255,0.7); padding: 8px; border: none; cursor: pointer; }
	.close-btn:hover { color: white; }
	.nav-btn { position: fixed; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,0.15); border: none; border-radius: 50%; width: 52px; height: 52px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: white; z-index: 1001; transition: background 200ms ease; }
	.nav-btn:hover { background: rgba(255,255,255,0.3); }
	.nav-prev { left: 16px; }
	.nav-next { right: 16px; }
</style>
