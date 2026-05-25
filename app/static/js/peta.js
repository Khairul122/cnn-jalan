// Pusat peta: Kota Lhokseumawe
var map = L.map('map').setView([5.1801, 97.1499], 13);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '© OpenStreetMap contributors'
}).addTo(map);

var markersLayer = L.layerGroup().addTo(map);

function showMapReady() {
  var skeleton = document.getElementById('map-skeleton');
  var mapEl    = document.getElementById('map');
  if (skeleton) { skeleton.style.display = 'none'; skeleton.removeAttribute('aria-busy'); }
  if (mapEl)    { mapEl.style.display = 'block'; }
  map.invalidateSize();
}

function showMapError(message) {
  var errorEl = document.getElementById('map-error');
  var msgEl   = document.getElementById('map-error-msg');
  if (errorEl) errorEl.style.display = 'block';
  if (msgEl && message) msgEl.textContent = message;
}

function hideMapError() {
  var errorEl = document.getElementById('map-error');
  if (errorEl) errorEl.style.display = 'none';
}

function loadMarkers() {
  hideMapError();
  var status = document.getElementById('filterStatus').value;

  var url = '/peta/geojson';
  var params = [];
  if (status) params.push('status=' + status);
  if (params.length) url += '?' + params.join('&');

  fetch(url)
    .then(function(r) {
      if (!r.ok) throw new Error('Server error: ' + r.status);
      return r.json();
    })
    .then(function(data) {
      showMapReady();
      markersLayer.clearLayers();
      data.features.forEach(function(f) {
        var p      = f.properties;
        var latlng = L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]);

        var marker = L.circleMarker(latlng, {
          radius      : 9,
          fillColor   : p.warna,
          color       : '#fff',
          weight      : 2,
          opacity     : 1,
          fillOpacity : 0.85
        });

        marker.bindPopup(
          '<strong>' + p.nama_citra + '</strong><br>' +
          'Jenis: ' + p.jenis + '<br>' +
          'Tingkat: <span style="color:' + p.warna + ';font-weight:bold">' + p.tingkat + '</span><br>' +
          'Status: ' + p.status + '<br>' +
          'Prioritas: ' + p.prioritas
        );

        markersLayer.addLayer(marker);
      });
    })
    .catch(function(err) {
      showMapReady();
      showMapError('Gagal memuat data peta. Periksa koneksi dan coba lagi.');
      console.error('Gagal memuat GeoJSON:', err);
    });
}

document.getElementById('btnFilter').addEventListener('click', loadMarkers);
loadMarkers();
