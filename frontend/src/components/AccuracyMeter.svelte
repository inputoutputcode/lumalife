<script>
	let { tagged = 0, total = 0, minRequired = 8, recommended = 15 } = $props();

	function getStars() {
		if (tagged >= recommended) return 5;
		if (tagged >= 12) return 4;
		if (tagged >= minRequired) return 3;
		if (tagged >= 5) return 2;
		if (tagged >= 2) return 1;
		return 0;
	}

	function getMessage() {
		const stars = getStars();
		const remaining = minRequired - tagged;
		if (remaining > 0) {
			return `Tag ${remaining} more photo${remaining !== 1 ? 's' : ''} to unlock timeline`;
		}
		const toRecommended = recommended - tagged;
		if (toRecommended > 0) {
			return `Tag ${toRecommended} more for better results`;
		}
		return 'Excellent coverage!';
	}
</script>

<div class="accuracy-meter">
	<div class="meter-header">
		<span class="stars">
			{#each Array(5) as _, i}
				<span class="star" class:filled={i < getStars()}>
					{#if i < getStars()}
						&#9733;
					{:else}
						&#9734;
					{/if}
				</span>
			{/each}
		</span>
		<span class="count">{tagged} / {total} tagged</span>
	</div>

	<div class="meter-bar">
		<div class="meter-fill" style="width: {Math.min((tagged / recommended) * 100, 100)}%"></div>
		<div class="meter-min-marker" style="left: {(minRequired / recommended) * 100}%">
			<span class="marker-label">min ({minRequired})</span>
		</div>
	</div>

	<p class="meter-message">{getMessage()}</p>
</div>

<style>
	.accuracy-meter {
		background: var(--bg-card);
		border-radius: var(--radius-lg);
		padding: 20px 24px;
		border: 1px solid var(--border);
	}

	.meter-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 12px;
	}

	.stars {
		display: flex;
		gap: 2px;
	}

	.star {
		font-size: 1.3rem;
		color: var(--text-muted);
	}

	.star.filled {
		color: var(--accent);
	}

	.count {
		color: var(--text-secondary);
		font-size: 0.9rem;
		font-weight: 500;
	}

	.meter-bar {
		position: relative;
		height: 6px;
		background: var(--bg-primary);
		border-radius: 3px;
		margin-bottom: 8px;
	}

	.meter-fill {
		height: 100%;
		background: var(--accent);
		border-radius: 3px;
		transition: width 400ms ease;
	}

	.meter-min-marker {
		position: absolute;
		top: -4px;
		transform: translateX(-50%);
		width: 2px;
		height: 14px;
		background: var(--text-muted);
	}

	.marker-label {
		position: absolute;
		top: 18px;
		left: 50%;
		transform: translateX(-50%);
		font-size: 0.7rem;
		color: var(--text-muted);
		white-space: nowrap;
	}

	.meter-message {
		color: var(--text-secondary);
		font-size: 0.85rem;
		margin-top: 4px;
	}
</style>
