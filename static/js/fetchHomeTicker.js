document.addEventListener('DOMContentLoaded', () => {
  fetchDataAndRenderTicker('/api/currencies', 'currencies-ticker',
    'Currencies', 'fa-money-bill-trend-up');
  fetchDataAndRenderTicker('/api/stocks', 'stocks-ticker',
    'Country Indexes', 'fa-arrow-trend-up');
  fetchDataAndRenderTicker('/api/crypto', 'crypto-ticker',
    'Cryptocurrencies', 'fa-coins');

  function fetchDataAndRenderTicker(apiEndpoint, containerId, title,
    iconClass) {
    fetch(apiEndpoint)
      .then(response => response.json())
      .then(data => {
        renderTicker(data, containerId, title, iconClass);
      })
      .catch(error => {
        console.error('Error fetching data:', error);
      });
  }

  function renderTicker(data, containerId, title, iconClass) {
    const container = document.getElementById(containerId);
    const marketDate = document.getElementById('marketDate');
    marketDate.innerHTML = data[0]?.date;
    let html = `
          <div class="hwrap-home">
              <div class="hmove-home" style="color: white">
      `;

    data.forEach(entry => {
      // If the container is stocks-ticker, add the country flag image
      let itemHtml = `<div class="hitem" style="color: white">`;

      if ((containerId === 'stocks-ticker' || containerId ===
          'currencies-ticker') && entry.country && entry.country.code) {
        itemHtml += `
                  <img alt="${entry.country.code} flag"
                       data-src="https://infomundi.net/static/img/flags/4x3/${entry.country.code}.svg"
                       class="lazyload flag">
              `;
      }

      if (containerId === 'stocks-ticker' && entry.country.name) {
        itemHtml +=
          `<span style="color: white;">${entry.country.name}</span>`;
      } else if (containerId === 'currencies-ticker') {
        itemHtml +=
          `<span style="color: white;">${entry.name_plural} (${entry.symbol})</span>`;
      } else {
        itemHtml += `<span style="color: white;">${entry.name}</span>`;
      }

      if (containerId === 'crypto-ticker' || containerId ===
        'currencies-ticker') {
        itemHtml += `
              <span style="color: ${entry.color};">
                  ${entry.changes.percent}
              </span>
              ${entry.color === '#FF6666' ? 
                  '<span style="color: #FF6666">&#8659;</span>' : 
                  '<span style="color: #00FF00">&#8657;</span>'
              }`;
      } else {
        itemHtml += `
              <span style="color: ${entry.color};">
                  ${entry.name} ${entry.changes.percent}
              </span>
              ${entry.color === '#FF6666' ? 
                  '<span style="color: #FF6666">&#8659;</span>' : 
                  '<span style="color: #00FF00">&#8657;</span>'
              }`;
      }

      if (containerId === 'currencies-ticker') {
        if (entry.name.slice(0, 3) === 'USD') {
          itemHtml +=
            `<span style="color: white;"> | 1 USD = ${entry.price} ${entry.symbol}</span>`;
        } else {
          itemHtml +=
            `<span style="color: white;"> | 1 ${entry.symbol} = ${entry.price} USD</span>`;
        }
      }

      itemHtml += '</div>'

      html += itemHtml;
    });

    html += `
              </div>
          </div>
      `;

    container.innerHTML = html;
  }
});