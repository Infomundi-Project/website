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
  // 3.1) renderCalendar (Mon→Sun rows, responsive)
  // =========================================
  function renderCalendar(dailyCounts) {
    const calendarEl = document.getElementById("calendar");
    const monthLabelsEl = document.querySelector(".month-labels");

    // 1) Clear any old content
    calendarEl.innerHTML = "";
    monthLabelsEl.innerHTML = "";

    // 2) Build a lookup { "YYYY-MM-DD": count }
    const dateMap = {};
    dailyCounts.forEach(obj => {
      dateMap[obj.date] = obj.count;
    });

    // 3) Compute “today” (end of day) and “oneYearAgo” as UTC midnight
    const utcToday = new Date();
    const endOfDayToday = new Date(utcToday);
    endOfDayToday.setHours(23, 59, 59, 999);

    const oneYearAgoUTC = new Date(dailyCounts[0].date + "T00:00:00Z");
    // Example: if dailyCounts[0].date is "2024-05-31", that is exactly 365 days before today.

    // 4) Find the Sunday on or before oneYearAgoUTC
    const dowOrig = oneYearAgoUTC.getUTCDay(); // 0 = Sunday, 1 = Monday, …, 6 = Saturday
    const startOfCalendar = new Date(oneYearAgoUTC);
    startOfCalendar.setUTCDate(startOfCalendar.getUTCDate() - dowOrig);
    // Now startOfCalendar is that Sunday at 00:00 UTC.

    // 5) How many days from startOfCalendar → today (inclusive)?
    const totalDays = Math.ceil(
      (endOfDayToday.getTime() - startOfCalendar.getTime()) / (1000 * 60 * 60 * 24)
    ) + 1;

    // 6) How many full weeks do we need? (each week = 7 days)
    const totalWeeks = Math.ceil(totalDays / 7);

    // 7) Dynamically set the min-width of #calendar and .month-labels
    //    Each “column” is 12px wide + 3px gap = 15px total.
    const neededWidthPx = totalWeeks * 15; 
    calendarEl.style.minWidth = `${neededWidthPx}px`;
    monthLabelsEl.style.minWidth = `${neededWidthPx}px`;

    // 8) Now append each day in “column-major” order, but with rows = Mon→Sun
    for (let weekIndex = 0; weekIndex < totalWeeks; weekIndex++) {
      for (let rowIndex = 0; rowIndex < 7; rowIndex++) {
        // rowIndex=0 → Monday, ..., rowIndex=5 → Saturday, rowIndex=6 → Sunday
        // actualDow: 1=Mon,2=Tue,...6=Sat,0=Sun
        const actualDow = (rowIndex + 1) % 7;

        // Compute this cell’s date by offsetting from startOfCalendar
        const cellDate = new Date(startOfCalendar);
        cellDate.setUTCDate(cellDate.getUTCDate() + weekIndex * 7 + actualDow);

        // Format as "YYYY-MM-DD"
        const isoStr = cellDate.toISOString().slice(0, 10);

        // Check if this date is within the one-year-ago … today range:
        const inRange =
          cellDate.getTime() >= oneYearAgoUTC.getTime() &&
          cellDate.getTime() <= endOfDayToday.getTime();

        // Create the <div class="day">
        const dayEl = document.createElement("div");
        if (!inRange) {
          // Placeholder—outside of the one-year window
          dayEl.className = "day lvl-0 placeholder";
          dayEl.setAttribute("data-count", 0);
          dayEl.setAttribute("data-date", "");
        } else {
          // Look up how many “reads” on that date
          const count = dateMap[isoStr] || 0;
          const lvl = getLevel(count);
          dayEl.className = `day lvl-${lvl}`;
          dayEl.setAttribute("data-count", count);
          dayEl.setAttribute("data-date", isoStr);
          const readWord = count === 1 ? "read" : "reads";
          dayEl.setAttribute("data-bs-toggle", "tooltip");
          dayEl.setAttribute("data-bs-title", `${count} ${readWord} on ${isoStr}`);
        }

        // Because #calendar has "grid-auto-flow: column",
        // appending here places it at row=(rowIndex+1), col=(weekIndex+1).
        calendarEl.appendChild(dayEl);
      }
    }

    // 9) Finally, render month labels above their correct columns:
    renderMonthLabels(startOfCalendar, totalWeeks, oneYearAgoUTC, endOfDayToday);
  }

  // ------------------------------------------
  // Helper: bucket a count into 0…4
  // ------------------------------------------
  function getLevel(count) {
    if (count === 0) return 0;
    if (count < 3) return 1;
    if (count < 6) return 2;
    if (count < 10) return 3;
    return 4;
  }

  // =========================================
  // 3.2) renderMonthLabels
  // =========================================
  // Places a <span> with "Jan","Feb", etc. above the first column in which that month appears.
  function renderMonthLabels(startSunday, totalWeeks, oneYearAgoUTC, endOfDayToday) {
    const monthLabelsEl = document.querySelector(".month-labels");
    monthLabelsEl.innerHTML = "";

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
        span.style.left = `${weekIndex * 15}px`;
        monthLabelsEl.appendChild(span);
      }
    }
  }

  // =========================================
  // 3.3) renderOverview (unchanged from before)
  // =========================================
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
      pubString = `${firstTwo} and ${pubs.length - 2} other†s`;
    }
    document.getElementById("topPublishersList").textContent = pubString;

    const topTagsUl = document.getElementById("topTagsList");
    topTagsUl.innerHTML = "";
    data.top_tags.forEach(t => {
      const li = document.createElement("li");
      li.textContent = `${t.tag} (${t.count})`;
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
            color: "#8b949e",
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
