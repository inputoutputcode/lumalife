<script>
	import { onMount } from 'svelte';

	let { era, index = 0, onPhotoClick, onVisible } = $props();
	let sectionEl = $state(null);
	let photoEls = $state([]);

	onMount(async () => {
		const { gsap, ScrollTrigger } = await import('$lib/gsap-setup.js');

		if (sectionEl) {
			// Observe when section enters viewport
			ScrollTrigger.create({
				trigger: sectionEl,
				start: 'top 60%',
				onEnter: () => onVisible?.(),
				onEnterBack: () => onVisible?.(),
			});

			// Animate era label
			const label = sectionEl.querySelector('.era-label');
			if (label) {
				gsap.from(label, {
					opacity: 0,
					x: -40,
					duration: 0.7,
					ease: 'power2.out',
					scrollTrigger: {
						trigger: label,
						start: 'top 85%',
						toggleActions: 'play none none reverse',
					},
				});
			}

			// Animate each photo
			const photos = sectionEl.querySelectorAll('.timeline-photo');
			photos.forEach((photo, i) => {
				gsap.from(photo, {
					opacity: 0,
					scale: 0.92,
					y: 50,
					duration: 0.8,
					delay: i * 0.08,
					ease: 'power3.out',
					scrollTrigger: {
						trigger: photo,
						start: 'top 90%',
						toggleActions: 'play none none reverse',
					},
				});
			});
		}
	});
</script>

<section class="timeline-section" bind:this={sectionEl}>
	<div class="era-label">
		<div class="era-line"></div>
		<h2>{era.label}</h2>
		<span class="era-count">{era.photos.length} photo{era.photos.length !== 1 ? 's' : ''}</span>
	</div>

	<div class="photos-layout">
		{#each era.photos as photo, i}
			<button
				class="timeline-photo"
				class:full-bleed={i === 0 || (i % 5 === 0 && era.photos.length > 3)}
				onclick={() => onPhotoClick?.(photo)}
			>
				<img
					src={photo.url}
					alt={photo.original_filename || 'Photo'}
					loading="lazy"
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
		padding: 40px 24px 60px;
		max-width: 1200px;
		margin: 0 auto;
	}

	.era-label {
		display: flex;
		align-items: center;
		gap: 16px;
		margin-bottom: 32px;
	}

	.era-line {
		width: 40px;
		height: 2px;
		background: var(--accent);
		flex-shrink: 0;
	}

	.era-label h2 {
		font-size: 2rem;
		color: var(--accent);
		white-space: nowrap;
	}

	.era-count {
		color: var(--text-muted);
		font-size: 0.85rem;
		white-space: nowrap;
	}

	.photos-layout {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 12px;
	}

	.timeline-photo {
		position: relative;
		overflow: hidden;
		border-radius: var(--radius);
		cursor: pointer;
		background: var(--bg-card);
		border: none;
		padding: 0;
		aspect-ratio: 4/3;
	}

	.timeline-photo.full-bleed {
		grid-column: 1 / -1;
		aspect-ratio: 21/9;
	}

	.timeline-photo img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		transition: transform 600ms ease;
	}

	.timeline-photo:hover img {
		transform: scale(1.05);
	}

	.photo-overlay {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		padding: 20px 16px 12px;
		background: linear-gradient(transparent, rgba(0, 0, 0, 0.7));
		opacity: 0;
		transition: opacity 300ms ease;
	}

	.timeline-photo:hover .photo-overlay {
		opacity: 1;
	}

	.photo-year {
		color: var(--accent);
		font-family: var(--font-serif);
		font-size: 1.2rem;
	}

	@media (max-width: 768px) {
		.photos-layout {
			grid-template-columns: repeat(2, 1fr);
		}

		.timeline-photo.full-bleed {
			aspect-ratio: 16/9;
		}

		.era-label h2 {
			font-size: 1.5rem;
		}
	}

	@media (max-width: 480px) {
		.photos-layout {
			grid-template-columns: 1fr;
		}
	}
</style>
