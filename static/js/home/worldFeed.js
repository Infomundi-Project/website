(() => {
  const root = document.getElementById('worldFeedAccordion');
  if (!root) return;

  const FEED_URL = root.dataset.feedEndpoint;
  const FLAG_BASE = '/static/img/flags/4x3/';

  const fmtDate = (iso) => {
    try {
      return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  const flagUrl = (country) => {
    const code = (country.code || country.cca2 || country.alpha2 || '').toLowerCase();
    return code ? `${FLAG_BASE}${code}.svg` : '';
  };

  const chip = (c) => {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = 'country-chip btn btn-sm btn-ghost text-start';
    el.dataset.country = c.code || c.cca2 || '';
    const url = flagUrl(c);
    el.innerHTML = `
      ${url ? `<img class="flag" src="${url}" alt="${c.name} flag">` : '🏳️'}
      <span>${c.name}</span>
    `;
    el.addEventListener('click', () => {
      const code = (c.code || c.cca2 || '').toUpperCase();
      const first = root.querySelector(`.news-card[data-country="${code}"]`);
      if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    return el;
  };

  const card = (c, s) => {
    const a = document.createElement('a');
    a.href = s.url;
    a.target = '_blank';
    a.rel = 'noopener';
    a.className = 'card news-card text-decoration-none';
    a.dataset.country = (c.code || c.cca2 || '').toUpperCase();
    const url = flagUrl(c);
    a.innerHTML = `
      <div class="card-body">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <span class="news-country-pill">
            ${url ? `<img class="flag" src="${url}" alt="${c.name} flag">` : '🏳️'}
            <span class="fw-semibold">${c.name}</span>
          </span>
          <span class="news-meta">${fmtDate(s.published_at)}</span>
        </div>
        ${s.source ? `<div class="small text-body-secondary mb-1">${s.source}</div>` : ``}
        <h6 class="card-title mb-2">${s.title}</h6>
        ${s.summary ? `<p class="card-text text-body-secondary">${s.summary}</p>` : ``}
      </div>
    `;
    return a;
  };

  const renderRegion = (regionName, regionData) => {
    const chipsWrap = root.querySelector(`[data-role="countries"][data-region="${regionName}"]`);
    const grid = root.querySelector(`[data-role="grid"][data-region="${regionName}"]`);
    const skeleton = root.querySelector(`[data-role="skeleton"][data-region="${regionName}"]`);
    skeleton?.remove();

    const countries = regionData?.countries || [];
    countries.forEach((c) => chipsWrap?.appendChild(chip(c)));
    countries.forEach((c) => (c.topStories || []).forEach((s) => grid?.appendChild(card(c, s))));
  };

  // Open ALL accordions by default and allow multiple open at once
  const openAllAccordions = () => {
    // Remove data-bs-parent so Bootstrap doesn't auto-close siblings
    root.querySelectorAll('.accordion-collapse').forEach((el) => {
      el.removeAttribute('data-bs-parent');
      const inst = bootstrap.Collapse.getOrCreateInstance(el, { toggle: false });
      inst.show();
    });
    // Update buttons' state (visual "expanded")
    root.querySelectorAll('.accordion-button').forEach((btn) => {
      btn.classList.remove('collapsed');
      btn.setAttribute('aria-expanded', 'true');
    });
  };

  // --- Fallback demo data (now for every region) ---
  const fallback = {
    regions: {
      'Europe': {
        countries: [
          {
            code: 'FR',
            name: 'France',
            topStories: [
              {
                title: 'France invests in high-speed rail expansion',
                source: 'AFP',
                summary: 'New TGV routes will connect major cities with reduced travel times.',
                url: '#',
                published_at: '2025-08-08T10:00:00Z'
              },
              {
                title: 'Paris launches urban cooling program',
                source: 'Le Monde',
                summary: 'Shaded corridors and misting stations to mitigate heatwaves.',
                url: '#',
                published_at: '2025-08-05T08:30:00Z'
              }
            ]
          },
          {
            code: 'DE',
            name: 'Germany',
            topStories: [
              {
                title: 'Germany leads EU renewable energy goals',
                source: 'DW',
                summary: 'Electricity generation crosses a new renewable benchmark.',
                url: '#',
                published_at: '2025-08-07T09:00:00Z'
              }
            ]
          },
          {
            code: 'IT',
            name: 'Italy',
            topStories: [
              {
                title: 'Italy unveils green tourism plan',
                source: 'ANSA',
                summary: 'Incentives to preserve coastal parks and villages.',
                url: '#',
                published_at: '2025-08-06T08:00:00Z'
              }
            ]
          }
        ]
      },
      'North America': {
        countries: [
          {
            code: 'US',
            name: 'United States',
            topStories: [
              {
                title: 'US tech stocks rally after earnings',
                source: 'Bloomberg',
                summary: 'Major indexes close higher on strong guidance.',
                url: '#',
                published_at: '2025-08-08T21:00:00Z'
              },
              {
                title: 'Federal infrastructure grants announced',
                source: 'Reuters',
                summary: 'Funding targets bridges and broadband in rural areas.',
                url: '#',
                published_at: '2025-08-06T15:15:00Z'
              }
            ]
          },
          {
            code: 'CA',
            name: 'Canada',
            topStories: [
              {
                title: 'Canada expands EV charging network',
                source: 'CBC',
                summary: 'New coast-to-coast fast chargers planned along Trans-Canada.',
                url: '#',
                published_at: '2025-08-07T17:45:00Z'
              }
            ]
          },
          {
            code: 'MX',
            name: 'Mexico',
            topStories: [
              {
                title: 'Mexico City launches air quality initiative',
                source: 'El Universal',
                summary: 'Low-emission zones to phase in over the next year.',
                url: '#',
                published_at: '2025-08-05T12:10:00Z'
              }
            ]
          }
        ]
      },
      'Latin America': {
        countries: [
          {
            code: 'BR',
            name: 'Brazil',
            topStories: [
              {
                title: 'Brazil accelerates Amazon reforestation',
                source: 'Folha',
                summary: 'Public-private partnerships aim to restore key corridors.',
                url: '#',
                published_at: '2025-08-08T13:00:00Z'
              }
            ]
          },
          {
            code: 'AR',
            name: 'Argentina',
            topStories: [
              {
                title: 'Argentina announces export incentives',
                source: 'La Nación',
                summary: 'New measures target agribusiness and lithium.',
                url: '#',
                published_at: '2025-08-06T11:20:00Z'
              }
            ]
          },
          {
            code: 'CL',
            name: 'Chile',
            topStories: [
              {
                title: 'Chile expands national park system',
                source: 'BioBio',
                summary: 'New protected areas designated in Patagonia.',
                url: '#',
                published_at: '2025-08-04T09:10:00Z'
              }
            ]
          }
        ]
      },
      'Africa': {
        countries: [
          {
            code: 'NG',
            name: 'Nigeria',
            topStories: [
              {
                title: 'Nigeria launches fintech regulatory sandbox',
                source: 'Punch',
                summary: 'Startups to test products with consumer safeguards.',
                url: '#',
                published_at: '2025-08-08T08:05:00Z'
              }
            ]
          },
          {
            code: 'ZA',
            name: 'South Africa',
            topStories: [
              {
                title: 'Cape Town water resilience plan updated',
                source: 'News24',
                summary: 'Desalination and reuse projects move forward.',
                url: '#',
                published_at: '2025-08-07T07:30:00Z'
              }
            ]
          },
          {
            code: 'KE',
            name: 'Kenya',
            topStories: [
              {
                title: 'Kenya expands mobile money interoperability',
                source: 'Nation',
                summary: 'Transfers between networks become seamless.',
                url: '#',
                published_at: '2025-08-05T10:00:00Z'
              }
            ]
          }
        ]
      },
      'Asia': {
        countries: [
          {
            code: 'IN',
            name: 'India',
            topStories: [
              {
                title: 'India unveils semiconductor cluster incentives',
                source: 'The Hindu',
                summary: 'States compete to host fab projects.',
                url: '#',
                published_at: '2025-08-08T06:30:00Z'
              }
            ]
          },
          {
            code: 'JP',
            name: 'Japan',
            topStories: [
              {
                title: 'Japan tests next-gen wind turbines',
                source: 'NHK',
                summary: 'Floating platforms deployed off Hokkaido.',
                url: '#',
                published_at: '2025-08-07T03:45:00Z'
              }
            ]
          },
          {
            code: 'CN',
            name: 'China',
            topStories: [
              {
                title: 'China announces new high-speed rail link',
                source: 'Xinhua',
                summary: 'Route will reduce travel time by 40%.',
                url: '#',
                published_at: '2025-08-06T02:10:00Z'
              }
            ]
          }
        ]
      },
      'Oceania': {
        countries: [
          {
            code: 'AU',
            name: 'Australia',
            topStories: [
              {
                title: 'Australia expands solar storage rebates',
                source: 'ABC',
                summary: 'Households to get additional support for batteries.',
                url: '#',
                published_at: '2025-08-08T04:00:00Z'
              }
            ]
          },
          {
            code: 'NZ',
            name: 'New Zealand',
            topStories: [
              {
                title: 'New Zealand launches green hydrogen pilot',
                source: 'RNZ',
                summary: 'Port operations to trial zero-emission equipment.',
                url: '#',
                published_at: '2025-08-05T01:25:00Z'
              }
            ]
          }
        ]
      }
    }
  };

  (async () => {
    try {
      const res = FEED_URL
        ? await fetch(FEED_URL, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        : null;
      const data = res && res.ok ? await res.json() : fallback;
      const regions = data.regions || {};
      Object.keys(regions).forEach((name) => renderRegion(name, regions[name]));
    } catch (e) {
      console.error('WorldFeed error', e);
      Object.keys(fallback.regions).forEach((name) => renderRegion(name, fallback.regions[name]));
    } finally {
      openAllAccordions();
    }
  })();
})();
