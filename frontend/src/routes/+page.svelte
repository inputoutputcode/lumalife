<script>
	import { appState, stats } from '$lib/stores.js';
	import { api } from '$lib/api.js';
	import { onMount } from 'svelte';
	import Upload from './Upload.svelte';
	import Identify from './Identify.svelte';
	import Tag from './Tag.svelte';
	import Timeline from './Timeline.svelte';

	let currentState = $state('upload');
	let processingProgress = $state(null);
	let error = $state(null);
	let appStats = $state(null);

	appState.subscribe((v) => (currentState = v));

	onMount(async () => {
		try {
			appStats = await api.getStats();
			stats.set(appStats);

			// Auto-navigate based on existing data
			if (appStats.timeline_entries > 0) {
				appState.set('timeline');
			} else if (appStats.tagged_photos >= 8) {
				appState.set('tag');
			} else if (appStats.target_faces > 0) {
				appState.set('tag');
			} else if (appStats.total_clusters > 0) {
				appState.set('identify');
			} else if (appStats.total_photos > 0) {
				appState.set('processing');
			}
		} catch {
			// Fresh start
		}
	});

	function goTo(state) {
		appState.set(state);
		error = null;
	}

	async function startProcessing() {
		appState.set('processing');
		error = null;
		processingProgress = { phase: 'starting', current: 0, total: 0 };

		const eventSource = api.processStream();

		eventSource.addEventListener('start', (e) => {
			const data = JSON.parse(e.data);
			processingProgress = { phase: 'face_detection', current: 0, total: data.total };
		});

		eventSource.addEventListener('progress', (e) => {
			const data = JSON.parse(e.data);
			processingProgress = {
				phase: data.phase,
				current: data.current,
				total: data.total,
				detail: data.detail,
			};
		});

		eventSource.addEventListener('phase', (e) => {
			const data = JSON.parse(e.data);
			processingProgress = { ...processingProgress, phase: data.phase };
		});

		eventSource.addEventListener('clustering_done', (e) => {
			const data = JSON.parse(e.data);
			processingProgress = {
				...processingProgress,
				phase: 'clustering_done',
				clusters: data.clusters,
			};
		});

		eventSource.addEventListener('info', (e) => {
			const data = JSON.parse(e.data);
			processingProgress = { ...processingProgress, phase: 'info', message: data.message };
		});

		eventSource.addEventListener('complete', () => {
			eventSource.close();
			processingProgress = null;
			appState.set('identify');
		});

		eventSource.addEventListener('error', (e) => {
			if (e.data) {
				const data = JSON.parse(e.data);
				error = data.error;
			}
			eventSource.close();
			processingProgress = null;
		});

		eventSource.onerror = () => {
			eventSource.close();
			// SSE completed normally
			if (!error) {
				appState.set('identify');
			}
			processingProgress = null;
		};
	}
</script>

<div class="app">
	<header class="app-header">
		<div class="header-content">
			<button class="logo" onclick={() => goTo('upload')}>LumaLife</button>
			<nav class="nav-steps">
				<button
					class="step"
					class:active={currentState === 'upload'}
					onclick={() => goTo('upload')}
				>
					<span class="step-num">1</span> Upload
				</button>
				<span class="step-divider"></span>
				<button
					class="step"
					class:active={currentState === 'processing' || currentState === 'identify'}
					onclick={() => goTo('identify')}
				>
					<span class="step-num">2</span> Identify
				</button>
				<span class="step-divider"></span>
				<button
					class="step"
					class:active={currentState === 'tag'}
					onclick={() => goTo('tag')}
				>
					<span class="step-num">3</span> Tag
				</button>
				<span class="step-divider"></span>
				<button
					class="step"
					class:active={currentState === 'timeline' || currentState === 'building'}
					onclick={() => goTo('timeline')}
				>
					<span class="step-num">4</span> Timeline
				</button>
			</nav>
		</div>
	</header>

	{#if error}
		<div class="error-banner">
			<p>{error}</p>
			<button onclick={() => (error = null)}>Dismiss</button>
		</div>
	{/if}

	<main class="main-content">
		{#if currentState === 'upload'}
			<Upload onProcess={startProcessing} />
		{:else if currentState === 'processing'}
			<div class="processing-view">
				<div class="processing-card">
					<div class="spinner"></div>
					<h2>Processing Photos</h2>
					{#if processingProgress}
						{#if processingProgress.phase === 'face_detection'}
							<p class="phase-label">Detecting faces...</p>
							<div class="progress-bar">
								<div
									class="progress-fill"
									style="width: {processingProgress.total > 0
										? (processingProgress.current / processingProgress.total) * 100
										: 0}%"
								></div>
							</div>
							<p class="progress-text">
								{processingProgress.current} / {processingProgress.total} photos
							</p>
						{:else if processingProgress.phase === 'clustering'}
							<p class="phase-label">Clustering faces...</p>
						{:else if processingProgress.phase === 'info'}
							<p class="phase-label">{processingProgress.message}</p>
						{:else}
							<p class="phase-label">Starting...</p>
						{/if}
					{/if}
				</div>
			</div>
		{:else if currentState === 'identify'}
			<Identify onNext={() => goTo('tag')} />
		{:else if currentState === 'tag'}
			<Tag onNext={() => goTo('timeline')} />
		{:else if currentState === 'timeline' || currentState === 'building'}
			<Timeline onManage={() => goTo('upload')} />
		{/if}
	</main>
</div>

<style>
	.app {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
	}

	.app-header {
		position: sticky;
		top: 0;
		z-index: 100;
		background: rgba(10, 10, 10, 0.9);
		backdrop-filter: blur(20px);
		border-bottom: 1px solid var(--border);
	}

	.header-content {
		max-width: 1200px;
		margin: 0 auto;
		padding: 16px 24px;
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.logo {
		font-family: var(--font-serif);
		font-size: 1.5rem;
		font-weight: 500;
		color: var(--accent);
		cursor: pointer;
		user-select: none;
		background: none;
		padding: 0;
	}

	.nav-steps {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.step {
		background: none;
		color: var(--text-muted);
		padding: 8px 16px;
		border-radius: var(--radius);
		font-size: 0.85rem;
		font-weight: 500;
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.step:hover {
		color: var(--text-secondary);
		background: var(--bg-card);
	}

	.step.active {
		color: var(--accent);
		background: var(--accent-glow);
	}

	.step-num {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		font-size: 0.75rem;
		border: 1px solid currentColor;
	}

	.step.active .step-num {
		background: var(--accent);
		color: var(--bg-primary);
		border-color: var(--accent);
	}

	.step-divider {
		width: 20px;
		height: 1px;
		background: var(--border);
	}

	.main-content {
		flex: 1;
	}

	.error-banner {
		background: rgba(231, 76, 60, 0.1);
		border-bottom: 1px solid var(--danger);
		padding: 12px 24px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		max-width: 1200px;
		margin: 0 auto;
		width: 100%;
	}

	.error-banner p {
		color: var(--danger);
		font-size: 0.9rem;
	}

	.error-banner button {
		background: none;
		color: var(--danger);
		font-size: 0.85rem;
		padding: 4px 12px;
		border: 1px solid var(--danger);
		border-radius: var(--radius);
	}

	.processing-view {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 60vh;
		padding: 40px 24px;
	}

	.processing-card {
		text-align: center;
		max-width: 400px;
	}

	.processing-card h2 {
		margin: 24px 0 16px;
	}

	.phase-label {
		color: var(--text-secondary);
		margin-bottom: 16px;
	}

	.progress-bar {
		height: 4px;
		background: var(--bg-card);
		border-radius: 2px;
		overflow: hidden;
		margin-bottom: 8px;
	}

	.progress-fill {
		height: 100%;
		background: var(--accent);
		border-radius: 2px;
		transition: width 300ms ease;
	}

	.progress-text {
		color: var(--text-muted);
		font-size: 0.85rem;
	}

	.spinner {
		width: 48px;
		height: 48px;
		border: 3px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		margin: 0 auto;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 768px) {
		.header-content {
			flex-direction: column;
			gap: 12px;
		}
		.nav-steps {
			flex-wrap: wrap;
			justify-content: center;
		}
		.step-divider {
			display: none;
		}
	}
</style>
