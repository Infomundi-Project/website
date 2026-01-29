/**
 * World Map Zoom Controller
 * Handles smooth viewBox transitions for SVG map zoom
 * Optimized for performance with GPU acceleration
 */
(() => {
  const svg = document.getElementById('world-map');
  const backBtn = document.getElementById('map-back-btn');
  if (!svg) return;

  // Default viewBox (world view)
  const DEFAULT_VIEWBOX = { x: 0, y: 0, w: 1000, h: 500 };

  // Region viewBox configurations
  const REGIONS = {
    'north-america': { x: 100, y: 40, w: 280, h: 180 },
    'central-america': { x: 180, y: 150, w: 200, h: 130 },
    'south-america': { x: 240, y: 200, w: 180, h: 240 },
    'europe': { x: 440, y: 60, w: 180, h: 130 },
    'asia': { x: 520, y: 40, w: 440, h: 300 },
    'africa': { x: 420, y: 130, w: 220, h: 260 },
    'oceania': { x: 700, y: 220, w: 280, h: 200 }
  };

  let animationFrame = null;
  let currentRegion = 'continents';

  // Parse current viewBox
  const parseViewBox = () => {
    const vb = svg.getAttribute('viewBox').split(' ').map(Number);
    return { x: vb[0], y: vb[1], w: vb[2], h: vb[3] };
  };

  // Set viewBox
  const setViewBox = (vb) => {
    svg.setAttribute('viewBox', `${vb.x.toFixed(1)} ${vb.y.toFixed(1)} ${vb.w.toFixed(1)} ${vb.h.toFixed(1)}`);
  };

  // Show/hide back button
  const updateBackButton = (show) => {
    if (backBtn) {
      backBtn.style.display = show ? 'inline-flex' : 'none';
    }
  };

  // Faster easing function
  const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

  // Animate viewBox transition (optimized)
  const animateViewBox = (target, duration = 400) => {
    if (animationFrame) {
      cancelAnimationFrame(animationFrame);
    }

    const start = parseViewBox();
    const startTime = performance.now();

    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeOutCubic(progress);

      const current = {
        x: start.x + (target.x - start.x) * eased,
        y: start.y + (target.y - start.y) * eased,
        w: start.w + (target.w - start.w) * eased,
        h: start.h + (target.h - start.h) * eased
      };

      svg.setAttribute('viewBox', `${current.x.toFixed(1)} ${current.y.toFixed(1)} ${current.w.toFixed(1)} ${current.h.toFixed(1)}`);

      if (progress < 1) {
        animationFrame = requestAnimationFrame(animate);
      }
    };

    animationFrame = requestAnimationFrame(animate);
  };

  // Show/hide layers
  const showLayer = (layerId) => {
    const allLayers = document.querySelectorAll('.country-layer');
    const continentsLayer = document.getElementById('continents');

    if (layerId === 'continents' || !layerId) {
      allLayers.forEach(layer => {
        layer.style.opacity = '0';
        layer.style.visibility = 'hidden';
        layer.style.pointerEvents = 'none';
      });
      if (continentsLayer) {
        continentsLayer.style.opacity = '1';
        continentsLayer.style.visibility = 'visible';
        continentsLayer.style.pointerEvents = 'auto';
      }
    } else {
      if (continentsLayer) {
        continentsLayer.style.opacity = '0';
        continentsLayer.style.visibility = 'hidden';
        continentsLayer.style.pointerEvents = 'none';
      }
      allLayers.forEach(layer => {
        if (layer.id === layerId) {
          layer.style.opacity = '1';
          layer.style.visibility = 'visible';
          layer.style.pointerEvents = 'auto';
        } else {
          layer.style.opacity = '0';
          layer.style.visibility = 'hidden';
          layer.style.pointerEvents = 'none';
        }
      });
    }
  };

  // Navigate to region
  const navigateTo = (regionId) => {
    if (regionId === 'continents' || !regionId || regionId === '') {
      currentRegion = 'continents';
      showLayer('continents');
      animateViewBox(DEFAULT_VIEWBOX, 350);
      updateBackButton(false);
    } else if (REGIONS[regionId]) {
      currentRegion = regionId;
      showLayer(regionId);
      animateViewBox(REGIONS[regionId], 400);
      updateBackButton(true);
    }
  };

  // Handle continent clicks
  const handleContinentClick = (e) => {
    const continent = e.target.closest('.continent');
    if (continent) {
      e.preventDefault();
      e.stopPropagation();
      const href = continent.getAttribute('href');
      if (href && href.startsWith('#')) {
        const regionId = href.slice(1);
        history.pushState({ region: regionId }, '', href);
        navigateTo(regionId);
      }
    }
  };

  // Handle clicks outside region (on empty SVG area)
  const handleSvgClick = (e) => {
    // Check if we're currently in a region view (not continents)
    if (currentRegion === 'continents') return;

    // Check if click was on a country element
    const country = e.target.closest('.country');
    const continent = e.target.closest('.continent');

    // If click was not on a country or continent, go back to world view
    if (!country && !continent) {
      e.preventDefault();
      e.stopPropagation();
      handleBackClick();
    }
  };

  // Handle back button click
  const handleBackClick = () => {
    history.pushState({ region: 'continents' }, '', window.location.pathname + window.location.search);
    navigateTo('continents');
  };

  // Handle browser back/forward
  const handlePopState = () => {
    const hash = window.location.hash.slice(1);
    navigateTo(hash || 'continents');
  };

  // Initialize
  const init = () => {
    // Always start with default view (reset zoom on refresh)
    setViewBox(DEFAULT_VIEWBOX);
    showLayer('continents');
    updateBackButton(false);

    // Clear hash on page load to ensure clean state
    if (window.location.hash) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }

    // Event listeners
    window.addEventListener('popstate', handlePopState);
    svg.addEventListener('click', handleContinentClick);
    svg.addEventListener('click', handleSvgClick);

    if (backBtn) {
      backBtn.addEventListener('click', handleBackClick);
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
