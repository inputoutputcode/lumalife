<script>
	import { api } from '$lib/api.js';

	let { photos = [], onUpdate = null } = $props();
	let rotating = $state({});
	let deleting = $state({});

	async function rotatePhoto(photoId) {
		rotating[photoId] = true;
		rotating = { ...rotating };
		try {
			await api.rotatePhoto(photoId);
			if (onUpdate) onUpdate();
		} catch (e) {
			console.error('Rotate failed:', e);
		} finally {
			rotating[photoId] = false;
			rotating = { ...rotating };
		}
	}

	async function deletePhoto(photoId) {
		if (!confirm('Delete this photo?')) return;
		deleting[photoId] = true;
		deleting = { ...deleting };
		try {
			await api.deletePhoto(photoId);
			if (onUpdate) onUpdate();
		} catch (e) {
			console.error('Delete failed:', e);
		} finally {
			deleting[photoId] = false;
			deleting = { ...deleting };
		}
	}
</script>

<div class="grid">
	{#each photos as photo}
		<div class="grid-item" class:deleting={deleting[photo.id]}>
			<img
				src={`${photo.url}?t=${Date.now()}`}
				alt={photo.original_filename}
				loading="lazy"
			/>
			<div class="photo-actions">
				<button
					class="action-btn delete-btn"
					title="Delete photo"
					onclick={(e) => { e.stopPropagation(); deletePhoto(photo.id); }}
					disabled={deleting[photo.id]}
				>
					{#if deleting[photo.id]}
						<div class="mini-spinner"></div>
					{:else}
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<polyline points="3 6 5 6 21 6" />
							<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
						</svg>
					{/if}
				</button>
				<button
					class="action-btn rotate-btn"
					title="Rotate 90°"
					onclick={(e) => { e.stopPropagation(); rotatePhoto(photo.id); }}
					disabled={rotating[photo.id]}
				>
					{#if rotating[photo.id]}
						<div class="mini-spinner"></div>
					{:else}
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<polyline points="1 4 1 10 7 10" />
							<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
						</svg>
					{/if}
				</button>
			</div>
		</div>
	{/each}
</div>

<style>
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
		gap: 8px;
	}

	.grid-item {
		position: relative;
		aspect-ratio: 1;
		border-radius: var(--radius);
		overflow: hidden;
		background: var(--bg-card);
		transition: opacity 300ms ease;
	}

	.grid-item.deleting {
		opacity: 0.3;
	}

	.grid-item img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		transition: transform 300ms ease;
	}

	.grid-item:hover img {
		transform: scale(1.05);
	}

	.photo-actions {
		position: absolute;
		bottom: 6px;
		right: 6px;
		display: flex;
		gap: 4px;
		opacity: 0.6;
		transition: opacity 200ms ease;
	}

	.grid-item:hover .photo-actions {
		opacity: 1;
	}

	.action-btn {
		background: rgba(255, 255, 255, 0.9);
		border: none;
		border-radius: 50%;
		width: 28px;
		height: 28px;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		color: var(--text-primary);
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
		transition: background 200ms ease, color 200ms ease;
	}

	.action-btn:hover {
		background: white;
	}

	.delete-btn:hover {
		background: var(--error, #e53e3e);
		color: white;
	}

	.action-btn:disabled {
		opacity: 1;
		cursor: wait;
		background: var(--accent);
		color: white;
	}

	.mini-spinner {
		width: 12px;
		height: 12px;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: white;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}
</style>
