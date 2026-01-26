/**
 * Region Market Tickers
 * Renders market indices and currency tickers for each region/continent
 * Groups stock index + currency data by country
 */
document.addEventListener('DOMContentLoaded', () => {
  // Region to country codes mapping (matches backend WORLD_FEED_REGION_MAP)
  const REGION_COUNTRIES = {
    "North America": ["us", "ca", "mx"],
    "Latin America": ["br", "ar", "cl", "co", "pe", "ve", "ec", "uy", "py", "bo",
                      "cr", "pa", "cu", "do", "gt", "hn", "ni", "sv"],
    "Europe": ["gb", "de", "fr", "it", "es", "pt", "nl", "be", "se", "no", "pl",
               "at", "ch", "ie", "gr", "fi", "dk", "cz", "ro", "hu", "ua", "ru", "eu"],
    "Asia": ["cn", "jp", "in", "kr", "id", "th", "vn", "ph", "my", "sg", "pk",
             "bd", "il", "sa", "ae", "tr", "ir", "tw", "hk"],
    "Africa": ["za", "ng", "ke", "eg", "et", "gh", "tz", "ug", "dz", "ma", "tn", "sn", "ci"],
    "Oceania": ["au", "nz", "fj", "pg"]
  };

  let stocksData = [];
  let currenciesData = [];

  // Fetch both stocks and currencies data
  Promise.all([
    fetch('/api/stocks').then(r => r.json()).catch(() => []),
    fetch('/api/currencies').then(r => r.json()).catch(() => [])
  ]).then(([stocks, currencies]) => {
    stocksData = stocks || [];
    currenciesData = currencies || [];
    renderAllRegionTickers();
  }).catch(error => {
    console.error('Error fetching market data:', error);
    showErrorInAllRegions();
  });

  function renderAllRegionTickers() {
    Object.keys(REGION_COUNTRIES).forEach(region => {
      renderRegionTicker(region);
    });
  }

  function showErrorInAllRegions() {
    document.querySelectorAll('[data-role="ticker-content"]').forEach(container => {
      container.innerHTML = '<div class="ticker-empty">Unable to load market data</div>';
    });
  }

  function renderRegionTicker(region) {
    const container = document.querySelector(`[data-role="ticker-content"][data-region="${region}"]`);
    if (!container) return;

    const countryCodes = REGION_COUNTRIES[region] || [];

    // Group data by country code
    const countryDataMap = {};

    // Add stocks to country map
    stocksData.forEach(item => {
      if (item.country && countryCodes.includes(item.country.code.toLowerCase())) {
        const code = item.country.code.toLowerCase();
        if (!countryDataMap[code]) {
          countryDataMap[code] = { country: item.country, stocks: [], currency: null };
        }
        countryDataMap[code].stocks.push(item);
      }
    });

    // Add currencies to country map
    currenciesData.forEach(item => {
      if (item.country && countryCodes.includes(item.country.code.toLowerCase())) {
        const code = item.country.code.toLowerCase();
        if (!countryDataMap[code]) {
          countryDataMap[code] = { country: item.country, stocks: [], currency: null };
        }
        countryDataMap[code].currency = item;
      }
    });

    // If no data for this region, show empty message
    if (Object.keys(countryDataMap).length === 0) {
      container.innerHTML = '<div class="ticker-empty"><i class="fa-solid fa-chart-line me-2"></i>No market data available for this region</div>';
      return;
    }

    // Build ticker HTML - grouped by country
    let tickerItems = '';

    Object.values(countryDataMap).forEach(data => {
      tickerItems += buildCountryTickerItem(data);
    });

    // Duplicate items for seamless loop animation
    // The content is doubled so when animation reaches -50%, it looks identical to 0%
    const html = `
      <div class="hwrap-region">
        <div class="hmove-region">
          <div class="ticker-set">${tickerItems}</div>
          <div class="ticker-set">${tickerItems}</div>
        </div>
      </div>
    `;

    container.innerHTML = html;

    // Apply current speed to newly rendered ticker
    if (regionSpeeds[region]) {
      updateTickerSpeed(region);
    }
  }

  function buildCountryTickerItem(data) {
    const { country, stocks, currency } = data;

    // Get unique stocks only
    const uniqueStocks = stocks.filter((stock, index, self) =>
      index === self.findIndex(s => s.name === stock.name)
    );

    // Build stock badges HTML
    let stocksHtml = '';
    uniqueStocks.forEach((stock, i) => {
      const isNeg = stock.color === '#FF6666';
      const arrow = isNeg ? '↓' : '↑';
      const cls = isNeg ? 'text-danger' : 'text-success';
      const percent = stock.changes?.percent || '';
      stocksHtml += `<span class="data-badge ${cls}">${stock.name} ${percent} ${arrow}</span>`;
    });

    // Build currency HTML
    let currencyHtml = '';
    if (currency) {
      const isNeg = currency.color === '#FF6666';
      const arrow = isNeg ? '↓' : '↑';
      const cls = isNeg ? 'text-danger' : 'text-success';
      const percent = currency.changes?.percent || '';

      let rate;
      if (currency.name && currency.name.startsWith('USD')) {
        rate = `1 USD = ${currency.price} ${currency.symbol}`;
      } else {
        rate = `1 ${currency.symbol} = ${currency.price} USD`;
      }

      currencyHtml = `
        <div class="hitem-row">
          <i class="fa-solid fa-coins data-icon"></i>
          <span class="data-badge ${cls}">${currency.symbol} ${percent} ${arrow}</span>
          <span class="rate-text">${rate}</span>
        </div>`;
    }

    // Build stocks row HTML
    let stocksRowHtml = '';
    if (stocksHtml) {
      stocksRowHtml = `
        <div class="hitem-row">
          <i class="fa-solid fa-chart-line data-icon"></i>
          <div class="data-values">${stocksHtml}</div>
        </div>`;
    }

    const flagSrc = country?.code ? `/static/img/flags/4x3/${country.code}.svg` : '';
    const countryName = country?.name || 'Unknown';

    return `
      <div class="hitem-card">
        <div class="hitem-header">
          ${flagSrc ? `<img alt="${country.code}" data-src="${flagSrc}" class="lazyload flag">` : ''}
          <span class="country-name">${countryName}</span>
        </div>
        <div class="hitem-data">
          ${stocksRowHtml}
          ${currencyHtml}
        </div>
      </div>`;
  }

  // Speed control state per region
  const regionSpeeds = {};
  const BASE_DURATION = 40; // Base animation duration in seconds
  const SPEED_STEPS = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4];
  const DEFAULT_SPEED_INDEX = 3; // 1x

  function getSpeedMultiplier(region) {
    if (!regionSpeeds[region]) {
      regionSpeeds[region] = { index: DEFAULT_SPEED_INDEX, paused: false };
    }
    return SPEED_STEPS[regionSpeeds[region].index];
  }

  function updateTickerSpeed(region) {
    const state = regionSpeeds[region];
    const multiplier = SPEED_STEPS[state.index];
    const duration = BASE_DURATION / multiplier;

    const tickerContent = document.querySelector(`[data-role="ticker-content"][data-region="${region}"]`);
    const display = document.querySelector(`.ticker-speed-display[data-region="${region}"]`);

    if (tickerContent) {
      const moveElement = tickerContent.querySelector('.hmove-region');
      if (moveElement) {
        moveElement.style.animationDuration = `${duration}s`;
        if (state.paused) {
          moveElement.classList.add('paused');
        } else {
          moveElement.classList.remove('paused');
        }
      }
    }

    if (display) {
      display.textContent = `${multiplier}x`;
    }

    // Update pause button state
    const pauseBtn = document.querySelector(`.ticker-pause-btn[data-region="${region}"]`);
    if (pauseBtn) {
      if (state.paused) {
        pauseBtn.classList.add('active');
        pauseBtn.dataset.label = 'Play';
      } else {
        pauseBtn.classList.remove('active');
        pauseBtn.dataset.label = 'Pause';
      }
    }
  }

  function initSpeedControls() {
    document.querySelectorAll('.ticker-speed-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.action;
        const region = btn.dataset.region;

        if (!regionSpeeds[region]) {
          regionSpeeds[region] = { index: DEFAULT_SPEED_INDEX, paused: false };
        }

        const state = regionSpeeds[region];

        switch (action) {
          case 'faster':
            if (state.index < SPEED_STEPS.length - 1) {
              state.index++;
              // Visual feedback
              btn.style.transform = 'scale(1.3)';
              setTimeout(() => btn.style.transform = '', 150);
            }
            break;

          case 'slower':
            if (state.index > 0) {
              state.index--;
              // Visual feedback
              btn.style.transform = 'scale(1.3)';
              setTimeout(() => btn.style.transform = '', 150);
            }
            break;

          case 'pause':
            state.paused = !state.paused;
            break;

          case 'reset':
            state.index = DEFAULT_SPEED_INDEX;
            state.paused = false;
            // Visual feedback - spin the icon
            const icon = btn.querySelector('i');
            if (icon) {
              icon.style.transition = 'transform 0.3s ease';
              icon.style.transform = 'rotate(-360deg)';
              setTimeout(() => {
                icon.style.transition = '';
                icon.style.transform = '';
              }, 300);
            }
            break;
        }

        updateTickerSpeed(region);
      });
    });
  }

  // Initialize speed controls after DOM is ready
  initSpeedControls();
});
