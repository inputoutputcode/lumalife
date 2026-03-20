<script>
	import { onMount } from 'svelte';

	let { era, index = 0, onPhotoClick, onVisible } = $props();
	let sectionEl = $state(null);

	// Dot size based on photo count: min 12px, max 28px
	$effect(() => {});
	function getDotSize(count) {
		return Math.min(28, Math.max(12, 8 + count * 2.5));
	}

	onMount(async () => {
		const { gsap, ScrollTrigger } = await import('$lib/gsap-setup.js');

		if (sectionEl) {
			ScrollTrigger.create({
				trigger: sectionEl,
				start: 'top 60%',
				onEnter: () => onVisible?.(),
				onEnterBack: () => onVisible?.(),
			});

			// Animate photos
			const photos = sectionEl.querySelectorAll('.timeline-photo');
			photos.forEach((photo, i) => {
				gsap.from(photo, {
					opacity: 0,
					x: 30,
					duration: 0.6,
					delay: i * 0.06,
					ease: 'power2.out',
					scrollTrigger: {
						trigger: photo,
						start: 'top 90%',
						toggleActions: 'play none none reverse',
					},
				});
			});

			// Animate era label
			const label = sectionEl.querySelector('.era-info');
			if (label) {
				gsap.from(label, {
					opacity: 0,
					y: 20,
					duration: 0.5,
					ease: 'power2.out',
					scrollTrigger: {
						trigger: label,
						start: 'top 85%',
						toggleActions: 'play none none reverse',
					},
				});
			}
		}
	});
</script>

<section class="timeline-section" bind:this={sectionEl}>
	<div class="timeline-marker">
		<span class="timeline-year-label">{era.label}</span>
		<div
			class="timeline-dot"
			style="width: {getDotSize(era.photos.length)}px; height: {getDotSize(era.photos.length)}px;"
		></div>
	</div>

	<div class="era-info">
		<span class="era-count">{era.photos.length} photo{era.photos.length !== 1 ? 's' : ''}{era.label === 'Undated' ? ' · not yet dated' : ''}</span>
	</div>

	<div class="photos-layout">
		{#each era.photos as photo, i}
			<button
				class="timeline-photo"
				onclick={() => onPhotoClick?.(photo)}
			>
				<img
					src={photo.url}
					alt={photo.original_filename || 'Photo'}
					loading="eager"
				/>
				<div class="photo-overlay">
					<span class="photo-year">
						{#if photo.tagged_year}
							{photo.tagged_year}
						{:else if photo.estimated_year}
							~{photo.estimated_year}
						{/if}
					</span>
				</div>
			</button>
		{/each}
	</div>
</section>

<style>
	.timeline-section {
		position: relative;
		padding: 0 0 48px 0;
	}

	.timeline-marker {
		position: absolute;
		left: -31px;
		top: 0;
		transform: translateX(-50%);
		display: flex;
		flex-direction: row;
		align-items: center;
		z-index: 2;
	}

	.timeline-year-label {
		position: absolute;
		right: calc(100% + 12px);
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--accent);
		white-space: nowrap;
	}

	.timeline-dot {
		border-radius: 50%;
		background: var(--accent);
		border: 3px solid var(--bg-primary);
		box-shadow: 0 0 0 2px var(--accent);
		transition: transform 200ms ease;
	}

	.timeline-section:hover .timeline-dot {
		transform: scale(1.15);
	}

	.era-info {
		margin-bottom: 12px;
	}

	.era-count {
		color: var(--text-muted);
		font-size: 0.8rem;
		white-space: nowrap;
	}

	.photos-layout {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
		gap: 8px;
	}

	.timeline-photo {
		position: relative;
		overflow: hidden;
		border-radius: var(--radius);
		cursor: pointer;
		background: var(--bg-card);
		border: none;
		padding: 0;
		aspect-ratio: 1;
	}

	.timeline-photo img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		transition: transform 400ms ease;
	}

	.timeline-photo:hover img {
		transform: scale(1.04);
	}

	.photo-overlay {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		padding: 16px 12px 8px;
		background: linear-gradient(transparent, rgba(0, 0, 0, 0.6));
		opacity: 0;
		transition: opacity 200ms ease;
	}

	.timeline-photo:hover .photo-overlay {
		opacity: 1;
	}

	.photo-year {
		color: white;
		font-size: 0.9rem;
		font-weight: 600;
	}

	@media (max-width: 768px) {
		.photos-layout {
			grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
		}

		.timeline-photo.featured {
			grid-column: span 1;
			grid-row: span 1;
			aspect-ratio: 4/3;
		}

		.era-title {
			font-size: 1.1rem;
		}
	}
</style>
