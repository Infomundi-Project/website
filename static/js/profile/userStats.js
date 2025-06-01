document.addEventListener("DOMContentLoaded", function() {
  const uid = profileUserId; // however you inject the user ID
  fetch(`/api/user/${uid}/stats/reading`, {
    credentials: "same-origin"
  })
  .then(res => res.json())
  .then(data => {
    renderCalendar(data.daily_counts);
    renderOverview(data); // your existing overview code
  })
  .catch(err => {
    console.error("Failed to load reading stats:", err);
  });

// =========================================
// 3.1) renderCalendar (using Bootstrap bg classes)
// =========================================
function renderCalendar(dailyCounts) {
  const calendarEl       = document.getElementById("calendar");
  const monthLabelsEl    = document.querySelector(".month-labels");

  // 1) Clear any old content
  calendarEl.innerHTML    = "";
  monthLabelsEl.innerHTML = "";

  // 2) Build a lookup { "YYYY-MM-DD": count }
  const dateMap = {};
  dailyCounts.forEach(obj => {
    dateMap[obj.date] = obj.count;
  });

  // 3) Compute “today” and “oneYearAgo”
  const utcToday       = new Date();
  const endOfDayToday  = new Date(utcToday);
  endOfDayToday.setHours(23, 59, 59, 999);

  const oneYearAgoUTC = new Date(dailyCounts[0].date + "T00:00:00Z");
  // … same as before …

  // 4) Find the Sunday on/before oneYearAgoUTC
  const dowOrig       = oneYearAgoUTC.getUTCDay();
  const startOfCalendar = new Date(oneYearAgoUTC);
  startOfCalendar.setUTCDate(startOfCalendar.getUTCDate() - dowOrig);

  // 5) Compute totalDays, totalWeeks
  const totalDays  = Math.ceil(
    (endOfDayToday.getTime() - startOfCalendar.getTime()) /
    (1000 * 60 * 60 * 24)
  ) + 1;
  const totalWeeks = Math.ceil(totalDays / 7);

  // 6) Set #calendar / .month-labels width
  const neededWidthPx = totalWeeks * 15;  // 12px + 3px gap = 15px
  calendarEl.style.minWidth    = `${neededWidthPx}px`;
  monthLabelsEl.style.minWidth = `${neededWidthPx}px`;

  // 7) Append each day “column-major” (Mon→Sun down each column)
  for (let weekIndex = 0; weekIndex < totalWeeks; weekIndex++) {
    for (let rowIndex = 0; rowIndex < 7; rowIndex++) {
      const actualDow = (rowIndex + 1) % 7; // 1=Mon … 6=Sat, 0=Sun
      const cellDate  = new Date(startOfCalendar);
      cellDate.setUTCDate(
        cellDate.getUTCDate() + (weekIndex * 7) + actualDow
      );
      const isoStr = cellDate.toISOString().slice(0, 10);

      const inRange = 
        cellDate.getTime() >= oneYearAgoUTC.getTime() &&
        cellDate.getTime() <= endOfDayToday.getTime();

      // Create the <div class="day">
      const dayEl = document.createElement("div");
      dayEl.classList.add("day");

      if (!inRange) {
        // OUTSIDE the 1-year window → just a placeholder
        // We’ll keep it as a dimmed square (opacity set in CSS)
        dayEl.classList.add("placeholder");
        // If you want a specific background-color for placeholders,
        // you could also add a Bootstrap class like “bg-dark bg-opacity-10”:
        // dayEl.classList.add("bg-dark", "bg-opacity-10");
        dayEl.setAttribute("data-count", 0);
        dayEl.setAttribute("data-date", "");
      } else {
        // INSIDE the 1-year window: figure out how many “reads” on this date
        const count = dateMap[isoStr] || 0;
        const lvl   = getLevel(count);

        // Depending on lvl (0…3), we map to Bootstrap utilities:
        //
        //   lvl = 0  →  no reads:     bg-secondary
        //   lvl = 1  →  1–10 reads:    bg-success bg-opacity-50
        //   lvl = 2  →  11–25 reads:    bg-success bg-opacity-75
        //   lvl = 3  →  25+ reads:    bg-success
        //
        switch (lvl) {
          case 0:
            dayEl.classList.add("bg-secondary");
            break;
          case 1:
            dayEl.classList.add("bg-success", "bg-opacity-50");
            break;
          case 2:
            dayEl.classList.add("bg-success", "bg-opacity-75");
            break;
          case 3:
            dayEl.classList.add("bg-success");
            break;
        }

        dayEl.setAttribute("data-count", count);
        dayEl.setAttribute("data-date", isoStr);

        const readWord = count === 1 ? "read" : "reads";
        dayEl.setAttribute("data-bs-toggle", "tooltip");
        dayEl.setAttribute(
          "data-bs-title",
          `${count} ${readWord} on ${isoStr}`
        );
      }

      // Because #calendar has “grid-auto-flow: column”,
      // appending here places <div> at row=(rowIndex+1), col=(weekIndex+1).
      calendarEl.appendChild(dayEl);
    }
  }

  // 8) Finally, render month labels
  renderMonthLabels(startOfCalendar, totalWeeks, oneYearAgoUTC, endOfDayToday);
  initializeTooltips();
}


  // ------------------------------------------
  // Helper: bucket a count into 0…4
  // ------------------------------------------
  function getLevel(count) {
    if (count === 0) return 0;
    if (count < 11) return 1;
    if (count < 25) return 2;
    return 3;
  }

  function renderMonthLabels(startSunday, totalWeeks, oneYearAgoUTC, endOfDayToday) {
    const monthLabelsEl = document.querySelector(".month-labels");
    monthLabelsEl.innerHTML = "";
    //monthLabelsEl.classList = "text-secondary";

    function shortMonthName(idx) {
      return ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][idx];
    }

    let lastMonthRendered = null;
    for (let weekIndex = 0; weekIndex < totalWeeks; weekIndex++) {
      // The “candidate” date for this column is the first in-range day
      // in that week (it may be Sunday or Monday, depending on oneYearAgo).
      const sundayOfThisWeek = new Date(startSunday);
      sundayOfThisWeek.setUTCDate(sundayOfThisWeek.getUTCDate() + weekIndex * 7 + 0); 
      // That’s the Sunday of weekIndex.

      // If that Sunday < oneYearAgoUTC, we move forward to exactly oneYearAgoUTC:
      const candidateDate = sundayOfThisWeek.getTime() < oneYearAgoUTC.getTime()
        ? new Date(oneYearAgoUTC)
        : sundayOfThisWeek;

      // If candidateDate > today, break out (no more months).
      if (candidateDate.getTime() > endOfDayToday.getTime()) {
        break;
      }

      const monthIdx = candidateDate.getUTCMonth();
      if (monthIdx !== lastMonthRendered) {
        lastMonthRendered = monthIdx;
        const span = document.createElement("span");
        span.textContent = shortMonthName(monthIdx);
        // Each column is 12px + 3px gap = 15px wide
        span.style.left = `${weekIndex * 15.5}px`;
        monthLabelsEl.appendChild(span);
      }
    }
  }

  function renderOverview(data) {
    const yearTotal = data.daily_counts.reduce((sum, obj) => sum + obj.count, 0);
    document.getElementById("yearTotalReads").textContent = yearTotal;

    const pubs = data.top_publishers.map(p => p.name);
    let pubString;
    if (pubs.length === 0) {
      pubString = "no publishers yet";
    } else if (pubs.length <= 2) {
      pubString = pubs.join(" and ");
    } else {
      const firstTwo = pubs.slice(0, 2).join(", ");
      pubString = `${firstTwo} and ${pubs.length - 2} others`;
    }
    document.getElementById("topPublishersList").textContent = pubString;

    const topTagsUl = document.getElementById("topTagsList");
    topTagsUl.innerHTML = "";
    data.top_tags.forEach(t => {
      const li = document.createElement("li");
      li.textContent = `${t.tag} (${t.count})`;
      li.classList = "text-secondary mb-1";
      topTagsUl.appendChild(li);
    });
    if (data.top_tags.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No tags yet";
      topTagsUl.appendChild(li);
    }

    const topCountriesUl = document.getElementById("topCountriesList");
    topCountriesUl.innerHTML = "";
    data.top_countries.forEach(c => {
      const li = document.createElement("li");
      li.textContent = `${c.country} (${c.count})`;
      li.classList = 'text-secondary mb-1';
      topCountriesUl.appendChild(li);
    });
    if (data.top_countries.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No locales yet";
      topCountriesUl.appendChild(li);
    }

    const ctx = document.getElementById("miniDistributionChart").getContext("2d");
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: ["Daily", "Weekly", "Monthly"],
        datasets: [{
          label: "Stories Read",
          data: [
            data.counts.daily || 0,
            data.counts.weekly || 0,
            data.counts.monthly || 0
          ],
          backgroundColor: ["#238636", "#238636", "#238636"],
          barThickness: 16,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          title: {
            display: true,
            text: "Reading Rhythm",
            font: { size: 12 }
          }
        },
        scales: {
          x: {
            ticks: { color: "#8b949e", font: { size: 11 } },
            grid: { display: false }
          },
          y: {
            beginAtZero: true,
            ticks: { color: "#8b949e", font: { size: 11 } },
            grid: { color: "#30363d" }
          }
        }
      }
    });
  }
});
