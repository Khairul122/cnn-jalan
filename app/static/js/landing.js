(function () {
  'use strict';

  var D = JSON.parse(document.getElementById('landing-data').textContent);
  var KELAS = D.kelas;
  var BY_KEY = {};
  var BY_NAMA = {};
  KELAS.forEach(function (k) { BY_KEY[k.key] = k; BY_NAMA[k.nama] = k; });
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var fmt = function (n, d) { return Number(n).toFixed(d == null ? 1 : d).replace('.', ','); };

  // ── Header: tautan aktif menurut bagian yang sedang terlihat ─────────
  var navLinks = $$('.lp-nav a.nav-link');
  var seen = {};
  var spy = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { seen[e.target.id] = e.isIntersecting; });
    var current = ['peta', 'sebaran', 'metode', 'batasan'].filter(function (id) { return seen[id]; }).pop();
    navLinks.forEach(function (a) {
      var on = a.getAttribute('href') === '#' + current;
      a.classList.toggle('is-active', on);
      if (on) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
    });
  }, { rootMargin: '-72px 0px -55% 0px' });
  ['peta', 'sebaran', 'metode', 'batasan'].forEach(function (id) { var el = document.getElementById(id); if (el) spy.observe(el); });

  // Tutup menu mobile setelah memilih tautan
  var menu = document.getElementById('menu');
  navLinks.forEach(function (a) {
    a.addEventListener('click', function () {
      if (menu.classList.contains('show')) bootstrap.Collapse.getOrCreateInstance(menu).hide();
    });
  });

  // ── Penampil contoh foto (opsional, hanya jika ada di halaman) ──
  if ($('#spec')) (function () {
    var tabs = $$('.lp-spec__tab');
    var img = $('#spec-img');
    var cap = $('#spec-cap');
    if (tabs.length && img && cap) {
      var specKey = tabs.length ? tabs[0].dataset.key : null;
      var specIdx = 0;

      function renderSpec() {
        var list = D.contoh[specKey] || [];
        var k = BY_KEY[specKey];
        tabs.forEach(function (t) {
          var on = t.dataset.key === specKey;
          t.setAttribute('aria-selected', on);
          t.tabIndex = on ? 0 : -1;
        });
        if (!list.length) { img.removeAttribute('src'); cap.textContent = 'Belum ada contoh untuk tingkat ini.'; return; }
        var c = list[specIdx % list.length];
        img.src = c.src;
        img.alt = 'Foto jalan ' + c.citra + ', label dan prediksi ' + k.nama;
        cap.innerHTML = '';
        var b = document.createElement('b'); b.textContent = c.citra;
        cap.appendChild(b);
        cap.appendChild(document.createTextNode(' · prediksi ' + k.nama + ', keyakinan ' + fmt(c.confidence) + '%'));
      }
      tabs.forEach(function (t, i) {
        t.addEventListener('click', function () { specKey = t.dataset.key; specIdx = 0; renderSpec(); });
        t.addEventListener('keydown', function (e) {
          var d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
          if (!d) return;
          e.preventDefault();
          var n = tabs[(i + d + tabs.length) % tabs.length];
          n.focus(); n.click();
        });
      });
      var nextBtn = $('#spec-next');
      if (nextBtn) nextBtn.addEventListener('click', function () { specIdx += 1; renderSpec(); });
      img.addEventListener('error', function () { cap.textContent = 'Foto tidak dapat dimuat.'; });
      renderSpec();
    }
  })();

  // ── Peta ─────────────────────────────────────────────────────────────
  var map = L.map('landing-map', { scrollWheelZoom: false }).setView([5.1801, 97.1499], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; kontributor OpenStreetMap'
  }).addTo(map);
  // Zoom dengan scroll hanya setelah peta diklik, supaya halaman tidak macet saat digulir.
  map.on('focus', function () { map.scrollWheelZoom.enable(); });
  map.on('blur', function () { map.scrollWheelZoom.disable(); });

  var layer = L.layerGroup().addTo(map);
  var features = [];
  var filter = 'all';
  var onlyMiss = false;
  var elLoading = $('#map-loading');
  var elError = $('#map-error');
  var elCount = $('#map-count');

  function popup(p, kls) {
    var wrap = document.createElement('div');
    wrap.className = 'lp-pop';
    if (p.path_file) {
      var im = document.createElement('img');
      im.alt = 'Foto ' + p.nama_citra;
      im.src = '/static/' + p.path_file.split('/').map(encodeURIComponent).join('/');
      im.onerror = function () { im.remove(); };
      wrap.appendChild(im);
    }
    var dl = document.createElement('dl');
    [['Lokasi', p.nama_citra], ['Prediksi', p.prediksi], ['Label', p.aktual && p.aktual !== '?' ? p.aktual : '-'],
     ['Keyakinan', fmt(p.confidence * 100) + '%'], ['Hasil', p.benar ? 'Sama dengan label' : 'Berbeda dari label']]
      .forEach(function (r) {
        var dt = document.createElement('dt'); dt.textContent = r[0];
        var dd = document.createElement('dd'); dd.textContent = r[1];
        dl.appendChild(dt); dl.appendChild(dd);
      });
    wrap.appendChild(dl);
    return wrap;
  }

  function render() {
    layer.clearLayers();
    var shown = features.filter(function (f) {
      var p = f.properties;
      if (filter !== 'all' && (BY_NAMA[p.prediksi] || {}).key !== filter) return false;
      return !onlyMiss || !p.benar;
    });
    var bounds = [];
    shown.forEach(function (f) {
      var p = f.properties, ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
      bounds.push(ll);
      L.circleMarker(ll, {
        radius: 8, fillColor: p.warna, fillOpacity: .9, color: '#12161C', weight: p.benar ? 1 : 2.5,
        dashArray: p.benar ? null : '3 3'
      }).bindPopup(function () { return popup(p); }, { maxWidth: 240 }).addTo(layer);
    });
    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
    elCount.textContent = shown.length ? shown.length + ' titik ditampilkan' : 'Tidak ada titik untuk kombinasi filter ini.';
  }

  function setFilter(key) {
    filter = key;
    $$('#filters .lp-filter').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.filter === key); });
    render();
  }
  $$('#filters .lp-filter').forEach(function (b) { b.addEventListener('click', function () { setFilter(b.dataset.filter); }); });
  $('#only-miss').addEventListener('change', function (e) { onlyMiss = e.target.checked; render(); });
  // Segmen penggaris di hero membuka peta pada tingkat yang sama
  $$('.lp-ruler__seg').forEach(function (b) {
    b.addEventListener('click', function () {
      setFilter(b.dataset.filter);
      document.getElementById('peta').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    });
  });

  function load() {
    elError.classList.remove('is-on');
    elLoading.classList.add('is-on');
    fetch('/api/landing/gis').then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (g) {
      features = g.features || [];
      elLoading.classList.remove('is-on');
      map.invalidateSize();
      render();
    }).catch(function () {
      elLoading.classList.remove('is-on');
      elError.classList.add('is-on');
      elCount.textContent = 'Titik tidak dimuat.';
    });
  }
  $('#map-retry').addEventListener('click', load);
  load();

  // ── Confusion matrix ─────────────────────────────────────────────────
  var read = $('#cm-read');
  var cells = $$('.lp-cm__c');
  cells.forEach(function (c) {
    c.addEventListener('click', function () {
      var i = +c.dataset.i, j = +c.dataset.j, v = D.cm[i][j];
      var tot = D.cm[i].reduce(function (a, b) { return a + b; }, 0);
      cells.forEach(function (o) { o.setAttribute('aria-pressed', o === c); });
      var teks = i === j
        ? v + ' dari ' + tot + ' foto berlabel ' + KELAS[i].nama + ' diprediksi benar (' + fmt(tot ? v / tot * 100 : 0) + '%).'
        : v + ' foto berlabel ' + KELAS[i].nama + ' diprediksi ' + KELAS[j].nama + ', dari ' + tot + ' foto berlabel ' + KELAS[i].nama + '.';
      read.textContent = teks;
    });
  });

  // ── Grafik akurasi per epoch ─────────────────────────────────────────
  var H = D.riwayat;
  var svg = $('#chart');
  var range = $('#chart-range');
  var out = $('#chart-read');
  var W = 560, HT = 300, m = { l: 44, r: 12, t: 12, b: 30 };
  var NS = 'http://www.w3.org/2000/svg';
  var lo = Math.floor(Math.min.apply(null, H.map(function (h) { return Math.min(h.acc, h.val); })) * 10) / 10;
  var x = function (e) { return m.l + (e - 1) / (H.length - 1) * (W - m.l - m.r); };
  var y = function (v) { return m.t + (1 - (v - lo) / (1 - lo)) * (HT - m.t - m.b); };
  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    (parent || svg).appendChild(n);
    return n;
  }
  for (var g = lo; g <= 1.0001; g += .1) {
    el('line', { x1: m.l, x2: W - m.r, y1: y(g), y2: y(g), stroke: '#D3D9E0', 'stroke-width': 1 });
    var t = el('text', { x: m.l - 6, y: y(g) + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#5F6B7A' });
    t.textContent = Math.round(g * 100) + '%';
  }
  [1, 10, 20, 30, 40, H.length].forEach(function (e) {
    if (e > H.length) return;
    var t = el('text', { x: x(e), y: HT - 10, 'text-anchor': 'middle', 'font-size': 11, fill: '#5F6B7A' });
    t.textContent = e;
  });
  if (D.fase1 && D.fase1 < H.length) {
    el('line', { x1: x(D.fase1 + .5), x2: x(D.fase1 + .5), y1: m.t, y2: HT - m.b, stroke: '#12161C', 'stroke-dasharray': '4 4' });
    var f2 = el('text', { x: x(D.fase1 + .5) + 5, y: m.t + 12, 'font-size': 11, fill: '#12161C' });
    f2.textContent = 'Fase 2';
  }
  var path = function (key) { return H.map(function (h, i) { return (i ? 'L' : 'M') + x(h.e).toFixed(1) + ' ' + y(h[key]).toFixed(1); }).join(' '); };
  el('path', { d: path('acc'), fill: 'none', stroke: '#12161C', 'stroke-width': 2, 'stroke-dasharray': '5 3' });
  el('path', { d: path('val'), fill: 'none', stroke: '#0F4C81', 'stroke-width': 3 });
  var cur = el('line', { y1: m.t, y2: HT - m.b, stroke: '#0F4C81', 'stroke-width': 1 });
  var d1 = el('circle', { r: 4.5, fill: '#12161C' });
  var d2 = el('circle', { r: 5, fill: '#0F4C81' });

  function at(e) {
    e = Math.max(1, Math.min(H.length, e));
    var h = H[e - 1];
    cur.setAttribute('x1', x(e)); cur.setAttribute('x2', x(e));
    d1.setAttribute('cx', x(e)); d1.setAttribute('cy', y(h.acc));
    d2.setAttribute('cx', x(e)); d2.setAttribute('cy', y(h.val));
    range.value = e;
    out.textContent = 'Epoch ' + e + (e > D.fase1 ? ' (Fase 2)' : ' (Fase 1)') + ' · latih ' + fmt(h.acc * 100) + '% · validasi ' + fmt(h.val * 100) + '%';
  }
  range.addEventListener('input', function () { at(+range.value); });
  svg.addEventListener('pointermove', function (ev) {
    var r = svg.getBoundingClientRect();
    var px = (ev.clientX - r.left) / r.width * W;
    at(Math.round(1 + (px - m.l) / (W - m.l - m.r) * (H.length - 1)));
  });
  at(H.reduce(function (b, h, i) { return h.val > H[b].val ? i : b; }, 0) + 1);
})();
