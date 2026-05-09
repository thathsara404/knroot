/**
 * auth.js — HTMX auth form response handling.
 *
 * Handles error display and Alpine.js field-error injection for login/register forms.
 * Called via hx-on::after-request on the form element.
 *
 * @param {CustomEvent} evt   - HTMX after-request event
 * @param {string}      errorId - ID of the banner error element to show/hide
 */
function handleAuthResponse(evt, errorId) {
  const xhr = evt.detail.xhr;
  const errorEl = document.getElementById(errorId);
  if (!errorEl) return;

  if (xhr.status >= 400) {
    let bannerMsg = 'Something went wrong. Please try again.';
    let fieldErrors = {};

    try {
      const data = JSON.parse(xhr.responseText);

      if (data.fields && Object.keys(data.fields).length > 0) {
        fieldErrors = data.fields;

        const knownFields = [
          'first_name', 'last_name', 'username', 'email',
          'phone', 'password', 'confirm_password', 'identifier',
        ];
        const unknown = Object.entries(data.fields)
          .filter(([k]) => !knownFields.includes(k))
          .map(([, v]) => v);

        if (unknown.length > 0) {
          errorEl.textContent = unknown.join(' · ');
          errorEl.classList.remove('hidden');
        } else if (data.error) {
          errorEl.textContent = data.error;
          errorEl.classList.remove('hidden');
        } else {
          errorEl.classList.add('hidden');
        }
      } else {
        errorEl.textContent = data.error || bannerMsg;
        errorEl.classList.remove('hidden');
      }
    } catch (_) {
      errorEl.textContent = bannerMsg;
      errorEl.classList.remove('hidden');
    }

    // Inject field-level errors into the nearest Alpine component (register form).
    const form = evt.target;
    if (form && form._x_dataStack) {
      const alpineData = form._x_dataStack[0];
      if (alpineData && 'fieldErrors' in alpineData) {
        alpineData.fieldErrors = fieldErrors;
      }
    }
  } else {
    errorEl.classList.add('hidden');
  }
}
