/* Progres interaktif untuk proses panjang (POST biasa).

   Dua mode:
   - Tanpa data-progress-url: overlay indeterminate, tahapan bergilir tiap
     data-progress-interval ms, POST dikirim setelah data-progress-delay ms
     (menunda supaya browser dapat menggambar overlay sebelum handler Flask
     yang berat CPU memblokir main thread).
   - Dengan data-progress-url: POST dijalankan di thread background server,
     persen nyata diambil dari endpoint JSON itu.

   Pemakaian: tambah data-progress="Judul" pada <form>, panggil
   window.progressSteps(['tahap', ...]). Dipakai otomatis oleh showConfirmForm
   di base.html dan oleh submit handler di bawah untuk form Tanpa konfirmasi. */
(function () {
  var overlay, titleEl, subEl, fillEl, pctEl, stepsEl;
  var steps = [], stopCycle = false, pollSecs = 0;

  function $(id) { return document.getElementById(id); }

  function cache() {
    overlay = $('pv-overlay');
    titleEl = $('pvTitle');
    subEl   = $('pvSub');
    fillEl  = $('pvFill');
    pctEl   = $('pvPct');
    stepsEl = $('pvSteps');
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

  function setPct(pct) {
    if (fillEl) fillEl.style.width = pct + '%';
    if (pctEl) pctEl.textContent = pct + '%';
  }

  function show(title) {
    stopCycle = false;
    if (!overlay) return;
    titleEl.textContent = title;
    subEl.textContent = steps.length ? steps[0] : 'Menyiapkan…';
    setPct(0);
    markStep(0);
    overlay.hidden = false;
    overlay.setAttribute('aria-hidden', 'false');
  }

  function hide() {
    if (!overlay) return;
    overlay.hidden = true;
    overlay.setAttribute('aria-hidden', 'true');
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
    if (!overlay) { alert(msg); return; }
    setPct(100);
    overlay.classList.add('pv-overlay--error');
    titleEl.textContent = 'Proses gagal';
    subEl.textContent = msg;
    setTimeout(function () { overlay.classList.remove('pv-overlay--error'); hide(); }, 3000);
  }

  /* POST biasa lalu ikuti redirect Flask. Saat ini halaman hanya live (overlay
     tergambar, main thread bebas) sehingga navigasi terjadi di akhir proses. */
  function post(form) {
    form.submit();
  }

  function poll(url, form) {
    var secs = pollSecs;
    setTimeout(function () {
      fetch(url)
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (d) {
          if (d.error) { fail(d.error); return; }
          if (d.status === 'running') {
            if (typeof d.pct === 'number') setPct(d.pct);
            subEl.textContent = d.step || (d.current && d.total ? d.current + ' / ' + d.total : subEl.textContent);
            poll(url, form);
            return;
          }
          if (d.reload) { location.replace(d.reload); return; }
          poll(url, form);   // selesai tapi belum ada lokasi hasil: tunggu sebentar lagi
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
    var delayMs = parseInt(d.progressDelay, 10) || 400;
    cycle(Date.now(), everyMs);
    setTimeout(function () { if (!stopCycle) post(form); }, delayMs);
  }

  window.runWithProgress = run;
  window.progressSteps = setSteps;

  // Halaman yang selesai memproses dimuat sebagai GET biasa → form tidak dijalankan lagi.
  if (location.search.indexOf('proses=selesai') !== -1) cache();

  // Form ber-atribut data-progress yang tidak lewat dialog konfirmasi.
  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (!form || !form.dataset || !form.dataset.progress) return;
    if (form.dataset.progressDone === '0') return;
    ev.preventDefault();
    run(form);
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', cache);
  else cache();
}());
