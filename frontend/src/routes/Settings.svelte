<script>
	import { api, clearUsername } from '$lib/api.js';
	import { currentUser, appState } from '$lib/stores.js';

	let deleting = $state(false);
	let reprocessing = $state(false);
	let message = $state('');
	let stats = $state(null);

	async function loadStats() {
		try {
			stats = await api.getStats();
		} catch {
			// ignore
		}
	}

	$effect(() => {
		loadStats();
	});

	async function handleDeleteAll() {
		if (!confirm('Delete ALL your photos and data? This cannot be undone.')) return;
		deleting = true;
		try {
			await api.deleteAllData();
			message = 'All data deleted.';
			await loadStats();
		} catch (e) {
			message = `Error: ${e.message}`;
		} finally {
			deleting = false;
		}
	}

	async function handleReprocess() {
		reprocessing = true;
		try {
			await api.reprocess();
			message = 'Processing state reset. Go to Upload to re-process.';
			await loadStats();
		} catch (e) {
			message = `Error: ${e.message}`;
		} finally {
			reprocessing = false;
		}
	}

	function handleLogout() {
		clearUsername();
		currentUser.set(null);
		appState.set('login');
	}
</script>

<div class="settings-page">
	<div class="settings-header">
		<h2>Settings</h2>
		<button class="btn-secondary" onclick={() => appState.set('upload')}>← Back</button>
	</div>

	<div class="settings-section">
		<h3>Account</h3>
		<div class="settings-card">
			<div class="setting-row">
				<div>
					<p class="setting-label">Logged in as</p>
					<p class="setting-value">{$currentUser}</p>
				</div>
				<button class="btn-secondary" onclick={handleLogout}>Sign Out</button>
			</div>
		</div>
	</div>

	{#if stats}
	<div class="settings-section">
		<h3>Your Data</h3>
		<div class="settings-card">
			<div class="stats-grid">
				<div class="stat-item">
					<span class="stat-number">{stats.total_photos}</span>
					<span class="stat-label">Photos</span>
				</div>
				<div class="stat-item">
					<span class="stat-number">{stats.total_faces}</span>
					<span class="stat-label">Faces</span>
				</div>
				<div class="stat-item">
					<span class="stat-number">{stats.tagged_photos}</span>
					<span class="stat-label">Tagged</span>
				</div>
				<div class="stat-item">
					<span class="stat-number">{stats.timeline_entries}</span>
					<span class="stat-label">Timeline</span>
				</div>
			</div>
		</div>
	</div>
	{/if}

	<div class="settings-section">
		<h3>Data Management</h3>
		<div class="settings-card">
			<div class="setting-row">
				<div>
					<p class="setting-label">Re-process photos</p>
					<p class="setting-desc">Reset face detection and clustering. Keeps photos and tags.</p>
				</div>
				<button class="btn-secondary" onclick={handleReprocess} disabled={reprocessing}>
					{reprocessing ? 'Resetting...' : 'Re-process'}
				</button>
			</div>
			<hr />
			<div class="setting-row danger-zone">
				<div>
					<p class="setting-label">Delete all data</p>
					<p class="setting-desc">Permanently remove all photos, faces, tags, and timeline data.</p>
				</div>
				<button class="btn-danger" onclick={handleDeleteAll} disabled={deleting}>
					{deleting ? 'Deleting...' : 'Delete Everything'}
				</button>
			</div>
		</div>
	</div>

	{#if message}
		<div class="settings-message">
			<p>{message}</p>
		</div>
	{/if}
</div>

<style>
	.settings-page {
		max-width: 700px;
		margin: 0 auto;
		padding: 40px 24px 80px;
	}

	.settings-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 32px;
	}

	.settings-header h2 {
		font-size: 1.8rem;
		color: var(--text-primary);
	}

	.settings-section {
		margin-bottom: 28px;
	}

	.settings-section h3 {
		font-family: var(--font-sans);
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
		margin-bottom: 10px;
		font-weight: 600;
	}

	.settings-card {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 20px;
	}

	.setting-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
	}

	.setting-label {
		font-weight: 500;
		font-size: 0.95rem;
	}

	.setting-value {
		color: var(--accent);
		font-weight: 600;
		font-size: 1.1rem;
	}

	.setting-desc {
		color: var(--text-muted);
		font-size: 0.8rem;
		margin-top: 2px;
	}

	hr {
		border: none;
		border-top: 1px solid var(--border);
		margin: 16px 0;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 16px;
		text-align: center;
	}

	.stat-item {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.stat-number {
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--accent);
	}

	.stat-label {
		font-size: 0.75rem;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.settings-message {
		margin-top: 16px;
		padding: 12px 20px;
		background: rgba(46, 204, 113, 0.1);
		border: 1px solid var(--success);
		border-radius: var(--radius);
		color: var(--success);
		font-size: 0.9rem;
	}
</style>
