// confirm.js — theme-aware reusable confirmation dialog (replaces window.confirm).
// Usage: window.KnrConfirm({ title, message, confirmText, cancelText, danger }) → Promise<boolean>
(function () {
  'use strict';

  var _overlay = null;
  var _resolvePromise = null;

  function _buildDialog() {
    var el = document.createElement('div');
    el.id = 'knr-confirm-overlay';
    el.style.display = 'none';
    el.innerHTML =
      '<div class="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" id="knr-confirm-backdrop">' +
        '<div class="bg-white rounded-2xl shadow-2xl ring-1 ring-black/10 w-full max-w-sm overflow-hidden">' +
          '<div class="px-5 pt-5 pb-4">' +
            '<div class="flex items-start gap-3">' +
              '<div id="knr-confirm-icon" class="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center"></div>' +
              '<div class="flex-1 min-w-0 pt-0.5">' +
                '<h3 id="knr-confirm-title" class="text-sm font-semibold text-gray-900 leading-snug"></h3>' +
                '<p id="knr-confirm-message" class="mt-1.5 text-xs text-gray-500 leading-relaxed"></p>' +
              '</div>' +
            '</div>' +
          '</div>' +
          '<div class="px-5 pb-4 flex gap-2 justify-end border-t border-gray-100 pt-3">' +
            '<button id="knr-confirm-cancel" class="px-4 py-2 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-200">Cancel</button>' +
            '<button id="knr-confirm-ok" class="px-4 py-2 text-xs font-semibold text-white rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 shadow-sm"></button>' +
          '</div>' +
        '</div>' +
      '</div>';

    document.body.appendChild(el);

    document.getElementById('knr-confirm-cancel').addEventListener('click', function () {
      _resolve(false);
    });
    document.getElementById('knr-confirm-ok').addEventListener('click', function () {
      _resolve(true);
    });
    document.getElementById('knr-confirm-backdrop').addEventListener('click', function (e) {
      if (e.target === this) _resolve(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && _overlay && _overlay.style.display !== 'none') _resolve(false);
    });

    return el;
  }

  function _resolve(result) {
    if (_overlay) _overlay.style.display = 'none';
    if (_resolvePromise) {
      var cb = _resolvePromise;
      _resolvePromise = null;
      cb(result);
    }
  }

  window.KnrConfirm = function (options) {
    if (!_overlay) _overlay = _buildDialog();

    var title = options.title || 'Are you sure?';
    var message = options.message || '';
    var confirmText = options.confirmText || 'Confirm';
    var cancelText = options.cancelText || 'Cancel';
    var danger = options.danger !== false;

    document.getElementById('knr-confirm-title').textContent = title;
    document.getElementById('knr-confirm-message').textContent = message;
    document.getElementById('knr-confirm-cancel').textContent = cancelText;

    var okBtn = document.getElementById('knr-confirm-ok');
    okBtn.textContent = confirmText;

    var iconEl = document.getElementById('knr-confirm-icon');

    if (danger) {
      okBtn.className = 'px-4 py-2 text-xs font-semibold text-white bg-red-600 rounded-xl hover:bg-red-700 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 shadow-sm';
      iconEl.className = 'flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center bg-red-100';
      iconEl.innerHTML =
        '<svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
          '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" ' +
                'd="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M9 7V4a2 2 0 012-2h2a2 2 0 012 2v3"/>' +
        '</svg>';
    } else {
      okBtn.className = 'px-4 py-2 text-xs font-semibold text-white bg-indigo-600 rounded-xl hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 shadow-sm';
      iconEl.className = 'flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center bg-indigo-100';
      iconEl.innerHTML =
        '<svg class="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
          '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" ' +
                'd="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>' +
        '</svg>';
    }

    _overlay.style.display = '';

    return new Promise(function (res) {
      _resolvePromise = res;
    });
  };
}());
