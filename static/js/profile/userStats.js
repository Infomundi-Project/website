async function loadReadingStats() {
  const res = await fetch(`/api/user/${profileUserId}/stats/reading`, {
    credentials: "same-origin"
  });
  const data = await res.json();

  // 1. Reads over time (bar chart)
  new Chart(
    document.getElementById("readsChart").getContext("2d"), {
      type: "bar",
      data: {
        labels: ["Daily", "Weekly", "Monthly"],
        datasets: [{
          label: "Stories Read",
          data: [
            data.counts.daily,
            data.counts.weekly,
            data.counts.monthly
          ]
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            display: false
          },
          title: {
            display: true,
            text: "Reading Rhythm"
          }
        },
        scales: {
          y: {
            beginAtZero: true
          }
        }
      }
    }
  );

  // 2. Top publishers (horizontal bar)
  new Chart(
    document.getElementById("publishersChart").getContext("2d"), {
      type: "bar",
      data: {
        labels: data.top_publishers.map(p => p.name),
        datasets: [{
          label: "Reads",
          data: data.top_publishers.map(p => p.count)
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: "Go-To Sources"
          },
          legend: {
            display: false
          }
        },
        scales: {
          x: {
            beginAtZero: true
          }
        }
      }
    }
  );

  // 3. Favorite tags (bar chart)
  new Chart(
    document.getElementById("tagsChart").getContext("2d"), {
      type: "bar",
      data: {
        labels: data.top_tags.map(t => t.tag),
        datasets: [{
          label: "Mentions",
          data: data.top_tags.map(t => t.count)
        }]
      },
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: "Favorite Topics"
          },
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true
          }
        }
      }
    }
  );

  // 4. Countries you explore (pie chart)
  new Chart(
    document.getElementById("countriesChart").getContext("2d"), {
      type: "pie",
      data: {
        labels: data.top_countries.map(c => c.country),
        datasets: [{
          label: "Reads by Country",
          data: data.top_countries.map(c => c.count)
        }]
      },
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: "Favorite Locales"
          }
        }
      }
    }
  );
}

document.addEventListener("DOMContentLoaded", loadReadingStats);