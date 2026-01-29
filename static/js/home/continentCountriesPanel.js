/**
 * Continent Countries Panel
 * Shows a beautiful sidebar with countries when a continent is clicked on the map
 */
(() => {
  // Check if we're on the homepage with the world map
  const worldMap = document.getElementById('world-map');
  if (!worldMap) return;

  const FLAG_BASE = '/static/img/flags/4x3/';

  // Mapping of SVG continent IDs to API region names
  const CONTINENT_TO_REGION = {
    'north-america': 'North America',
    'central-america': 'Central America',
    'south-america': 'Latin America',
    'europe': 'Europe',
    'asia': 'Asia',
    'africa': 'Africa',
    'oceania': 'Oceania'
  };

  // Cache for country data per continent
  const countryDataCache = {};

  // Cache for region countries data (avoids re-fetching on auto-open)
  const regionCountriesCache = {};

  // Panel elements (will be created dynamically)
  let panelOverlay = null;
  let panel = null;
  let panelContent = null;
  let panelTitle = null;

  // State tracking for auto-open on hover
  let currentRegionId = null;
  let isAutoOpening = false;

  /**
   * Create panel HTML structure
   */
  const createPanel = () => {
    // Create panel (NO overlay - map stays fully interactive)
    panel = document.createElement('div');
    panel.className = 'continent-countries-panel';

    // Create header
    const header = document.createElement('div');
    header.className = 'continent-panel-header';

    panelTitle = document.createElement('h3');
    panelTitle.className = 'continent-panel-title';
    panelTitle.innerHTML = '<i class="fa-solid fa-earth-americas"></i><span>Countries</span>';

    const hint = document.createElement('div');
    hint.className = 'continent-panel-hint';
    hint.innerHTML = '<i class="fa-solid fa-computer-mouse"></i>Hover to highlight on map';

    const closeBtn = document.createElement('button');
    closeBtn.className = 'continent-panel-close';
    closeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    closeBtn.setAttribute('aria-label', 'Close panel');
    closeBtn.addEventListener('click', closePanel);

    const titleContainer = document.createElement('div');
    titleContainer.className = 'continent-panel-title-container';

    titleContainer.appendChild(panelTitle);
    titleContainer.appendChild(hint);

    header.appendChild(titleContainer);
    header.appendChild(closeBtn);

    // Create content area
    panelContent = document.createElement('div');
    panelContent.className = 'continent-panel-content';

    // Assemble panel
    panel.appendChild(header);
    panel.appendChild(panelContent);

    // Add to document
    document.body.appendChild(panel);
  };

  /**
   * Open panel with loading state
   */
  const openPanel = (continentName, countryCount = 0) => {
    if (!panel) createPanel();

    // Update title with country count
    const subtitle = countryCount > 0 ? `<span class="continent-panel-subtitle">${countryCount} countries</span>` : '';
    panelTitle.innerHTML = `<i class="fa-solid fa-earth-americas"></i><span>${continentName}</span>${subtitle}`;

    // Show loading
    panelContent.innerHTML = `
      <div class="continent-panel-loading">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
        <p>Loading countries...</p>
      </div>
    `;

    // Activate panel
    panel.classList.add('active');
  };

  /**
   * Close panel
   */
  const closePanel = () => {
    if (!panel) return;

    panel.classList.remove('active');

    // Clear any map highlights
    clearMapHighlights();

    // Remove all country hover listeners from map
    worldMap.querySelectorAll('.country').forEach(el => {
      if (el._hoverHandler) {
        el.removeEventListener('mouseenter', el._hoverHandler);
        el.removeEventListener('mouseleave', el._leaveHandler);
        el.removeEventListener('click', el._clickHandler);
        delete el._hoverHandler;
        delete el._leaveHandler;
        delete el._clickHandler;
      }
    });
  };

  /**
   * Highlight a country on the map
   */
  const highlightCountryOnMap = (countryCode) => {
    if (!countryCode) return;

    // Find the country element in the SVG (try both uppercase and lowercase)
    let countryElement = worldMap.querySelector(`.country[data-country="${countryCode}"]`);
    if (!countryElement) {
      countryElement = worldMap.querySelector(`.country[data-country="${countryCode.toLowerCase()}"]`);
    }

    if (!countryElement) return;

    // Clear previous highlights on map (but not on cards)
    worldMap.querySelectorAll('.country-highlight, .country-dim').forEach(el => {
      el.classList.remove('country-highlight', 'country-dim');
    });

    // Add highlight class to this country
    countryElement.classList.add('country-highlight');

    // Dim other countries in the same region
    const region = countryElement.getAttribute('data-region');
    const regionCountries = worldMap.querySelectorAll(`.country[data-region="${region}"]`);
    regionCountries.forEach(el => {
      if (el !== countryElement) {
        el.classList.add('country-dim');
      }
    });
  };

  /**
   * Clear all map and card highlights
   */
  const clearMapHighlights = (clearCards = true) => {
    // Always clear map highlights
    worldMap.querySelectorAll('.country-highlight, .country-dim').forEach(el => {
      el.classList.remove('country-highlight', 'country-dim');
    });

    // Optionally clear card highlights
    if (clearCards && panelContent) {
      panelContent.querySelectorAll('.country-card.highlighted').forEach(card => {
        card.classList.remove('highlighted');
      });
    }
  };

  /**
   * Format number with locale
   * Handles both raw numbers and pre-formatted strings from the API
   */
  const formatNumber = (num) => {
    if (num === null || num === undefined || num === '') return 'N/A';
    if (typeof num === 'string') return num; // Already formatted by API
    return new Intl.NumberFormat('en-US', { notation: 'compact', compactDisplay: 'short' }).format(num);
  };

  /**
   * Get flag URL for country
   */
  const getFlagUrl = (countryCode) => {
    if (!countryCode) return null;
    const code = countryCode.toLowerCase();
    return `${FLAG_BASE}${code}.svg`;
  };

  /**
   * Load country data from API
   */
  const loadCountryData = async (countryCode) => {
    try {
      const response = await fetch(`/api/country/${countryCode.toLowerCase()}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      if (!response.ok) return null;
      const data = await response.json();
      return data && data[0] ? data[0] : data;
    } catch (error) {
      console.warn(`Could not load data for ${countryCode}:`, error);
      return null;
    }
  };

  /**
   * Create country card HTML
   */
  const createCountryCard = (country, detailedData) => {
    const card = document.createElement('div');
    card.className = 'country-card';
    card.setAttribute('tabindex', '0');
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', `View news from ${country.name}`);

    const countryCode = (country.code || country.cca2 || '').toUpperCase();
    card.dataset.countryCode = countryCode; // Store country code for easy matching
    const flagUrl = getFlagUrl(countryCode);

    // Extract detailed info - handle both API format (strings) and raw JSON format (arrays/objects)
    const capital = Array.isArray(detailedData?.capital)
      ? detailedData.capital[0]
      : (detailedData?.capital || 'N/A');
    const population = detailedData?.population ?? null;
    const region = detailedData?.subregion || detailedData?.region || 'N/A';
    const languages = typeof detailedData?.languages === 'string'
      ? detailedData.languages
      : (detailedData?.languages && typeof detailedData.languages === 'object'
        ? Object.values(detailedData.languages).slice(0, 2).join(', ')
        : 'N/A');

    card.innerHTML = `
      <div class="country-card-flag">
        ${flagUrl ? `<img src="${flagUrl}" alt="${country.name} flag" loading="lazy">` : '<i class="fa-solid fa-flag fa-3x text-muted"></i>'}
      </div>
      <div class="country-card-info">
        <h4 class="country-card-name">
          ${country.name}
          <i class="fa-solid fa-arrow-right"></i>
        </h4>
        <div class="country-card-details">
          ${capital !== 'N/A' ? `
            <div class="country-detail-row">
              <i class="fa-solid fa-city"></i>
              <span class="country-detail-label">Capital:</span>
              <span>${capital}</span>
            </div>
          ` : ''}
          ${population ? `
            <div class="country-detail-row">
              <i class="fa-solid fa-users"></i>
              <span class="country-detail-label">Population:</span>
              <span>${formatNumber(population)}</span>
            </div>
          ` : ''}
          ${region !== 'N/A' ? `
            <div class="country-detail-row">
              <i class="fa-solid fa-location-dot"></i>
              <span class="country-detail-label">Region:</span>
              <span>${region}</span>
            </div>
          ` : ''}
          ${languages !== 'N/A' ? `
            <div class="country-detail-row">
              <i class="fa-solid fa-language"></i>
              <span class="country-detail-label">Language:</span>
              <span>${languages}</span>
            </div>
          ` : ''}
        </div>
      </div>
    `;

    // Add click handler to navigate to country news
    const handleClick = () => {
      window.location.href = `/news?country=${countryCode.toLowerCase()}`;
    };

    card.addEventListener('click', handleClick);
    card.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleClick();
      }
    });

    // Add hover handlers to highlight country on map
    card.addEventListener('mouseenter', () => {
      // Clear previous card highlights
      if (panelContent) {
        panelContent.querySelectorAll('.country-card.highlighted').forEach(c => {
          c.classList.remove('highlighted');
        });
      }

      // Highlight country on map
      highlightCountryOnMap(countryCode);

      // Highlight this card
      card.classList.add('highlighted');
    });

    card.addEventListener('mouseleave', () => {
      clearMapHighlights();
    });

    return card;
  };

  /**
   * Update an existing card's detail rows with API data
   */
  const updateCardDetails = (card, detailedData) => {
    if (!detailedData) return;

    const detailsDiv = card.querySelector('.country-card-details');
    if (!detailsDiv) return;

    const capital = Array.isArray(detailedData.capital)
      ? detailedData.capital[0]
      : (detailedData.capital || 'N/A');
    const population = detailedData.population ?? null;
    const languages = typeof detailedData.languages === 'string'
      ? detailedData.languages
      : (detailedData.languages && typeof detailedData.languages === 'object'
        ? Object.values(detailedData.languages).slice(0, 2).join(', ')
        : 'N/A');

    detailsDiv.innerHTML = `
      ${capital && capital !== 'N/A' ? `
        <div class="country-detail-row">
          <i class="fa-solid fa-city"></i>
          <span class="country-detail-label">Capital:</span>
          <span>${capital}</span>
        </div>
      ` : ''}
      ${population !== null && population !== undefined ? `
        <div class="country-detail-row">
          <i class="fa-solid fa-users"></i>
          <span class="country-detail-label">Population:</span>
          <span>${formatNumber(population)}</span>
        </div>
      ` : ''}
      ${languages && languages !== 'N/A' ? `
        <div class="country-detail-row">
          <i class="fa-solid fa-language"></i>
          <span class="country-detail-label">Language:</span>
          <span>${languages}</span>
        </div>
      ` : ''}
    `;
  };

  /**
   * Render countries in panel
   * Cards are created immediately for instant interaction;
   * detailed data is loaded in parallel and cards are updated as data arrives
   */
  const renderCountries = async (countries, continentName) => {
    if (!countries || countries.length === 0) {
      panelContent.innerHTML = `
        <div class="continent-panel-empty">
          <i class="fa-solid fa-earth-americas"></i>
          <h5>No countries found</h5>
          <p>We couldn't find any countries for ${continentName}.</p>
        </div>
      `;
      return;
    }

    // Update title with country count
    const subtitle = `<span class="continent-panel-subtitle">${countries.length} ${countries.length === 1 ? 'country' : 'countries'}</span>`;
    panelTitle.innerHTML = `<i class="fa-solid fa-earth-americas"></i><span>${continentName}</span>${subtitle}`;

    // Clear content
    panelContent.innerHTML = '';

    // Step 1: Create all cards immediately with basic info (name + flag only)
    const cardEntries = countries.map(country => {
      const countryCode = (country.code || country.cca2 || '').toUpperCase();
      const cached = countryDataCache[countryCode];
      const card = createCountryCard(country, cached || null);
      panelContent.appendChild(card);
      return { country, card, countryCode, hadCache: !!cached };
    });

    // Step 2: Set up map hover listeners immediately (no waiting for API)
    addMapCountryListeners(countries);

    // Step 3: Load detailed data in parallel and update cards as data arrives
    const loadPromises = cardEntries
      .filter(entry => !entry.hadCache && entry.countryCode)
      .map(async ({ card, countryCode }) => {
        const detailedData = await loadCountryData(countryCode);
        if (detailedData) {
          countryDataCache[countryCode] = detailedData;
          updateCardDetails(card, detailedData);
        }
      });

    await Promise.all(loadPromises);
  };

  /**
   * Add hover and click listeners to countries in the map
   */
  const addMapCountryListeners = (countries) => {
    countries.forEach(country => {
      const countryCode = (country.code || country.cca2 || '').toUpperCase();

      // Try multiple variations to find the country element
      let countryElement = worldMap.querySelector(`.country[data-country="${countryCode}"]`);
      if (!countryElement) {
        countryElement = worldMap.querySelector(`.country[data-country="${countryCode.toLowerCase()}"]`);
      }

      if (!countryElement) return;

      // Remove existing listeners to avoid duplicates
      if (countryElement._hoverHandler) {
        countryElement.removeEventListener('mouseenter', countryElement._hoverHandler);
        countryElement.removeEventListener('mouseleave', countryElement._leaveHandler);
        countryElement.removeEventListener('click', countryElement._clickHandler);
      }

      // Create new handlers
      const hoverHandler = () => {
        // Clear previous highlights first
        clearMapHighlights();

        // Highlight the corresponding card in the panel by matching country code
        const cards = panelContent.querySelectorAll('.country-card');

        cards.forEach(card => {
          const cardCode = card.dataset.countryCode;
          if (cardCode === countryCode) {
            // Highlight this card
            card.classList.add('highlighted');
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        });

        // Highlight on map too
        highlightCountryOnMap(countryCode);
      };

      const leaveHandler = () => {
        clearMapHighlights();
      };

      const clickHandler = (e) => {
        // Allow the default link behavior (navigate to news page)
        // This works because the SVG countries are already <a> tags
        // Just add a visual feedback before navigation
        countryElement.style.opacity = '0.6';
        setTimeout(() => {
          countryElement.style.opacity = '';
        }, 200);
      };

      // Store handlers for removal later
      countryElement._hoverHandler = hoverHandler;
      countryElement._leaveHandler = leaveHandler;
      countryElement._clickHandler = clickHandler;

      // Add listeners
      countryElement.addEventListener('mouseenter', hoverHandler);
      countryElement.addEventListener('mouseleave', leaveHandler);
      countryElement.addEventListener('click', clickHandler);
    });
  };

  // Cache for the world feed API response
  let worldFeedCache = null;

  /**
   * Fetch countries for a region from the API
   * Caches the feed response to avoid redundant fetches on auto-open
   */
  const fetchRegionCountries = async (regionName) => {
    try {
      const accordion = document.getElementById('worldFeedAccordion');
      if (!accordion) return [];

      const feedUrl = accordion.dataset.feedEndpoint;
      if (!feedUrl) return [];

      // Use cached feed data if available
      if (!worldFeedCache) {
        const response = await fetch(feedUrl, {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        if (!response.ok) return [];
        worldFeedCache = await response.json();
      }

      const regions = worldFeedCache.regions || {};
      const regionData = regions[regionName];
      return regionData?.countries || [];
    } catch (error) {
      console.error('Error fetching region countries:', error);
      return [];
    }
  };

  /**
   * Get display name from continent/region ID
   */
  const getDisplayName = (continentId) => {
    return continentId.split('-').map(word =>
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  /**
   * Handle continent click
   */
  const handleContinentClick = async (e) => {
    const continent = e.target.closest('.continent');
    if (!continent) return;

    const href = continent.getAttribute('href');
    if (!href || !href.startsWith('#')) return;

    const continentId = href.slice(1); // Remove '#'
    const regionName = CONTINENT_TO_REGION[continentId];

    if (!regionName) return;

    // Track current region
    currentRegionId = continentId;

    const displayName = getDisplayName(continentId);

    // Fetch countries first to get count (and cache them)
    const countries = await fetchRegionCountries(regionName);
    regionCountriesCache[continentId] = countries;

    // Open panel with country count
    openPanel(displayName, countries.length);

    // Render countries
    await renderCountries(countries, displayName);
  };

  /**
   * Auto-open panel when hovering a country on the map
   * Works when zoomed into a region but the panel is closed
   */
  const setupAutoOpenOnHover = () => {
    worldMap.addEventListener('mouseover', async (e) => {
      const countryEl = e.target.closest('.country');
      if (!countryEl) return;

      // Don't auto-open if panel is already active or already opening
      if (isAutoOpening) return;
      if (panel && panel.classList.contains('active')) return;

      // Check if the country belongs to a visible country-layer (zoomed in)
      const parentLayer = countryEl.closest('.country-layer');
      if (!parentLayer) return;
      if (parentLayer.style.visibility === 'hidden' || parentLayer.style.opacity === '0') return;

      const regionId = parentLayer.id; // e.g., 'south-america'
      const regionName = CONTINENT_TO_REGION[regionId];
      if (!regionName) return;

      isAutoOpening = true;
      currentRegionId = regionId;
      const displayName = getDisplayName(regionId);

      // Use cached countries if available, otherwise fetch
      let countries = regionCountriesCache[regionId];
      if (!countries) {
        countries = await fetchRegionCountries(regionName);
        regionCountriesCache[regionId] = countries;
      }

      // Open panel
      openPanel(displayName, countries.length);
      await renderCountries(countries, displayName);

      // After panel opens, highlight the hovered country
      const countryCode = (countryEl.getAttribute('data-country') || '').toUpperCase();
      if (countryCode) {
        highlightCountryOnMap(countryCode);
        if (panelContent) {
          panelContent.querySelectorAll('.country-card').forEach(card => {
            if (card.dataset.countryCode === countryCode) {
              card.classList.add('highlighted');
              card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          });
        }
      }

      isAutoOpening = false;
    });
  };

  /**
   * Preload world feed data so auto-open on hover is instant
   */
  const preloadWorldFeed = async () => {
    try {
      const accordion = document.getElementById('worldFeedAccordion');
      if (!accordion) return;

      const feedUrl = accordion.dataset.feedEndpoint;
      if (!feedUrl) return;

      const response = await fetch(feedUrl, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });

      if (response.ok) {
        worldFeedCache = await response.json();
      }
    } catch (error) {
      // Silently fail - data will be fetched on demand
    }
  };

  /**
   * Initialize
   */
  const init = () => {
    // Listen for clicks on continents
    worldMap.addEventListener('click', handleContinentClick);

    // Auto-open panel when hovering countries on the map
    setupAutoOpenOnHover();

    // Preload world feed data for instant hover response
    preloadWorldFeed();

    // Close panel when navigating back to world view
    worldMap.addEventListener('click', (e) => {
      if (e.target.closest('.home-btn')) {
        closePanel();
        currentRegionId = null;
      }
    });

    // Close panel when clicking the map back button
    const backBtn = document.getElementById('map-back-btn');
    if (backBtn) {
      backBtn.addEventListener('click', () => {
        closePanel();
        currentRegionId = null;
      });
    }

    // Close panel when clicking on empty SVG area (to go back to world view)
    worldMap.addEventListener('click', (e) => {
      // If we're in a zoomed region and click on empty space (not a country/continent)
      if (currentRegionId && !e.target.closest('.country') && !e.target.closest('.continent')) {
        closePanel();
        currentRegionId = null;
      }
    });

    // Close panel on browser back/forward navigation
    window.addEventListener('popstate', () => {
      const hash = window.location.hash.slice(1);
      if (!hash || hash === 'continents') {
        closePanel();
        currentRegionId = null;
      }
    });

    // Close panel on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && panel && panel.classList.contains('active')) {
        closePanel();
      }
    });
  };

  // Run when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
