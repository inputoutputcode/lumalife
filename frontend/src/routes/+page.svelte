<script>
	import { appState, stats, currentUser } from '$lib/stores.js';
	import { api, getStoredUsername, setUsername } from '$lib/api.js';
	import { onMount } from 'svelte';
	import Login from './Login.svelte';
	import Upload from './Upload.svelte';
	import Identify from './Identify.svelte';
	import Tag from './Tag.svelte';
	import Timeline from './Timeline.svelte';
	import Settings from './Settings.svelte';

	let currentState = $state('login');
	let processingProgress = $state(null);
	let error = $state(null);
	let appStats = $state(null);
	let user = $state(null);
	let showUserMenu = $state(false);

	appState.subscribe((v) => (currentState = v));
	currentUser.subscribe((v) => (user = v));

	onMount(async () => {
		// Check for stored user session
		const stored = getStoredUsername();
		if (stored) {
			currentUser.set(stored);
			setUsername(stored);
			await loadAppState();
		} else {
			appState.set('login');
		}
	});

	async function loadAppState() {
		try {
			appStats = await api.getStats();
			stats.set(appStats);

			if (appStats.timeline_entries > 0) {
				appState.set('timeline');
			} else if (appStats.tagged_photos >= 8) {
				appState.set('tag');
			} else if (appStats.target_faces > 0) {
				appState.set('tag');
			} else if (appStats.total_clusters > 0) {
				appState.set('identify');
			} else {
				appState.set('upload');
			}
		} catch {
			appState.set('upload');
		}
	}

	// Watch for user login
	currentUser.subscribe(async (v) => {
		if (v && currentState === 'login') {
			await loadAppState();
		}
	});

	function goTo(state) {
		if (!user && state !== 'login') return;
		appState.set(state);
		error = null;
		showUserMenu = false;
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
			if (!error) {
				appState.set('identify');
			}
			processingProgress = null;
		};
	}
</script>

{#if currentState === 'login'}
	<Login />
{:else}
	<div class="app">
		<header class="app-header">
			<div class="header-content">
				<button class="logo" onclick={() => goTo('upload')}>LumaLife</button>
				<nav class="nav-steps">
					<button class="step" class:active={currentState === 'upload'} onclick={() => goTo('upload')}>
						<span class="step-num">1</span> Upload
					</button>
					<span class="step-divider"></span>
					<button class="step" class:active={currentState === 'processing' || currentState === 'identify'} onclick={() => goTo('identify')}>
						<span class="step-num">2</span> Identify
					</button>
					<span class="step-divider"></span>
					<button class="step" class:active={currentState === 'tag'} onclick={() => goTo('tag')}>
						<span class="step-num">3</span> Tag
					</button>
					<span class="step-divider"></span>
					<button class="step" class:active={currentState === 'timeline' || currentState === 'building'} onclick={() => goTo('timeline')}>
						<span class="step-num">4</span> Timeline
					</button>
				</nav>
				<div class="user-meta">
					<span class="user-name-display">{user}</span>
					<button class="meta-link" onclick={() => goTo('settings')} title="Settings">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
					</button>
					<button class="meta-link signout-link" onclick={() => { import('$lib/api.js').then(m => { m.clearUsername(); }); currentUser.set(null); appState.set('login'); }} title="Sign Out">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
						<span>Sign Out</span>
					</button>
				</div>
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
									<div class="progress-fill" style="width: {processingProgress.total > 0 ? (processingProgress.current / processingProgress.total) * 100 : 0}%"></div>
								</div>
								<p class="progress-text">{processingProgress.current} / {processingProgress.total} photos</p>
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
			{:else if currentState === 'settings'}
				<Settings />
			{/if}
		</main>
	</div>
{/if}



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
		background: rgba(255, 255, 255, 0.92);
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
		color: white;
		border-color: var(--accent);
	}

	.step-divider {
		width: 20px;
		height: 1px;
		background: var(--border);
	}

	.user-meta {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.user-name-display {
		font-size: 0.9rem;
		font-weight: 500;
		color: var(--text-secondary);
		max-width: 120px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meta-link {
		display: flex;
		align-items: center;
		gap: 5px;
		background: none;
		padding: 6px;
		border-radius: var(--radius);
		color: var(--text-muted);
		font-size: 0.8rem;
	}

	.meta-link:hover {
		color: var(--text-primary);
		background: var(--bg-hover);
	}

	.meta-link span {
		font-weight: 500;
	}

	.signout-link:hover {
		color: var(--text-primary);
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
		to { transform: rotate(360deg); }
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
