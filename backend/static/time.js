(function () {
  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  function format(isoStr) {
    if (!isoStr) return '';
    var dt = new Date(isoStr);
    if (isNaN(dt.getTime())) return '';

    var now = new Date();
    var diffMs = now - dt;
    if (diffMs < 0) diffMs = 0;

    var diffMins  = Math.floor(diffMs / 60000);
    var diffHours = Math.floor(diffMs / 3600000);
    var diffDays  = Math.floor(diffMs / 86400000);

    // Date label uses the user's local timezone (JS Date methods are always local)
    var sameYear  = dt.getFullYear() === now.getFullYear();
    var dateLabel = MONTHS[dt.getMonth()] + ' ' + dt.getDate();
    if (!sameYear) dateLabel += ', ' + dt.getFullYear();

    var rel;
    if (diffMins  < 1)  rel = 'just now';
    else if (diffHours < 1)  rel = diffMins  + 'm ago';
    else if (diffDays  < 1)  rel = diffHours + 'h ago';
    else if (diffDays === 1) rel = 'Yesterday';
    else if (diffDays < 7)   rel = diffDays  + 'd ago';
    else return dateLabel;   // old enough — date alone is sufficient

    return dateLabel + ' · ' + rel;
  }

  function updateAll() {
    var els = document.querySelectorAll('time[data-knr-time]');
    for (var i = 0; i < els.length; i++) {
      var el  = els[i];
      var iso = el.getAttribute('datetime');
      var out = format(iso);
      if (out) el.textContent = out;
    }
  }

  // Initial render + re-render after HTMX swaps (fragments loaded via hx-get)
  document.addEventListener('DOMContentLoaded', updateAll);
  document.addEventListener('htmx:afterSwap',   updateAll);

  // Refresh every 60 s so "1m ago" ticks to "2m ago" without a page reload
  setInterval(updateAll, 60000);
})();
