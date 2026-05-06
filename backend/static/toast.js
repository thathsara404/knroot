/**
 * toast.js — Reusable toast notification utility.
 *
 * API:
 *   Toast.show(message, type, duration)
 *   Toast.success(message)
 *   Toast.error(message)
 *   Toast.warning(message)
 *   Toast.info(message)
 *
 * The container (#toast-container) is created on first use if not already in the DOM.
 * Loaded globally via base.html before app.js so both files can call Toast.*
 */
const Toast = (() => {
  const STYLES = {
    success: 'bg-green-100 border-green-200 text-green-800',
    error:   'bg-red-100 border-red-200 text-red-800',
    warning: 'bg-amber-100 border-amber-200 text-amber-800',
    info:    'bg-blue-100 border-blue-200 text-blue-800',
  };
  const ICONS = {
    success: '✓',
    error:   '✕',
    warning: '⚠',
    info:    'ℹ',
  };

  function getContainer() {
    let c = document.getElementById('toast-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'toast-container';
      c.setAttribute('aria-live', 'polite');
      c.setAttribute('aria-atomic', 'false');
      c.className = 'fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none';
      document.body.appendChild(c);
    }
    return c;
  }

  function dismiss(el) {
    if (!el.parentNode) return;
    clearTimeout(el._toastTimer);
    el.style.opacity = '0';
    el.style.transform = 'translateY(-4px)';
    setTimeout(() => el.remove(), 300);
  }

  function show(message, type, duration) {
    if (type === undefined) type = 'info';
    if (duration === undefined) duration = 4000;

    const styles = STYLES[type] || STYLES.info;
    const icon = ICONS[type] || ICONS.info;

    const el = document.createElement('div');
    el.setAttribute('role', 'alert');
    el.className = [
      'flex items-center gap-2 rounded-lg px-4 py-3 text-sm shadow-md border',
      'pointer-events-auto',
      styles,
    ].join(' ');
    el.style.transition = 'opacity 300ms, transform 300ms';
    el.style.opacity = '0';
    el.style.transform = 'translateY(-4px)';

    const iconSpan = document.createElement('span');
    iconSpan.setAttribute('aria-hidden', 'true');
    iconSpan.textContent = icon;

    const textSpan = document.createElement('span');
    textSpan.className = 'flex-1';
    textSpan.textContent = message;

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'ml-1 font-bold opacity-60 hover:opacity-100 focus:outline-none';
    closeBtn.setAttribute('aria-label', 'Dismiss notification');
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', function () { dismiss(el); });

    el.appendChild(iconSpan);
    el.appendChild(textSpan);
    el.appendChild(closeBtn);
    getContainer().appendChild(el);

    requestAnimationFrame(function () {
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    });

    el._toastTimer = setTimeout(function () { dismiss(el); }, duration);
    return el;
  }

  return {
    show:    show,
    success: function (msg, dur) { return show(msg, 'success', dur); },
    error:   function (msg, dur) { return show(msg, 'error',   dur); },
    warning: function (msg, dur) { return show(msg, 'warning', dur); },
    info:    function (msg, dur) { return show(msg, 'info',    dur); },
  };
})();
