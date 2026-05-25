(function () {
  var DURATION = 4000;

  var STYLES = {
    success: { wrap: 'bg-emerald-50 border-emerald-400 text-emerald-800', icon: 'text-emerald-500', bar: 'bg-emerald-400' },
    danger:  { wrap: 'bg-red-50 border-red-400 text-red-800',             icon: 'text-red-500',     bar: 'bg-red-400'     },
    warning: { wrap: 'bg-amber-50 border-amber-400 text-amber-800',       icon: 'text-amber-500',   bar: 'bg-amber-400'   },
    info:    { wrap: 'bg-blue-50 border-blue-400 text-blue-800',          icon: 'text-blue-500',    bar: 'bg-blue-400'    },
    error:   { wrap: 'bg-red-50 border-red-400 text-red-800',             icon: 'text-red-500',     bar: 'bg-red-400'     },
  };

  var ICONS = {
    success: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>',
    danger:  '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>',
    error:   '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>',
    warning: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>',
    info:    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>',
  };

  function showToast(message, category) {
    var container = document.getElementById('toast-container');
    if (!container) return;

    var s = STYLES[category] || STYLES.info;
    var iconPath = ICONS[category] || ICONS.info;

    var toast = document.createElement('div');
    toast.setAttribute('role', 'alert');
    toast.style.cssText = 'transform:translateX(110%);opacity:0;transition:transform 200ms ease-out,opacity 200ms ease-out;';
    toast.className = [
      'flex items-start gap-3 p-4 rounded-xl border shadow-lg relative overflow-hidden',
      s.wrap
    ].join(' ');

    toast.innerHTML =
      '<span class="flex-shrink-0 mt-0.5 ' + s.icon + '">' +
        '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">' + iconPath + '</svg>' +
      '</span>' +
      '<p class="flex-1 text-sm font-medium leading-snug">' + escapeHtml(message) + '</p>' +
      '<button type="button" onclick="this.closest(\'[role=alert]\')._dismiss()" ' +
              'class="flex-shrink-0 ' + s.icon + ' hover:opacity-60 cursor-pointer transition-opacity" aria-label="Tutup">' +
        '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
          '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>' +
        '</svg>' +
      '</button>' +
      '<div class="absolute bottom-0 left-0 h-0.5 ' + s.bar + ' tw-progress-bar" style="width:100%;transition:width ' + DURATION + 'ms linear;"></div>';

    toast._dismiss = function () { dismiss(toast); };

    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
        // Start progress bar
        var bar = toast.querySelector('.tw-progress-bar');
        if (bar) bar.style.width = '0%';
      });
    });

    var timer = setTimeout(function () { dismiss(toast); }, DURATION);

    // Pause on hover
    toast.addEventListener('mouseenter', function () { clearTimeout(timer); });
    toast.addEventListener('mouseleave', function () {
      timer = setTimeout(function () { dismiss(toast); }, 1500);
    });
  }

  function dismiss(toast) {
    toast.style.transform = 'translateX(110%)';
    toast.style.opacity = '0';
    setTimeout(function () { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 220);
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Hydrate flash messages rendered by Flask
  document.addEventListener('DOMContentLoaded', function () {
    var el = document.getElementById('flash-data');
    if (!el) return;
    try {
      var messages = JSON.parse(el.textContent || el.innerText);
      messages.forEach(function (pair) { showToast(pair[1], pair[0]); });
    } catch (e) {}
  });

  // Public API for manual toasts
  window.showToast = showToast;
}());
