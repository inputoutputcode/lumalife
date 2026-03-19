<script>
	import { api } from '$lib/api.js';

	let { photos = [], onUpdate = null } = $props();
	let rotating = $state({});

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
</script>

<div class="grid">
	{#each photos as photo}
		<div class="grid-item">
			<img
				src={`${photo.url}?t=${Date.now()}`}
				alt={photo.original_filename}
				loading="lazy"
			/>
			<div class="photo-actions">
				<button
					class="rotate-btn"
					title="Rotate 90°"
					onclick={(e) => { e.stopPropagation(); rotatePhoto(photo.id); }}
					disabled={rotating[photo.id]}
				>
					{#if rotating[photo.id]}
						<div class="mini-spinner"></div>
					{:else}
						<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
		opacity: 0.6;
		transition: opacity 200ms ease;
	}

	.grid-item:hover .photo-actions {
		opacity: 1;
	}

	.rotate-btn {
		background: rgba(255, 255, 255, 0.9);
		border: none;
		border-radius: 50%;
		width: 30px;
		height: 30px;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		color: var(--text-primary);
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
		transition: background 200ms ease;
	}

	.rotate-btn:hover {
		background: white;
	}

	.rotate-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.mini-spinner {
		width: 14px;
		height: 14px;
		border: 2px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

</style>
