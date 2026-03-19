<script>
	import { api } from '$lib/api.js';
	import FaceCluster from '../components/FaceCluster.svelte';

	let { onNext } = $props();
	let clusterData = $state(null);
	let loading = $state(true);
	let confirming = $state(false);
	let confirmed = $state(false);
	let error = $state(null);
	let processing = $state(false);
	let processProgress = $state({ phase: '', current: 0, total: 0, message: '' });

	async function loadClusters() {
		loading = true;
		try {
			const data = await api.getClusters();
			clusterData = data;

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

	async function startProcessing() {
		processing = true;
		error = null;
		processProgress = { phase: 'starting', current: 0, total: 0, message: 'Starting...' };

		const eventSource = api.processStream();

		eventSource.addEventListener('start', (e) => {
			const data = JSON.parse(e.data);
			processProgress = { phase: 'face_detection', current: 0, total: data.total, message: 'Detecting faces...' };
		});

		eventSource.addEventListener('progress', (e) => {
			const data = JSON.parse(e.data);
			const facesFound = data.detail?.faces_found ?? 0;
			processProgress = {
				phase: data.phase,
				current: data.current,
				total: data.total,
				message: `Photo ${data.current}/${data.total} — ${facesFound} face${facesFound !== 1 ? 's' : ''} found`,
			};
		});

		eventSource.addEventListener('phase', (e) => {
			const data = JSON.parse(e.data);
			if (data.phase === 'clustering') {
				processProgress = { ...processProgress, phase: 'clustering', message: `Clustering ${data.total_faces} faces...` };
			}
		});

		eventSource.addEventListener('clustering_done', (e) => {
			const data = JSON.parse(e.data);
			const clusterCount = data.clusters?.length ?? 0;
			processProgress = { ...processProgress, phase: 'done', message: `Found ${clusterCount} cluster${clusterCount !== 1 ? 's' : ''} from ${data.total_faces} faces` };
		});

		eventSource.addEventListener('info', (e) => {
			const data = JSON.parse(e.data);
			processProgress = { ...processProgress, message: data.message };
		});

		eventSource.addEventListener('complete', () => {
			eventSource.close();
			processing = false;
			loadClusters();
		});

		eventSource.addEventListener('error', (e) => {
			if (e.data) {
				const data = JSON.parse(e.data);
				error = data.error;
			}
			eventSource.close();
			processing = false;
		});

		eventSource.onerror = () => {
			eventSource.close();
			processing = false;
			if (!error) loadClusters();
		};
	}

	$effect(() => {
		loadClusters().then(async () => {
			// Only auto-start processing if there are photos but no clusters
			if (clusterData && clusterData.clusters.length === 0 && !processing) {
				try {
					const stats = await api.getStats();
					if (stats.total_photos > 0) {
						startProcessing();
					}
				} catch {}
			}
		});
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

	{#if processing}
		<div class="process-status">
			<div class="process-status-bar">
				<div class="process-info">
					<div class="spinner-small"></div>
					<span class="process-message">{processProgress.message}</span>
				</div>
				{#if processProgress.total > 0}
					<div class="process-progress-track">
						<div class="process-progress-fill" style="width: {(processProgress.current / processProgress.total) * 100}%"></div>
					</div>
					<span class="process-count">{processProgress.current}/{processProgress.total}</span>
				{/if}
			</div>
		</div>
	{/if}

	{#if loading && !processing}
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
			<p>No photos uploaded yet. Go to <button class="link-btn" onclick={() => { import('$lib/stores.js').then(m => m.appState.set('upload')); }}>Upload</button> to add your photos first.</p>
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

	.process-status {
		margin-bottom: 32px;
	}

	.process-status-bar {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 16px 20px;
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.process-info {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-shrink: 0;
	}

	.spinner-small {
		width: 18px;
		height: 18px;
		border: 2px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.process-message {
		font-size: 0.9rem;
		color: var(--text-primary);
		font-weight: 500;
	}

	.process-progress-track {
		flex: 1;
		height: 6px;
		background: var(--border);
		border-radius: 3px;
		overflow: hidden;
		min-width: 100px;
	}

	.process-progress-fill {
		height: 100%;
		background: var(--accent);
		border-radius: 3px;
		transition: width 0.3s ease;
	}

	.process-count {
		font-size: 0.8rem;
		color: var(--text-muted);
		font-weight: 500;
		flex-shrink: 0;
	}

	.link-btn {
		background: none;
		color: var(--accent);
		font-weight: 600;
		font-size: inherit;
		text-decoration: underline;
		padding: 0;
		cursor: pointer;
	}
</style>
