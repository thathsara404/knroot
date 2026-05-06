// Global HTMX config
htmx.config.defaultSwapStyle = 'outerHTML';

// Redirect the browser when HTMX receives an HX-Redirect response header.
document.body.addEventListener('htmx:beforeSwap', function (evt) {
  const redirect = evt.detail.xhr.getResponseHeader('HX-Redirect');
  if (redirect) {
    evt.detail.shouldSwap = false;
    window.location.assign(redirect);
  }
});

// Show a toast on unhandled HTMX errors (non-2xx without a dedicated form handler).
document.body.addEventListener('htmx:responseError', function (evt) {
  let msg = 'An error occurred. Please try again.';
  try {
    const data = JSON.parse(evt.detail.xhr.responseText);
    msg = data.error || msg;
  } catch (_) {}
  Toast.error(msg);
});

// Render server-side flash messages as toasts on page load.
document.addEventListener('DOMContentLoaded', function () {
  const flashEl = document.getElementById('flash-data');
  if (!flashEl) return;
  try {
    const messages = JSON.parse(flashEl.textContent);
    messages.forEach(function (pair) {
      const category = pair[0];
      const message  = pair[1];
      if (typeof Toast[category] === 'function') {
        Toast[category](message);
      } else {
        Toast.info(message);
      }
    });
  } catch (_) {}
});
