<script>
	import { api } from '$lib/api.js';
	let { cluster, isLargest = false, onConfirm, onUpdate = null, disabled = false } = $props();
	let deleting = $state({});

	async function deleteFace(faceId) {
		deleting[faceId] = true;
		deleting = { ...deleting };
		try {
			await api.deleteFace(faceId);
			cluster.faces = cluster.faces.filter(f => f.face_id !== faceId);
			cluster.face_count = cluster.faces.length;
			cluster = cluster;
			if (onUpdate) onUpdate();
		} catch (e) {
			console.error('Delete face failed:', e);
		} finally {
			deleting[faceId] = false;
			deleting = { ...deleting };
		}
	}
</script>

<div class="cluster-card" class:largest={isLargest} class:target={cluster.is_target}>
	<div class="cluster-header">
		<div class="cluster-info">
			<h3>
				{#if cluster.is_target}
					You
				{:else}
					Person {cluster.cluster_id + 1}
				{/if}
			</h3>
			<span class="face-count">{cluster.face_count} photo{cluster.face_count !== 1 ? 's' : ''}</span>
		</div>

		{#if isLargest && !cluster.is_target}
			<span class="largest-badge">Most likely you</span>
		{/if}

		{#if cluster.is_target}
			<span class="confirmed-badge">Confirmed</span>
		{:else}
			<button
				class="btn-primary"
				onclick={onConfirm}
				{disabled}
			>
				This is me
			</button>
		{/if}
	</div>

	<div class="face-grid">
		{#each cluster.faces as face}
			<div class="face-thumb" class:deleting={deleting[face.face_id]}>
				<img src={face.crop_url} alt="Face" loading="lazy" />
				<button
					class="face-delete-btn"
					title="Remove this face"
					onclick={(e) => { e.stopPropagation(); deleteFace(face.face_id); }}
					disabled={deleting[face.face_id]}
				>✕</button>
			</div>
		{/each}
	</div>
</div>

<style>
	.cluster-card {
		background: var(--bg-card);
		border-radius: var(--radius-lg);
		padding: 24px;
		border: 2px solid transparent;
		transition: all var(--transition);
	}

	.cluster-card.largest {
		border-color: var(--accent-dim);
		background: linear-gradient(135deg, var(--bg-card), var(--accent-glow));
	}

	.cluster-card.target {
		border-color: var(--success);
	}

	.cluster-header {
		display: flex;
		align-items: center;
		gap: 16px;
		margin-bottom: 16px;
	}

	.cluster-info {
		flex: 1;
	}

	.cluster-info h3 {
		font-family: var(--font-sans);
		font-size: 1.1rem;
		font-weight: 600;
	}

	.face-count {
		color: var(--text-muted);
		font-size: 0.85rem;
	}

	.largest-badge {
		background: var(--accent-glow);
		color: var(--accent);
		padding: 4px 12px;
		border-radius: var(--radius);
		font-size: 0.8rem;
		font-weight: 500;
		border: 1px solid var(--accent-dim);
	}

	.confirmed-badge {
		background: rgba(46, 204, 113, 0.1);
		color: var(--success);
		padding: 4px 12px;
		border-radius: var(--radius);
		font-size: 0.8rem;
		font-weight: 500;
		border: 1px solid rgba(46, 204, 113, 0.3);
	}

	.face-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.face-thumb {
		position: relative;
		width: 64px;
		height: 64px;
		border-radius: 50%;
		overflow: visible;
		background: var(--bg-primary);
		flex-shrink: 0;
	}

	.face-thumb.deleting {
		opacity: 0.3;
	}

	.face-thumb img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		border-radius: 50%;
	}

	.face-delete-btn {
		position: absolute;
		top: -4px;
		right: -4px;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: var(--error, #e53e3e);
		color: white;
		border: 2px solid var(--bg-card);
		font-size: 10px;
		line-height: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		opacity: 0;
		transition: opacity 200ms ease;
		padding: 0;
	}

	.face-thumb:hover .face-delete-btn {
		opacity: 1;
	}

	.face-thumb.more {
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--text-muted);
		font-size: 0.8rem;
		font-weight: 500;
		border: 1px dashed var(--border);
	}
</style>
