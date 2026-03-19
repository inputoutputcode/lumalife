<script>
	import { setUsername } from '$lib/api.js';
	import { currentUser, appState } from '$lib/stores.js';

	let username = $state('');
	let error = $state('');

	function handleLogin() {
		const name = username.trim();
		if (!name) {
			error = 'Please enter a name';
			return;
		}
		if (name.length < 2) {
			error = 'Name must be at least 2 characters';
			return;
		}
		setUsername(name);
		currentUser.set(name);
		appState.set('upload');
	}

	function handleKeydown(e) {
		if (e.key === 'Enter') handleLogin();
	}
</script>

<div class="login-page">
	<div class="login-card">
		<div class="login-logo">📸</div>
		<h1>LumaLife</h1>
		<p class="login-subtitle">Your life, illuminated through time</p>

		<div class="login-form">
			<label for="username">What's your name?</label>
			<input
				id="username"
				type="text"
				bind:value={username}
				onkeydown={handleKeydown}
				placeholder="Enter your name"
				maxlength="64"
				autofocus
			/>
			{#if error}
				<p class="login-error">{error}</p>
			{/if}
			<button class="btn-primary login-btn" onclick={handleLogin}>
				Get Started
			</button>
		</div>

		<p class="login-hint">Your photos are stored under your name so you can come back anytime.</p>
	</div>
</div>

<style>
	.login-page {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 24px;
		background: var(--bg-primary);
	}

	.login-card {
		max-width: 400px;
		width: 100%;
		text-align: center;
		padding: 48px 36px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
	}

	.login-logo {
		font-size: 3rem;
		margin-bottom: 12px;
	}

	h1 {
		font-size: 2rem;
		color: var(--accent);
		margin-bottom: 8px;
	}

	.login-subtitle {
		color: var(--text-secondary);
		font-size: 0.95rem;
		margin-bottom: 36px;
	}

	.login-form {
		display: flex;
		flex-direction: column;
		gap: 12px;
		text-align: left;
	}

	label {
		font-weight: 500;
		font-size: 0.9rem;
		color: var(--text-primary);
	}

	input {
		padding: 12px 16px;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		font-size: 1rem;
		font-family: var(--font-sans);
		background: var(--bg-primary);
		color: var(--text-primary);
		outline: none;
		transition: border-color var(--transition);
	}

	input:focus {
		border-color: var(--accent);
	}

	.login-btn {
		margin-top: 8px;
		width: 100%;
	}

	.login-error {
		color: var(--danger);
		font-size: 0.85rem;
	}

	.login-hint {
		margin-top: 24px;
		font-size: 0.8rem;
		color: var(--text-muted);
	}
</style>
