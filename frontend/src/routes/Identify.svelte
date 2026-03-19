<script>
	import { api } from '$lib/api.js';
	import FaceCluster from '../components/FaceCluster.svelte';

	let { onNext } = $props();
	let clusterData = $state(null);
	let loading = $state(true);
	let confirming = $state(false);
	let confirmed = $state(false);
	let error = $state(null);

	async function loadClusters() {
		loading = true;
		try {
			const data = await api.getClusters();
			clusterData = data;

			// Check if already confirmed
			const target = data.clusters.find((c) => c.is_target);
			if (target) {
				confirmed = true;
			}
		} catch (e) {
			error = e.message;
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadClusters();
	});

	async function confirmCluster(clusterId) {
		confirming = true;
		error = null;
		try {
			await api.confirmCluster(clusterId);
			confirmed = true;
			await loadClusters();
		} catch (e) {
			error = e.message;
		} finally {
			confirming = false;
		}
	}
</script>

<div class="identify-page">
	<div class="identify-hero">
		<h2>Is This You?</h2>
		<p class="subtitle">
			We found groups of faces in your photos. Select the cluster that represents you.
		</p>
	</div>

	{#if loading}
		<div class="loading">
			<div class="spinner"></div>
			<p>Loading face clusters...</p>
		</div>
	{:else if error}
		<div class="error-card">
			<p>{error}</p>
			<button class="btn-secondary" onclick={loadClusters}>Retry</button>
		</div>
	{:else if clusterData && clusterData.clusters.length > 0}
		<div class="clusters">
			{#each clusterData.clusters as cluster, i}
				<FaceCluster
					{cluster}
					isLargest={i === 0 && !confirmed}
					onConfirm={() => confirmCluster(cluster.cluster_id)}
					disabled={confirming}
				/>
			{/each}
		</div>

		{#if confirmed}
			<div class="confirmed-banner">
				<p>Identity confirmed! Now let's tag your photos with years.</p>
				<button class="btn-primary" onclick={onNext}>Continue to Tagging</button>
			</div>
		{/if}
	{:else}
		<div class="no-clusters">
			<p>No face clusters found. Try uploading more photos with clear faces.</p>
		</div>
	{/if}
</div>

<style>
	.identify-page {
		max-width: 1000px;
		margin: 0 auto;
		padding: 40px 24px 80px;
	}

	.identify-hero {
		text-align: center;
		margin-bottom: 40px;
	}

	.identify-hero h2 {
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

	.clusters {
		display: flex;
		flex-direction: column;
		gap: 24px;
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

	.confirmed-banner {
		margin-top: 32px;
		padding: 24px;
		background: rgba(46, 204, 113, 0.08);
		border: 1px solid rgba(46, 204, 113, 0.3);
		border-radius: var(--radius-lg);
		text-align: center;
	}

	.confirmed-banner p {
		color: var(--success);
		margin-bottom: 16px;
	}

	.no-clusters {
		text-align: center;
		padding: 60px 0;
		color: var(--text-secondary);
	}
</style>
