/* Progres interaktif untuk proses panjang (POST biasa).

   Dua mode:
   - Tanpa data-progress-url: POST dikirim setelah data-progress-delay ms; overlay
     menampilkan tahapan bergilir (progressSteps) dan bilah persen merayap
     (indeterminate) supaya user tahu proses masih hidup.
   - Dengan data-progress-url: POST dijalankan lewat fetch sementara persen nyata
     diambil dari endpoint JSON itu; ETA dihitung dari laju persen.

   Selalu tampil: penghitung waktu berjalan, ETA (bila persen nyata), dan tombol
   "Batalkan & tutup" yang melepas overlay saat proses server jalan lama/nyangkut.

   Pemakaian: tambah data-progress="Judul" pada <form>, panggil
   window.progressSteps(['tahap', ...]). Dipakai otomatis oleh showConfirmForm
   di base.html dan oleh submit handler di bawah untuk form tanpa konfirmasi. */
(function () {
  var overlay, titleEl, subEl, fillEl, pctEl, stepsEl, etaEl, cancelEl;
  var steps = [], stopCycle = false, pollSecs = 0;
  var startedAt = 0, tickTimer = null, creepTimer = null;
  var creepPct = 0, lastRealPct = null, etaAnchorPct = null, etaAnchorMs = 0;

  function $(id) { return document.getElementById(id); }

  function cache() {
    overlay  = $('pv-overlay');
    titleEl  = $('pvTitle');
    subEl    = $('pvSub');
    fillEl   = $('pvFill');
    pctEl    = $('pvPct');
    stepsEl  = $('pvSteps');
    etaEl    = $('pvEta');
    cancelEl = $('pvCancel');
  }

  function setSteps(list) {
    steps = list || [];
    if (!stepsEl) return;
    stepsEl.innerHTML = '';
    steps.forEach(function (s) {
      var li = document.createElement('li');
      li.className = 'pv-step';
      li.textContent = s;
      stepsEl.appendChild(li);
    });
  }

  function markStep(i) {
    if (!stepsEl) return;
    Array.prototype.forEach.call(stepsEl.children, function (li, n) {
      li.classList.toggle('is-active', n === i);
      li.classList.toggle('is-done', n < i);
    });
  }

  function fmt(secs) {
    if (!isFinite(secs) || secs < 0) return '';
    if (secs < 60) return Math.round(secs) + ' dtk';
    var m = Math.floor(secs / 60), s = Math.round(secs % 60);
    return m + ' mnt ' + (s < 10 ? '0' : '') + s + ' dtk';
  }

  function setPct(pct, nyata) {
    // Persen nyata dari server selalu menang atas bilah rayapan.
    if (nyata) {
      lastRealPct = pct;
      if (etaAnchorPct === null || pct < etaAnchorPct) {
        etaAnchorPct = pct;
        etaAnchorMs  = Date.now();
      } else if (pct > etaAnchorPct) {
        var dt = (Date.now() - etaAnchorMs) / 1000;
        var dp = (pct - etaAnchorPct) / 100;
        if (dp > 0 && dt > 1) etaEl.textContent = ' ± sisa ' + fmt(dt / dp * (1 - pct / 100));
      }
      creepPct = Math.max(creepPct, pct);
    }
    if (fillEl) fillEl.style.width = pct + '%';
    if (pctEl) pctEl.textContent = pct + '%';
  }

  function tick() {
    var el = Math.round((Date.now() - startedAt) / 1000);
    if (etaEl && !lastRealPct) etaEl.textContent = ' · ' + el + ' dtk';
  }

  /* Bilah rayap: naik cepat lalu melambat, mentok di 96% sampai persen nyata datang. */
  function creep() {
    if (creepTimer || lastRealPct !== null || stepTotal() === 0) return;
    creepTimer = setInterval(function () {
      creepPct += Math.max(0.2, (96 - creepPct) * 0.03);
      if (creepPct > 96) creepPct = 96;
      if (fillEl) fillEl.style.width = creepPct + '%';
      if (pctEl) pctEl.textContent = Math.floor(creepPct) + '%';
    }, 500);
  }

  function stepTotal() { return steps.length; }

  function show(title) {
    stopCycle  = false;
    startedAt  = Date.now();
    creepPct   = 0;
    lastRealPct = null;
    etaAnchorPct = null;
    if (!overlay) return;
    titleEl.textContent = title;
    subEl.textContent = steps.length ? steps[0] : 'Menyiapkan…';
    if (etaEl) etaEl.textContent = '';
    setPct(0);
    markStep(0);
    overlay.hidden = false;
    overlay.setAttribute('aria-hidden', 'false');
    if (cancelEl) cancelEl.hidden = false;
    tickTimer = setInterval(tick, 1000);
  }

  function stopTimers() {
    clearInterval(tickTimer);   tickTimer = null;
    clearInterval(creepTimer);  creepTimer = null;
  }

  function hide() {
    stopTimers();
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute('aria-hidden', 'true');
    if (cancelEl) cancelEl.hidden = true;
  }

  /* Tahapan bergilir: maju satu langkah tiap everyMs, mentok di langkah terakhir
     supaya tidak mengklaim lebih banyak daripada yang diketahui. */
  function cycle(startMs, everyMs) {
    if (!steps.length || stopCycle) return;
    var i = Math.min(steps.length - 1, Math.floor((Date.now() - startMs) / everyMs));
    markStep(i);
    subEl.textContent = steps[i];
    setTimeout(function () { cycle(startMs, everyMs); }, everyMs);
  }

  function fail(msg) {
    stopCycle = true;
    stopTimers();
    if (!overlay) { alert(msg); return; }
    setPct(100);
    overlay.classList.add('pv-overlay--error');
    titleEl.textContent = 'Proses gagal';
    subEl.textContent = msg;
    if (etaEl) etaEl.textContent = '';
    setTimeout(function () { overlay.classList.remove('pv-overlay--error'); hide(); }, 3000);
  }

  function post(form) {
    form.submit();
  }

  function poll(url, form) {
    var secs = pollSecs;
    setTimeout(function () {
      if (stopCycle) return;
      fetch(url)
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (d) {
          if (d.error) { fail(d.error); return; }
          if (d.status === 'running') {
            if (typeof d.pct === 'number') setPct(d.pct, true);
            subEl.textContent = d.step || (d.current && d.total ? d.current + ' / ' + d.total : subEl.textContent);
            poll(url, form);
            return;
          }
          if (d.status === 'gagal') { fail(d.error || 'Proses gagal.'); return; }
          if (d.reload) { location.replace(d.reload); return; }
          // 'selesai' tanpa reload (mis. server membalas flash & render ulang): POST-lah
          // yang membawa navigasi; hentikan polling supaya tidak menggantung.
          stopCycle = true;
        })
        .catch(function () { poll(url, form); });
    }, secs * 1000);
  }

  function run(form) {
    if (typeof form === 'string') form = document.getElementById(form);
    if (!form) return;

    var d = form.dataset;
    pollSecs = parseInt(d.progressPoll, 10) || 2;
    show(d.progress || d.progressTitle || 'Memproses…');

    if (d.progressUrl) {
      creep();   // jaring pengaman bila persen nyata lambat datang
      fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'fetch' }
      }).catch(function () { /* thread mungkin sudah jalan: biarkan polling */ });
      poll(d.progressUrl, form);
      return;
    }

    var everyMs = parseInt(d.progressInterval, 10) || 2000;
    creep();
    cycle(Date.now(), everyMs);
    setTimeout(function () { if (!stopCycle) post(form); }, parseInt(d.progressDelay, 10) || 400);
  }

  window.runWithProgress = run;
  window.progressSteps = setSteps;

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  function init() {
    cache();
    if (cancelEl) {
      cancelEl.addEventListener('click', function () {
        stopCycle = true;
        hide();
      });
    }
  }

  // Form ber-atribut data-progress yang tidak lewat dialog konfirmasi.
  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (!form || !form.dataset || !form.dataset.progress) return;
    if (form.dataset.progressDone === '0') return;
    ev.preventDefault();
    run(form);
  });
}());
