<script>
	import { api } from '$lib/api.js';
	import AccuracyMeter from '../components/AccuracyMeter.svelte';

	let { onNext } = $props();
	let targetData = $state(null);
	let loading = $state(true);
	let error = $state(null);
	let estimatingAges = $state(false);
	let buildingTimeline = $state(false);
	let editingPhotoId = $state(null);
	let yearInput = $state('');

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
		if (isNaN(year) || year < 1900 || year > 2030) {
			return;
		}
		try {
			await api.tagPhoto(photoId, year);
			editingPhotoId = null;
			yearInput = '';
			await loadTargetPhotos();
		} catch (e) {
			error = e.message;
		}
	}

	async function untagPhoto(photoId) {
		try {
			await api.untagPhoto(photoId);
			await loadTargetPhotos();
		} catch (e) {
			error = e.message;
		}
	}

	function startEditing(photoId, existingYear) {
		editingPhotoId = photoId;
		yearInput = existingYear ? String(existingYear) : '';
	}

	async function buildTimeline() {
		error = null;
		estimatingAges = true;

		try {
			// Step 1: Estimate ages
			await api.estimateAges();
			estimatingAges = false;
			buildingTimeline = true;

			// Step 2: Build timeline
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
	{:else if targetData}
		<div class="accuracy-section">
			<AccuracyMeter
				tagged={getTaggedCount()}
				total={targetData.total}
				minRequired={targetData.min_required}
				recommended={targetData.recommended}
			/>
		</div>

		{#if getTaggedCount() >= targetData.min_required}
			<div class="build-section">
				<button
					class="btn-primary build-btn"
					onclick={buildTimeline}
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
						You can build now, but tagging {targetData.recommended - getTaggedCount()} more photos will improve accuracy.
					</p>
				{/if}
			</div>
		{/if}

		<div class="photo-grid">
			{#each targetData.photos as photo}
				<div class="photo-card" class:tagged={photo.tagged_year}>
					<div class="photo-image-container">
						<img
							src={photo.url}
							alt={photo.original_filename}
							loading="lazy"
						/>
						<div class="face-crop-overlay">
							<img
								src={photo.face_crop_url}
								alt="Face"
								class="face-crop"
							/>
						</div>
					</div>

					<div class="photo-info">
						{#if editingPhotoId === photo.id}
							<div class="tag-input-row">
								<input
									type="number"
									min="1900"
									max="2030"
									placeholder="Year"
									bind:value={yearInput}
									onkeydown={(e) => e.key === 'Enter' && tagPhoto(photo.id)}
								/>
								<button class="btn-primary btn-small" onclick={() => tagPhoto(photo.id)}>
									Save
								</button>
								<button
									class="btn-secondary btn-small"
									onclick={() => { editingPhotoId = null; yearInput = ''; }}
								>
									Cancel
								</button>
							</div>
						{:else if photo.tagged_year}
							<div class="tagged-row">
								<span class="year-badge">{photo.tagged_year}</span>
								<button
									class="btn-edit"
									onclick={() => startEditing(photo.id, photo.tagged_year)}
								>
									Edit
								</button>
								<button class="btn-edit danger" onclick={() => untagPhoto(photo.id)}>
									Remove
								</button>
							</div>
						{:else}
							<button
								class="btn-secondary btn-small full-width"
								onclick={() => startEditing(photo.id, null)}
							>
								Tag with year
							</button>
						{/if}

						{#if photo.exif_date}
							<p class="exif-date">EXIF: {photo.exif_date.slice(0, 10)}</p>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.tag-page {
		max-width: 1100px;
		margin: 0 auto;
		padding: 40px 24px 80px;
	}

	.tag-hero {
		text-align: center;
		margin-bottom: 32px;
	}

	.tag-hero h2 {
		font-size: 2rem;
		color: var(--accent);
		margin-bottom: 12px;
	}

	.subtitle {
		color: var(--text-secondary);
		max-width: 500px;
		margin: 0 auto;
	}

	.loading {
		text-align: center;
		padding: 60px 0;
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
		margin: 0 auto;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.error-card {
		text-align: center;
		padding: 40px;
		background: var(--bg-card);
		border-radius: var(--radius-lg);
	}

	.error-card p {
		color: var(--danger);
		margin-bottom: 16px;
	}

	.accuracy-section {
		margin-bottom: 24px;
	}

	.build-section {
		text-align: center;
		margin-bottom: 32px;
		padding: 24px;
		background: var(--bg-card);
		border-radius: var(--radius-lg);
		border: 1px solid var(--border);
	}

	.build-btn {
		font-size: 1rem;
		padding: 14px 40px;
	}

	.build-hint {
		color: var(--text-muted);
		font-size: 0.85rem;
		margin-top: 12px;
	}

	.photo-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
		gap: 20px;
	}

	.photo-card {
		background: var(--bg-card);
		border-radius: var(--radius);
		overflow: hidden;
		border: 2px solid transparent;
		transition: all var(--transition);
	}

	.photo-card.tagged {
		border-color: var(--accent-dim);
	}

	.photo-image-container {
		position: relative;
		aspect-ratio: 1;
		overflow: hidden;
	}

	.photo-image-container img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.face-crop-overlay {
		position: absolute;
		bottom: 8px;
		right: 8px;
		width: 48px;
		height: 48px;
		border-radius: 50%;
		overflow: hidden;
		border: 2px solid var(--accent);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
	}

	.face-crop {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.photo-info {
		padding: 12px;
	}

	.tag-input-row {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.tag-input-row input {
		flex: 1;
		padding: 8px 12px;
		background: var(--bg-primary);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text-primary);
		font-size: 0.9rem;
		font-family: var(--font-sans);
	}

	.tag-input-row input:focus {
		outline: none;
		border-color: var(--accent);
	}

	.tagged-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.year-badge {
		background: var(--accent);
		color: var(--bg-primary);
		padding: 4px 12px;
		border-radius: var(--radius);
		font-weight: 600;
		font-size: 0.85rem;
	}

	.btn-edit {
		background: none;
		color: var(--text-muted);
		font-size: 0.8rem;
		padding: 4px 8px;
		border-radius: var(--radius);
	}

	.btn-edit:hover {
		color: var(--text-primary);
		background: var(--bg-hover);
	}

	.btn-edit.danger:hover {
		color: var(--danger);
	}

	.btn-small {
		padding: 6px 14px;
		font-size: 0.85rem;
	}

	.full-width {
		width: 100%;
	}

	.exif-date {
		color: var(--text-muted);
		font-size: 0.75rem;
		margin-top: 8px;
	}
</style>
