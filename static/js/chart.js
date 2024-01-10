am5.ready(function() {

var root = am5.Root.new("chartdiv");


root.setThemes([
  am5themes_Animated.new(root)
]);


var chart = root.container.children.push(am5map.MapChart.new(root, {
  panX: "rotateX",
  panY: "rotateY",
  projection: am5map.geoOrthographic(),
  paddingBottom: 20,
  paddingTop: 20,
  paddingLeft: 20,
  paddingRight: 20
}));


var polygonSeries = chart.series.push(am5map.MapPolygonSeries.new(root, {
  geoJSON: am5geodata_worldLow 
}));

polygonSeries.mapPolygons.template.setAll({
  tooltipText: "{name}",
  toggleKey: "active",
  interactive: true
});

polygonSeries.mapPolygons.template.states.create("hover", {
  fill: root.interfaceColors.get("primaryButtonHover")
});

polygonSeries.mapPolygons.template.states.create("active", {
  fill: root.interfaceColors.get("primaryButtonHover")
});


var backgroundSeries = chart.series.push(am5map.MapPolygonSeries.new(root, {}));
backgroundSeries.mapPolygons.template.setAll({
  fill: root.interfaceColors.get("alternativeBackground"),
  fillOpacity: 0.1,
  strokeOpacity: 0
});
backgroundSeries.data.push({
  geometry: am5map.getGeoRectangle(90, 180, -90, -180)
});


var previousPolygon;

polygonSeries.mapPolygons.template.on("active", function(active, target) {
  if (previousPolygon && previousPolygon != target) {
    previousPolygon.set("active", false);
  }
  if (target.get("active")) {
    selectCountry(target.dataItem.get("id"));
  }
  previousPolygon = target;
});

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function selectCountry(id) {
  var dataItem = polygonSeries.getDataItemById(id);
  var target = dataItem.get("mapPolygon");
  if (target) {
    var centroid = target.geoCentroid();
    if (centroid) {
      chart.animate({ key: "rotationX", to: -centroid.longitude, duration: 1500, easing: am5.ease.inOut(am5.ease.cubic) });
      chart.animate({ key: "rotationY", to: -centroid.latitude, duration: 1500, easing: am5.ease.inOut(am5.ease.cubic) });

      var selectedCountry = dataItem.get("id");
      sleep(2000).then(() => { window.location.href = 'https://infomundi.net/news?country=' + encodeURIComponent(selectedCountry); });
    }
  }
}


chart.appear(1000, 100);

});