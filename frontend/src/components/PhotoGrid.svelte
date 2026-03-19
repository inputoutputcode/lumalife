<script>
	let { photos = [] } = $props();
</script>

<div class="grid">
	{#each photos as photo}
		<div class="grid-item">
			<img
				src={photo.url}
				alt={photo.original_filename}
				loading="lazy"
			/>
			{#if photo.processed}
				<div class="processed-badge" title="Processed">
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
						<polyline points="20 6 9 17 4 12" />
					</svg>
				</div>
			{/if}
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

	.processed-badge {
		position: absolute;
		top: 6px;
		right: 6px;
		background: var(--success);
		color: white;
		border-radius: 50%;
		width: 22px;
		height: 22px;
		display: flex;
		align-items: center;
		justify-content: center;
	}
</style>
