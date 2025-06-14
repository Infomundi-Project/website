document.addEventListener("DOMContentLoaded", function() {
  // ── 1) STORIES LINE CHART ──
  const ctxLine = document.getElementById("storiesLineChart").getContext("2d");
  const storiesChart = new Chart(ctxLine, {
    type: 'line',
    data: {
      labels: [],            // ← filled from API
      datasets: [{
        label: 'Stories',
        data: [],            // ← filled from API
        fill: false,
        borderColor: 'rgba(75, 192, 192, 1)',
        tension: 0.1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: 'category',
          grid: { display: false }
        },
        y: {
          beginAtZero: true
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });

  // ── 2) TOP COUNTRIES BAR CHART ──
  const ctxPie = document
    .getElementById("countriesPieChart")
    .getContext("2d");

  const countriesPieChart = new Chart(ctxPie, {
    type: 'pie',   // ← change to 'polarArea' for a Polar Area chart
    data: {
      labels: [],     // ← will be filled from the API
      datasets: [{
        data: [],     // ← will be filled from the API
        backgroundColor: [
          'rgba(255, 99, 132, 0.6)',
          'rgba(54, 162, 235, 0.6)',
          'rgba(255, 206, 86, 0.6)',
          'rgba(75, 192, 192, 0.6)',
          'rgba(153, 102, 255, 0.6)'
        ],
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            padding: 16,
            boxWidth: 12
          }
        }
      }
    }
  });

  // ── 3) USER ENGAGEMENT DOUGHNUT ──
  const ctxDoughnut = document.getElementById("engagementDoughnut").getContext("2d");
  const engagementChart = new Chart(ctxDoughnut, {
    type: 'doughnut',
    data: {
      labels: ['Likes', 'Dislikes', 'Comments', 'Shares'],
      datasets: [{
        data: [],
        backgroundColor: [
          'rgba(75, 192, 192, 0.7)',
          'rgba(255, 99, 132, 0.7)',
          'rgba(255, 206, 86, 0.7)',
          'rgba(54, 162, 235, 0.7)'
        ],
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '60%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 12, padding: 16 }
        }
      }
    }
  });

  // ── 4) FETCH DASHBOARD DATA ──
  fetch("/api/home/dashboard")
    .then(res => {
      if (!res.ok) throw new Error("Failed to load dashboard data");
      return res.json();
    })
    .then(json => {
      // update line chart
      storiesChart.data.labels = json.days.map(d => {
        const dt = new Date(d);
        return dt.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
      });
      storiesChart.data.datasets[0].data = json.stories_last_7_days;
      storiesChart.update();

      // extract countries
      const labels = json.top_countries.map(c => c.country);
      const counts = json.top_countries.map(c => c.count);
      
      // update bar chart (top countries)
      countriesPieChart.data.labels = labels;
      countriesPieChart.data.datasets[0].data = counts;
      countriesPieChart.update();

      // update doughnut (engagement)
      const e = json.engagement;
      engagementChart.data.datasets[0].data = [e.likes, e.dislikes, e.comments, e.shares];
      engagementChart.update();
    })
    .catch(err => console.error("Could not load dashboard data:", err));

  // ── 5) TRENDING: GLOBE & TOP STORIES ──
  const topStoriesContainer = document.getElementById("topStoriesContainer");
  if (topStoriesContainer) {
    fetch("/api/home/trending")
      .then(res => res.ok ? res.json() : Promise.reject("Failed to fetch top stories"))
      .then(stories => {
        stories.forEach(story => {
          const {
            story_id, title, pub_date, image_url,
            publisher, views, likes, dislikes, num_comments, description=""
          } = story;

          // time-ago
          const then = new Date(pub_date), now = new Date();
          const diffHours = Math.floor((now - then) / 36e5);
          const diffDays  = Math.floor(diffHours / 24);
          const timeAgo   = diffHours < 24 ? `${diffHours}h ago` : `${diffDays}d ago`;

          // sanitize
          const desc = description
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

          // card wrapper
          const wrapper = document.createElement("div");
          wrapper.className = "flex-shrink-0";
          wrapper.style.width = "15rem";
          wrapper.innerHTML = `
            <div class="card h-100 shadow-sm position-relative mb-2" id="${story_id}">
              <a href="/comments?id=${story_id}">
                <img src="${image_url}"
                     class="card-img-top rounded-top"
                     alt="${title.replace(/"/g,"&quot;")}"
                     style="aspect-ratio:16/9; object-fit:cover;"
                     draggable="false">
              </a>
              <div class="position-absolute top-0 end-0 mt-2 me-2">
                <span data-bs-toggle="tooltip" data-bs-title="Source: ${publisher.name}">
                  ${publisher.favicon_url ? 
            `<img src="${publisher.favicon_url}" class="rounded" alt="${publisher.name} favicon image" width="30">` : 
            `<i class="fa-solid fa-tower-cell"></i>`
          }
                </span>
              </div>
              <div class="card-body">
                <h6 class="card-title fw-semibold line-clamp-2">${title}</h6>
                <p class="card-text text-muted small line-clamp-3">${desc}</p>
                <p class="card-text"><small class="text-secondary">${timeAgo}</small></p>
              </div>
            </div>`;
          topStoriesContainer.appendChild(wrapper);
        });

        // init tooltips
        Array.from(topStoriesContainer.querySelectorAll("[data-bs-toggle='tooltip']"))
             .forEach(el => new bootstrap.Tooltip(el));
      })
      .catch(err => console.error("Error loading top stories:", err));

    // ── drag to scroll ──
    let isDown = false, startX = 0, scrollStart = 0;
    topStoriesContainer.addEventListener("mousedown", e => {
      isDown = true;
      topStoriesContainer.classList.add("dragging");
      startX = e.pageX - topStoriesContainer.offsetLeft;
      scrollStart = topStoriesContainer.scrollLeft;
      e.preventDefault();
    });
    ['mouseleave','mouseup'].forEach(evt => {
      topStoriesContainer.addEventListener(evt, () => {
        isDown = false;
        topStoriesContainer.classList.remove("dragging");
      });
    });
    topStoriesContainer.addEventListener("mousemove", e => {
      if (!isDown) return;
      e.preventDefault();
      const x = e.pageX - topStoriesContainer.offsetLeft;
      topStoriesContainer.scrollLeft = scrollStart - (x - startX);
    });
    topStoriesContainer.addEventListener("dragstart", e => e.preventDefault());
  }
});