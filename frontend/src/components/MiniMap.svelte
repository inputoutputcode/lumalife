<script>
	let { eras = [], activeEra = 0, onEraClick } = $props();
</script>

<nav class="minimap">
	<div class="minimap-rail">
		{#each eras as era, i}
			<button
				class="minimap-item"
				class:active={i === activeEra}
				onclick={() => onEraClick?.(i)}
				title={era.label}
			>
				<span class="minimap-dot"></span>
				<span class="minimap-label">{era.label}</span>
			</button>
		{/each}
	</div>
</nav>

<style>
	.minimap {
		position: fixed;
		right: 20px;
		top: 50%;
		transform: translateY(-50%);
		z-index: 50;
	}

	.minimap-rail {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.minimap-item {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 8px;
		background: none;
		border-radius: var(--radius);
		cursor: pointer;
		justify-content: flex-end;
	}

	.minimap-item:hover {
		background: var(--bg-card);
	}

	.minimap-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--border);
		transition: all var(--transition);
		flex-shrink: 0;
		order: 2;
	}

	.minimap-item.active .minimap-dot {
		background: var(--accent);
		box-shadow: 0 0 8px var(--accent-glow);
		width: 10px;
		height: 10px;
	}

	.minimap-label {
		font-size: 0.7rem;
		color: var(--text-muted);
		opacity: 0;
		transition: opacity var(--transition);
		white-space: nowrap;
		order: 1;
	}

	.minimap-item:hover .minimap-label,
	.minimap-item.active .minimap-label {
		opacity: 1;
	}

	.minimap-item.active .minimap-label {
		color: var(--accent);
	}

	@media (max-width: 768px) {
		.minimap {
			display: none;
		}
	}
</style>
