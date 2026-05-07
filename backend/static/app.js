// app.js — Knowledge Root global HTMX wiring + application logic

// =============================================================================
// Global HTMX configuration
// =============================================================================

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
      const message = pair[1];
      if (typeof Toast[category] === 'function') {
        Toast[category](message);
      } else {
        Toast.info(message);
      }
    });
  } catch (_) {}
});

// =============================================================================
// Helpers — locate the active Alpine appState() component
// =============================================================================

function _getAppData() {
  const el = document.querySelector('[x-data="appState()"]');
  if (!el) return null;
  // Alpine v3 stores reactive data on _x_dataStack (array, top-most first)
  if (el._x_dataStack && el._x_dataStack.length) {
    return el._x_dataStack[0];
  }
  return null;
}

// =============================================================================
// Alpine component: appState() — main dashboard
// =============================================================================

function appState() {
  return {
    sidebarOpen: true,
    activeSessionId: null,
    chatLoading: false,
    quizLoading: false,
    sidebarWidth: parseInt(localStorage.getItem('knroot_sidebar_w') || '256'),
    rightPanelWidth: parseInt(localStorage.getItem('knroot_right_w') || '320'),
    isPanelDragging: false,

    init() {
      const saved = localStorage.getItem('knroot_sidebar');
      if (saved !== null) this.sidebarOpen = saved === 'true';
      this.$watch('sidebarOpen', (v) => localStorage.setItem('knroot_sidebar', v));
      this.$watch('sidebarWidth', (v) => localStorage.setItem('knroot_sidebar_w', String(v)));
      this.$watch('rightPanelWidth', (v) => localStorage.setItem('knroot_right_w', String(v)));
      // Release any in-progress drag on mouseup regardless of where it ends
      window.addEventListener('mouseup', () => {
        this.isPanelDragging = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      });
      window.addEventListener('mousemove', (e) => {
        if (!this.isPanelDragging) return;
        if (this._dragSide === 'left') {
          const container = document.querySelector('[x-data="appState()"]');
          const ox = container ? container.getBoundingClientRect().left : 0;
          this.sidebarWidth = Math.max(180, Math.min(480, e.clientX - ox));
        } else {
          const container = document.querySelector('[x-data="appState()"]');
          const right = container ? container.getBoundingClientRect().right : window.innerWidth;
          this.rightPanelWidth = Math.max(200, Math.min(600, right - e.clientX));
        }
      });
    },

    startResize(event, side) {
      this.isPanelDragging = true;
      this._dragSide = side;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    },

    setActiveFromEvent(event) {
      if (event && event.detail && event.detail.sessionId) {
        this.activeSessionId = event.detail.sessionId;
      }
    },

    generateQuiz() {
      const sessionId = this.activeSessionId;
      if (!sessionId) {
        Toast.error('No active session. Start a conversation first.');
        return;
      }
      generateQuizForSession(
        sessionId,
        (v) => { this.quizLoading = v; },
        () => {
          const sl = document.getElementById('session-list');
          if (sl) htmx.ajax('GET', `/sessions/partial?expand=${sessionId}`, { target: sl, swap: 'innerHTML' });
        },
      );
    },

    newChat() {
      fetch('/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_type: 'regular' }),
      })
        .then((r) => {
          if (!r.ok) throw new Error('Failed to create session');
          return r.json();
        })
        .then((session) => {
          this.activeSessionId = session.id;
          const messages = document.getElementById('chat-messages');
          if (messages) {
            messages.innerHTML =
              '<div class="text-sm text-gray-400 text-center py-8">' +
              'New conversation started. Say something!' +
              '</div>';
          }
          // Restore news panel in the right pane.
          htmx.ajax('GET', '/news/partial?category=ai', {
            target: '#right-panel',
            swap: 'innerHTML',
          });
          const sl = document.getElementById('session-list');
          if (sl) htmx.trigger(sl, 'sessionListRefresh');
        })
        .catch(() => Toast.error('Could not create session'));
    },
  };
}

// =============================================================================
// Alpine component: learnState(sessionId) — learn/session page
// =============================================================================

function learnState(sessionId) {
  return {
    sidebarOpen: false,
    sessionId: sessionId,

    init() {
      const saved = localStorage.getItem('knroot_sidebar');
      if (saved !== null) this.sidebarOpen = saved === 'true';
      this.$watch('sidebarOpen', (v) => localStorage.setItem('knroot_sidebar', v));
    },
  };
}

// =============================================================================
// Global functions called from templates (hx-on / onclick / @click)
// =============================================================================

// Mark a session as active in the sidebar and surface to Alpine state.
window.setActiveSession = function (sessionId) {
  window._activeSessionId = sessionId;

  // Update hidden session_id inputs directly so the form value is always correct.
  document.querySelectorAll('input[name="session_id"]').forEach((el) => {
    el.value = sessionId;
  });

  // Dispatch the event that Alpine's @session-activated.window listener handles.
  // Mutating _x_dataStack[0] directly bypasses Alpine's reactive proxy — this
  // event is the correct way to update Alpine state from outside Alpine.
  window.dispatchEvent(new CustomEvent('session-activated', { detail: { sessionId } }));

  // Highlight the clicked session row in the sidebar.
  document.querySelectorAll('#session-list a').forEach((a) => {
    a.classList.remove('bg-gray-800', 'text-white');
  });

  // Switch right panel to knowledge tree for the active session.
  htmx.ajax('GET', `/sessions/${sessionId}/knowledge-tree/partial`, {
    target: '#right-panel',
    swap: 'innerHTML',
  });
};

// Toggle chat-loading state from HTMX before-request hooks.
window.setChatLoading = function (val) {
  const data = _getAppData();
  if (data) data.chatLoading = !!val;
};

// After a chat message is sent: scroll to bottom, clear loading, refresh sidebar.
window.onChatResponse = function (event) {
  const messages = document.getElementById('chat-messages');
  if (messages) messages.scrollTop = messages.scrollHeight;

  const data = _getAppData();
  if (data) data.chatLoading = false;

  // Hide the welcome placeholder once any message is appended.
  const welcome = document.getElementById('chat-welcome');
  if (welcome) welcome.style.display = 'none';

  if (event && event.detail && event.detail.successful) {
    const form = event.target;
    if (form && form.tagName === 'FORM') {
      const ta = form.querySelector('textarea[name="message"]');
      if (ta) ta.value = '';
    }
    // Read new session ID if server created one (auto-created session on first send).
    const xhr = event.detail.xhr;
    if (xhr) {
      const sid = xhr.getResponseHeader('HX-Session-Id');
      if (sid) window.setActiveSession(sid);
    }
  }

  // Refresh session list so the most recent session bubbles up.
  setTimeout(() => {
    const sl = document.getElementById('session-list');
    if (sl) htmx.trigger(sl, 'sessionListRefresh');
  }, 300);
};

// Load a "Learn More" sub-session inline in the chat pane (no new tab).
window.exploreSection = function (sessionId, topic, btn, callback) {
  // Show a loading state immediately so the user sees something while the LLM runs
  const messages = document.getElementById('chat-messages');
  if (messages) {
    const safeT = topic.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    messages.innerHTML =
      '<div class="flex items-center justify-center h-full">' +
        '<div class="text-center space-y-3 text-gray-400">' +
          '<svg class="animate-spin w-8 h-8 mx-auto text-indigo-500" fill="none" viewBox="0 0 24 24">' +
            '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>' +
            '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>' +
          '</svg>' +
          '<p class="text-sm">Exploring <span class="font-medium text-gray-600">' + safeT + '</span>…</p>' +
        '</div>' +
      '</div>';
  }

  fetch(`/sessions/${sessionId}/learn-more`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic: topic }),
  })
    .then((r) => {
      if (!r.ok) throw new Error('Failed to create learn-more session');
      return r.json();
    })
    .then((result) => {
      const newId = result.session_id;
      // Load the generated content into the chat pane
      htmx.ajax('GET', `/sessions/${newId}/messages/partial`, {
        target: '#chat-messages',
        swap: 'innerHTML',
      });
      // Mark the new session as active (updates hidden inputs + knowledge tree)
      window.setActiveSession(newId);
      // Expand parent in sidebar so the new sub-thread is visible without page refresh
      const sl = document.getElementById('session-list');
      if (sl) htmx.ajax('GET', `/sessions/partial?expand=${sessionId}`, { target: sl, swap: 'innerHTML' });
      if (callback) callback(true);
    })
    .catch(() => {
      if (messages) {
        messages.innerHTML =
          '<div class="text-center py-10 text-gray-400 text-sm">' +
          'Could not load exploration. Please try again.</div>';
      }
      Toast.error('Could not load exploration');
      if (callback) callback(false);
    });
};

// Generate a quiz scoped to a specific section and open it in a new tab.
window.generateSectionQuiz = function (sessionId, sectionTitle, sectionContent, btn, callback) {
  if (btn) btn.disabled = true;
  // Open blank tab synchronously — browsers block window.open() inside async .then()
  const newTab = window.open('about:blank', '_blank', 'noopener,noreferrer');

  fetch('/quiz/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      section_title: sectionTitle,
      section_content: sectionContent,
    }),
  })
    .then((r) => {
      if (!r.ok) return r.json().then((d) => Promise.reject(d.error || 'Quiz generation failed'));
      return r.json();
    })
    .then((data) => {
      if (newTab) newTab.location.href = '/quiz/' + data.attempt_id;
      // Refresh sidebar with parent expanded so new quiz sub-thread is visible immediately
      const sl = document.getElementById('session-list');
      if (sl) htmx.ajax('GET', `/sessions/partial?expand=${sessionId}`, { target: sl, swap: 'innerHTML' });
      if (callback) callback(true);
    })
    .catch((err) => {
      if (newTab) newTab.close();
      Toast.error(typeof err === 'string' ? err : 'Could not generate quiz');
      if (btn) btn.disabled = false;
      if (callback) callback(false);
    });
};

// After a news "Discuss" button creates a new session.
window.onDiscussResponse = function (event) {
  if (!event || !event.detail) return;
  const xhr = event.detail.xhr;
  if (!xhr || xhr.status >= 400) return;

  const sessionId = xhr.getResponseHeader('HX-Session-Id');
  if (sessionId) {
    window.setActiveSession(sessionId);
    // Ensure the hidden input in the chat form has the session id immediately.
    document.querySelectorAll('input[name="session_id"]').forEach((el) => {
      el.value = sessionId;
    });
  }

  const sl = document.getElementById('session-list');
  if (sl) htmx.trigger(sl, 'sessionListRefresh');

  const messages = document.getElementById('chat-messages');
  if (messages) messages.scrollTop = messages.scrollHeight;
};

// Restore the news panel in the right pane.
window.showNewsPanel = function () {
  htmx.ajax('GET', '/news/partial?category=ai', {
    target: '#right-panel',
    swap: 'innerHTML',
  });
};

// Delete a session from the sidebar (childCount = number of direct+indirect children).
window.deleteSession = function (sessionId, childCount) {
  const extra = childCount > 0
    ? ` and its ${childCount} sub-thread${childCount === 1 ? '' : 's'}`
    : '';
  if (!window.confirm(`Delete this session${extra}? This cannot be undone.`)) return;

  fetch(`/sessions/${sessionId}`, { method: 'DELETE' })
    .then((r) => {
      if (!r.ok) throw new Error('Delete failed');
      const sl = document.getElementById('session-list');
      if (sl) htmx.trigger(sl, 'sessionListRefresh');

      // Clear messages pane if the deleted session (or a deleted child) was active.
      if (window._activeSessionId === sessionId || childCount > 0) {
        const messages = document.getElementById('chat-messages');
        if (messages) {
          messages.innerHTML =
            '<div id="chat-welcome" class="flex flex-col items-center justify-center h-full text-gray-400">' +
            '<p class="text-lg font-medium">Start a conversation</p>' +
            '<p class="text-sm mt-1">Ask anything or click Explore on a news article</p>' +
            '</div>';
        }
        window._activeSessionId = null;
        const data = _getAppData();
        if (data) data.activeSessionId = null;
        // Restore news panel — nothing is active so the knowledge tree is stale
        htmx.ajax('GET', '/news/partial?category=ai', {
          target: '#right-panel',
          swap: 'innerHTML',
        });
      }
      Toast.success('Session deleted');
    })
    .catch(() => Toast.error('Could not delete session'));
};

// Generate a full-session quiz and open in new tab (used on learn pages without appState).
window.generateQuizForSession = function (sessionId, onLoading, onDone) {
  const newTab = window.open('about:blank', '_blank', 'noopener,noreferrer');
  if (onLoading) onLoading(true);
  fetch('/quiz/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
    .then((r) => {
      if (!r.ok) return r.json().then((d) => Promise.reject(d.error || 'Quiz generation failed'));
      return r.json();
    })
    .then((data) => {
      if (newTab) newTab.location.href = '/quiz/' + data.attempt_id;
      if (onLoading) onLoading(false);
      if (onDone) onDone();
    })
    .catch((err) => {
      if (newTab) newTab.close();
      Toast.error(typeof err === 'string' ? err : 'Could not generate quiz');
      if (onLoading) onLoading(false);
    });
};

// Regenerate a learn_more or quiz sub-thread with a fresh LLM response.
window.regenerateSession = function (sessionId, sessionType) {
  if (!window.confirm('Regenerate this sub-thread? The current response will be replaced.')) return;

  Toast.info('Regenerating…');
  fetch(`/sessions/${sessionId}/regenerate`, { method: 'POST' })
    .then((r) => {
      if (!r.ok) return r.json().then((d) => Promise.reject(d.error || 'Regeneration failed'));
      return r.json();
    })
    .then((data) => {
      const sl = document.getElementById('session-list');
      if (sl) htmx.trigger(sl, 'sessionListRefresh');

      if (sessionType === 'quiz' && data.attempt_id) {
        // For quiz sessions, open the new attempt in a new tab
        window.open('/quiz/' + data.attempt_id, '_blank', 'noopener,noreferrer');
      } else {
        // For learn_more sessions, reload messages in the chat pane
        htmx.ajax('GET', `/sessions/${sessionId}/messages/partial`, {
          target: '#chat-messages',
          swap: 'innerHTML',
        });
        window.setActiveSession(sessionId);
      }
      Toast.success('Sub-thread regenerated');
    })
    .catch((err) => Toast.error(typeof err === 'string' ? err : 'Could not regenerate'));
};
