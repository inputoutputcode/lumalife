import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export { gsap, ScrollTrigger };

export function createScrollAnimation(element, options = {}) {
	const defaults = {
		opacity: 0,
		y: 60,
		duration: 1,
		ease: 'power2.out',
		scrollTrigger: {
			trigger: element,
			start: 'top 85%',
			end: 'top 20%',
			toggleActions: 'play none none reverse',
		},
	};

	return gsap.from(element, { ...defaults, ...options });
}

export function createPhotoReveal(element, index = 0) {
	return gsap.from(element, {
		opacity: 0,
		scale: 0.9,
		y: 40,
		duration: 0.8,
		delay: index * 0.1,
		ease: 'power3.out',
		scrollTrigger: {
			trigger: element,
			start: 'top 90%',
			toggleActions: 'play none none reverse',
		},
	});
}

export function createEraHeader(element) {
	return gsap.from(element, {
		opacity: 0,
		x: -30,
		duration: 0.6,
		ease: 'power2.out',
		scrollTrigger: {
			trigger: element,
			start: 'top 80%',
			toggleActions: 'play none none reverse',
		},
	});
}
