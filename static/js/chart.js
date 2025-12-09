am5.ready(function() {

  // 1) Create root element
  var root = am5.Root.new("chartdiv");

  // 2) Set themes
  root.setThemes([
    am5themes_Animated.new(root)
  ]);

  // 3) Create the map chart
  var chart = root.container.children.push(am5map.MapChart.new(root, {
    panX: "rotateX",
    projection: am5map.geoNaturalEarth1()
  }));

  // 4) Create polygon series for continents
  var continentSeries = chart.series.push(am5map.MapPolygonSeries.new(root, {
    geoJSON: am5geodata_continentsLow,
    exclude: ["antarctica"]
  }));

  continentSeries.mapPolygons.template.setAll({
    tooltipText: "{name}",
    interactive: true
  });

  continentSeries.mapPolygons.template.states.create("hover", {
    fill: root.interfaceColors.get("primaryButtonActive")
  });

  // Zoom into a continent on click
  continentSeries.mapPolygons.template.events.on("click", function(ev) {
    continentSeries.zoomToDataItem(ev.target.dataItem);
    continentSeries.hide();
    countrySeries.show();
    homeButton.show();
  });


  // 5) Create polygon series for countries (initially hidden)
  var countrySeries = chart.series.push(am5map.MapPolygonSeries.new(root, {
    geoJSON: am5geodata_worldLow,
    exclude: ["AQ"],      // Exclude Antarctica
    visible: false       // Start hidden
  }));

  countrySeries.mapPolygons.template.setAll({
    tooltipText: "{name}",
    interactive: true
  });

  countrySeries.mapPolygons.template.states.create("hover", {
    fill: root.interfaceColors.get("primaryButtonActive")
  });

  // HELPER: if you prefer a “Promise‐based” sleep
  function sleep(ms) {
    return new Promise(resolve => {
      setTimeout(resolve, ms);
    });
  }

  // 6) When a country is clicked, grab its ISO code (id) and redirect after 1.5 seconds
  countrySeries.mapPolygons.template.events.on("click", function(ev) {
    // ev.target.dataItem.get("id") is the ISO code (e.g., "US", "BR", etc.)
    var dataItem = ev.target.dataItem;
    var selectedCountry = dataItem.get("id");

    // Optional: you might want to hide the map or show a loading state here.
    // e.g. countrySeries.hide(); continentSeries.hide();

    // Wait 100ms, then redirect:
    sleep(10).then(function() {
      window.location.href = "/news?country=" + encodeURIComponent(selectedCountry);
    });
  });


  // 7) Add a “home” button to go back to the continents view
  var homeButton = chart.children.push(am5.Button.new(root, {
    paddingTop: 10,
    paddingBottom: 10,
    x: am5.percent(100),
    centerX: am5.percent(100),
    opacity: 0,
    interactiveChildren: false,
    icon: am5.Graphics.new(root, {
      svgPath: "M16,8 L14,8 L14,16 L10,16 L10,10 L6,10 L6,16 L2,16 L2,8 L0,8 L8,0 L16,8 Z M16,8",
      fill: am5.color(0xffffff)
    })
  }));

  homeButton.events.on("click", function() {
    chart.goHome();
    continentSeries.show();
    countrySeries.hide();
    homeButton.hide();
  });

}); // end am5.ready()
