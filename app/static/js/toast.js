(function () {
  var DURATION = 4000;

  var STYLES = {
    success: 'toast toast--ok',
    warning: 'toast toast--warn',
    danger: 'toast toast--danger',
    error: 'toast toast--danger',
    info: 'toast toast--info'
  };

  var ICONS = {
    success: 'bi bi-check-circle-fill',
    warning: 'bi bi-exclamation-triangle-fill',
    danger: 'bi bi-x-circle-fill',
    error: 'bi bi-x-circle-fill',
    info: 'bi bi-info-circle-fill'
  };

  function showToast(message, category) {
    var container = document.getElementById('toast-container');
    if (!container) return;

    var toast = document.createElement('div');
    var type = category || 'info';
    toast.setAttribute('role', 'alert');
    toast.className = STYLES[type] || STYLES.info;
    toast.innerHTML =
      '<i class="toast__icon ' + (ICONS[type] || ICONS.info) + '" aria-hidden="true"></i>' +
      '<p class="toast__message">' + escapeHtml(message) + '</p>' +
      '<button type="button" class="toast__close" aria-label="Tutup">' +
        '<i class="bi bi-x-lg" aria-hidden="true"></i>' +
      '</button>' +
      '<div class="tw-progress-bar" aria-hidden="true"></div>';

    toast._dismiss = function () { dismiss(toast); };
    toast.querySelector('.toast__close').addEventListener('click', toast._dismiss);
    container.appendChild(toast);

    requestAnimationFrame(function () {
      toast.classList.add('is-visible');
      var bar = toast.querySelector('.tw-progress-bar');
      if (bar) bar.style.width = '0%';
    });

    var timer = setTimeout(function () { dismiss(toast); }, DURATION);

    toast.addEventListener('mouseenter', function () { clearTimeout(timer); });
    toast.addEventListener('mouseleave', function () {
      timer = setTimeout(function () { dismiss(toast); }, 1500);
    });
  }

  function dismiss(toast) {
    toast.classList.remove('is-visible');
    toast.classList.add('is-leaving');
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 220);
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  document.addEventListener('DOMContentLoaded', function () {
    var el = document.getElementById('flash-data');
    if (!el) return;
    try {
      var messages = JSON.parse(el.textContent || el.innerText);
      messages.forEach(function (pair) { showToast(pair[1], pair[0]); });
    } catch (e) {}
  });

  window.showToast = showToast;
}());
