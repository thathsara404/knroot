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

// Auto-inject the active session ID as the expand param on every session-list refresh
// so the tree stays expanded to the current session's path after any re-render.
document.body.addEventListener('htmx:configRequest', function (evt) {
  var path = evt.detail.path || '';
  if (path.startsWith('/sessions/partial') && path.indexOf('expand=') === -1 && window._activeSessionId) {
    if (evt.detail.parameters) evt.detail.parameters['expand'] = window._activeSessionId;
  }
});

// Post-settle hooks — runs after Alpine has initialised new DOM nodes.
document.body.addEventListener('htmx:afterSettle', function (evt) {
  const targetId = evt.detail.target && evt.detail.target.id;
  if (targetId === 'session-list') {
    setTimeout(function () { window._reapplyActiveDot && window._reapplyActiveDot(); }, 0);
  }
  if (targetId === 'chat-messages') {
    // Clear quiz view state when non-quiz content is loaded into the chat pane.
    // (If a quiz loaded, its init() will have already dispatched quiz-view-changed.)
    setTimeout(function () {
      if (!evt.detail.target.querySelector('.knr-quiz-root')) {
        const appData = _getAppData();
        if (appData) appData.quizViewState = null;
      }
    }, 0);
  }
});

// Disable Send + Check Knowledge while any HTMX request is loading into #chat-messages.
document.body.addEventListener('htmx:beforeRequest', function (evt) {
  const targetId = evt.detail.target && evt.detail.target.id;
  if (targetId === 'chat-messages') _setContentBusy(true);
  if (targetId === 'right-panel') _setNewsPanelLoading(true);
});
document.body.addEventListener('htmx:afterRequest', function (evt) {
  const targetId = evt.detail.target && evt.detail.target.id;
  if (targetId === 'chat-messages') _setContentBusy(false);
  if (targetId === 'right-panel') _setNewsPanelLoading(false);
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
  var el = document.querySelector('[x-data="appState()"]');
  if (!el) return null;
  return window.Alpine ? window.Alpine.$data(el) : null;
}

function _setContentBusy(val) {
  const data = _getAppData();
  if (data) data.contentBusy = !!val;
}

function _setNewsPanelLoading(val) {
  const data = _getAppData();
  if (data) data.newsPanelLoading = !!val;
}

// Returns true if el has no display:none ancestor up to (not including) container.
function _isSessionLinkVisible(el, container) {
  let node = el.parentElement;
  while (node && node !== container) {
    if (node.style.display === 'none') return false;
    node = node.parentElement;
  }
  return true;
}

// Place the green dot on the active session row, or bubble it to the nearest
// visible ancestor when the active row is inside a collapsed subtree.
window._reapplyActiveDot = function () {
  const list = document.getElementById('session-list');
  if (!list) return;

  // Reset all dots and active row highlights
  list.querySelectorAll('.knr-dot').forEach((dot) => {
    dot.classList.add('hidden');
    dot.classList.remove('bg-green-400', 'bg-green-300');
  });
  list.querySelectorAll('a[data-session-id]').forEach((a) => {
    a.classList.remove('bg-gray-800', 'text-white');
  });

  const id = window._activeSessionId;
  if (!id) return;

  const activeLink = list.querySelector('a[data-session-id="' + id + '"]');
  if (!activeLink) return;

  // Always highlight the exact active row so it lights up when its parent expands
  activeLink.classList.add('bg-gray-800', 'text-white');

  // Decide where to show the dot: exact row (if visible) or nearest visible ancestor
  let targetLink = null;
  if (_isSessionLinkVisible(activeLink, list)) {
    targetLink = activeLink;
  } else {
    // Walk up the DOM through [x-data] session wrappers until we find a visible row
    let node = activeLink.parentElement;
    while (node && node !== list) {
      if (node.hasAttribute && node.hasAttribute('x-data')) {
        const rowLink = node.querySelector(':scope > div > a[data-session-id]');
        if (rowLink && _isSessionLinkVisible(rowLink, list)) {
          targetLink = rowLink;
          break;
        }
      }
      node = node.parentElement;
    }
  }

  if (targetLink) {
    const dot = targetLink.querySelector('.knr-dot');
    if (dot) {
      dot.classList.remove('hidden');
      // Bright green on the exact row, softer green when bubbled to an ancestor
      dot.classList.add(targetLink === activeLink ? 'bg-green-400' : 'bg-green-300');
    }
  }
};

// =============================================================================
// Alpine component: newsCardState(articleId) — per news-card state
// =============================================================================

function newsCardState(articleId) {
  return {
    exploreLoading: false,
    alreadyExplored: false,
    factChecking: false,

    init() {
      if (!articleId) return;
      try {
        const ids = JSON.parse(localStorage.getItem('knroot_explored') || '[]');
        this.alreadyExplored = ids.includes(articleId);
      } catch (_) {}
    },

    markExplored() {
      this.alreadyExplored = true;
      if (!articleId) return;
      try {
        const ids = JSON.parse(localStorage.getItem('knroot_explored') || '[]');
        if (!ids.includes(articleId)) {
          ids.push(articleId);
          // Cap at 500 entries so localStorage never grows unbounded
          if (ids.length > 500) ids.splice(0, ids.length - 500);
          localStorage.setItem('knroot_explored', JSON.stringify(ids));
        }
      } catch (_) {}
    },
  };
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
    contentBusy: false,
    newsPanelLoading: false,
    quizViewState: null,  // { isQuiz, attemptId, quizSessionId, parentSessionId, submitted, score }
    sidebarWidth: parseInt(localStorage.getItem('knroot_sidebar_w') || '256'),
    rightPanelWidth: parseInt(localStorage.getItem('knroot_right_w') || '320'),
    mobileBottomHeight: parseInt(localStorage.getItem('knroot_mobile_bottom_h') || '160'),
    isPanelDragging: false,
    activeTab: 'root',
    pendingFollowCount: 0,
    newWallPosts: 0,
    shareModal: { open: false, sessionId: null, visibility: 'public', description: '', loading: false },

    // Panel visibility — always resets to default on page refresh (no localStorage).
    showChat: true,
    showNews: true,
    showWallPublic: true,
    showWallPrivate: true,
    showProfileMain: true,
    showProfileScore: true,
    isMobile: window.innerWidth < 768,

    centerPanelVisible() {
      if (this.activeTab === 'root')    return this.showChat;
      if (this.activeTab === 'wall')    return this.showWallPublic;
      if (this.activeTab === 'profile') return this.showProfileMain;
      return true;
    },

    rightPanelVisible() {
      if (this.activeTab === 'root')    return this.showNews;
      if (this.activeTab === 'wall')    return this.showWallPrivate;
      if (this.activeTab === 'profile') return this.showProfileScore;
      return true;
    },

    togglePanel(panel) {
      this[panel] = !this[panel];
    },

    switchTab(tab) {
      this.activeTab = tab;
      // Open / close the SSE stream alongside the tab — only the wall needs live events.
      if (tab === 'wall') {
        this.newWallPosts = 0;
        window.wallInitSSE && window.wallInitSSE();
      } else {
        window.wallDestroySSE && window.wallDestroySSE();
      }
      if (tab === 'wall') {
        htmx.ajax('GET', '/wall/public/partial', { target: '#chat-messages', swap: 'innerHTML' });
        htmx.ajax('GET', '/wall/private/partial', { target: '#right-panel', swap: 'innerHTML' });
      } else if (tab === 'profile') {
        htmx.ajax('GET', '/wall/profile/partial', { target: '#chat-messages', swap: 'innerHTML' });
        htmx.ajax('GET', '/wall/score/partial', { target: '#right-panel', swap: 'innerHTML' });
        var self = this;
        fetch('/wall/follow-requests/count')
          .then(function(r) { return r.json(); })
          .then(function(d) { self.pendingFollowCount = d.count || 0; })
          .catch(function() {});
      } else if (tab === 'root') {
        htmx.ajax('GET', '/news/partial?category=ai', { target: '#right-panel', swap: 'innerHTML' });
        if (this.activeSessionId) {
          htmx.ajax('GET', '/sessions/' + this.activeSessionId + '/messages/partial',
                    { target: '#chat-messages', swap: 'innerHTML' });
        } else {
          const messages = document.getElementById('chat-messages');
          if (messages) {
            messages.innerHTML =
              '<div id="chat-welcome" class="flex flex-col items-center justify-center h-full text-gray-400">' +
              '<p class="text-lg font-medium">Start a conversation</p>' +
              '<p class="text-sm mt-1">Ask anything or click Explore on a news article</p>' +
              '</div>';
          }
        }
      }
    },

    submitShare() {
      if (!this.shareModal.sessionId) return;
      this.shareModal.loading = true;
      fetch('/wall/shares', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.shareModal.sessionId,
          visibility: this.shareModal.visibility,
          description: this.shareModal.description,
        }),
      })
        .then((r) => { if (!r.ok) return r.json().then((d) => Promise.reject(d.error || 'Share failed')); return r.json(); })
        .then(() => {
          this.shareModal.open = false;
          this.shareModal.description = '';
          Toast.success('Shared to your wall!');
          // Reload both walls so own post appears immediately without banner
          if (this.activeTab === 'wall') {
            this.newWallPosts = 0;
            htmx.ajax('GET', '/wall/public/partial', { target: '#chat-messages', swap: 'innerHTML' });
            htmx.ajax('GET', '/wall/private/partial', { target: '#right-panel', swap: 'innerHTML' });
          }
        })
        .catch((err) => Toast.error(typeof err === 'string' ? err : 'Could not share'))
        .finally(() => { this.shareModal.loading = false; });
    },

    init() {
      const saved = localStorage.getItem('knroot_sidebar');
      if (saved !== null) this.sidebarOpen = saved === 'true';
      this.$watch('sidebarOpen', (v) => localStorage.setItem('knroot_sidebar', v));
      this.$watch('sidebarWidth', (v) => localStorage.setItem('knroot_sidebar_w', String(v)));
      this.$watch('rightPanelWidth', (v) => localStorage.setItem('knroot_right_w', String(v)));
      this.$watch('mobileBottomHeight', (v) => localStorage.setItem('knroot_mobile_bottom_h', String(v)));
      // Release any in-progress drag on mouseup / touchend regardless of where it ends
      const endDrag = () => {
        this.isPanelDragging = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
      window.addEventListener('mouseup', endDrag);
      window.addEventListener('touchend', endDrag);
      window.addEventListener('resize', () => {
        this.isMobile = window.innerWidth < 768;
      });
      window.addEventListener('quiz-view-changed', (e) => {
        this.quizViewState = e.detail.isQuiz ? e.detail : null;
      });
      // Desktop horizontal drag
      window.addEventListener('mousemove', (e) => {
        if (!this.isPanelDragging || this._dragSide === 'bottom') return;
        const container = document.querySelector('[x-data="appState()"]');
        if (this._dragSide === 'left') {
          const ox = container ? container.getBoundingClientRect().left : 0;
          this.sidebarWidth = Math.max(180, Math.min(480, e.clientX - ox));
        } else {
          const right = container ? container.getBoundingClientRect().right : window.innerWidth;
          this.rightPanelWidth = Math.max(200, Math.min(600, right - e.clientX));
        }
      });
      // Mobile vertical drag — mouse
      window.addEventListener('mousemove', (e) => {
        if (!this.isPanelDragging || this._dragSide !== 'bottom') return;
        this._applyMobileDrag(e.clientY);
      });
      // Mobile vertical drag — touch
      window.addEventListener('touchmove', (e) => {
        if (!this.isPanelDragging || this._dragSide !== 'bottom') return;
        e.preventDefault();
        this._applyMobileDrag(e.touches[0].clientY);
      }, { passive: false });
    },

    _applyMobileDrag(clientY) {
      const wrapper = document.getElementById('mobile-content-wrapper');
      if (!wrapper) return;
      const rect = wrapper.getBoundingClientRect();
      // Height = distance from drag point to bottom of wrapper; clamp 80–70% of wrapper
      const maxH = Math.floor(rect.height * 0.7);
      const h = Math.max(80, Math.min(maxH, rect.bottom - clientY));
      this.mobileBottomHeight = h;
    },

    startResize(event, side) {
      this.isPanelDragging = true;
      this._dragSide = side;
      if (side === 'bottom') {
        document.body.style.userSelect = 'none';
      } else {
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
      }
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
      if (this.quizViewState && this.quizViewState.submitted) {
        // Active view is a completed quiz — generate a targeted follow-up
        const parentId = this.quizViewState.parentSessionId;
        generateFollowupQuiz(
          this.quizViewState.attemptId,
          parentId,
          (v) => { this.quizLoading = v; },
          () => {
            const sl = document.getElementById('session-list');
            if (sl) htmx.ajax('GET', `/sessions/partial?expand=${parentId || sessionId}`, { target: sl, swap: 'innerHTML' });
          },
        );
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

  // Update sidebar dot and active-row highlight
  window._reapplyActiveDot && window._reapplyActiveDot();

  // Switch right panel to topic-relevant news for the active session.
  htmx.ajax('GET', `/news/topic-partial?session_id=${sessionId}`, {
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
  _setContentBusy(true);
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
      _setContentBusy(false);
      if (messages) {
        messages.innerHTML =
          '<div class="text-center py-10 text-gray-400 text-sm">' +
          'Could not load exploration. Please try again.</div>';
      }
      Toast.error('Could not load exploration');
      if (callback) callback(false);
    });
};

// Generate a quiz scoped to a specific section and load it inline in the chat pane.
window.generateSectionQuiz = function (sessionId, sectionTitle, sectionContent, btn, callback) {
  _setContentBusy(true);
  if (btn) btn.disabled = true;
  const messages = document.getElementById('chat-messages');
  if (messages) {
    messages.innerHTML =
      '<div class="flex items-center justify-center h-full">' +
        '<div class="text-center space-y-3 text-gray-400">' +
          '<svg class="animate-spin w-8 h-8 mx-auto text-purple-500" fill="none" viewBox="0 0 24 24">' +
            '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>' +
            '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>' +
          '</svg>' +
          '<p class="text-sm">Generating quiz…</p>' +
        '</div>' +
      '</div>';
  }

  fetch('/quiz/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, section_title: sectionTitle, section_content: sectionContent }),
  })
    .then((r) => {
      if (!r.ok) return r.json().then((d) => Promise.reject(d.error || 'Quiz generation failed'));
      return r.json();
    })
    .then((data) => {
      htmx.ajax('GET', '/quiz/' + data.attempt_id + '/partial', { target: '#chat-messages', swap: 'innerHTML' });
      if (data.quiz_session_id) window.setActiveSession(data.quiz_session_id);
      const sl = document.getElementById('session-list');
      if (sl) htmx.ajax('GET', `/sessions/partial?expand=${sessionId}`, { target: sl, swap: 'innerHTML' });
      if (callback) callback(true);
    })
    .catch((err) => {
      _setContentBusy(false);
      if (messages) messages.innerHTML = '<div class="text-center py-10 text-gray-400 text-sm">Could not generate quiz. Please try again.</div>';
      Toast.error(typeof err === 'string' ? err : 'Could not generate quiz');
      if (btn) btn.disabled = false;
      if (callback) callback(false);
    });
};

// Fire a background news-discuss request without touching #chat-messages or setting contentBusy.
// The new session is created silently; the sidebar refreshes and a toast guides the user.
window.discussArticle = function (dataset, callback) {
  fetch('/news/discuss', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      article_id: dataset.articleId || '',
      article_title: dataset.articleTitle || '',
      article_summary: dataset.articleSummary || '',
      article_link: dataset.articleLink || '',
      source_category: dataset.sourceCategory || 'ai',
    }),
  })
    .then(function (r) {
      if (!r.ok) throw new Error('discuss failed');
      return r.json();
    })
    .then(function () {
      const sl = document.getElementById('session-list');
      if (sl) htmx.trigger(sl, 'sessionListRefresh');
      Toast.success('Exploration ready — click it in the sidebar to open');
      if (callback) callback(true);
    })
    .catch(function () {
      Toast.error('Could not start exploration');
      if (callback) callback(false);
    });
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
  window.KnrConfirm({
    title: 'Delete session?',
    message: `This will permanently remove the session${extra}. This cannot be undone.`,
    confirmText: 'Delete',
    danger: true,
  }).then(function (ok) {
    if (!ok) return;
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
  });
};

// Generate a full-session quiz and load it inline in the chat pane.
window.generateQuizForSession = function (sessionId, onLoading, onDone) {
  _setContentBusy(true);
  const messages = document.getElementById('chat-messages');
  if (messages) {
    messages.innerHTML =
      '<div class="flex items-center justify-center h-full">' +
        '<div class="text-center space-y-3 text-gray-400">' +
          '<svg class="animate-spin w-8 h-8 mx-auto text-purple-500" fill="none" viewBox="0 0 24 24">' +
            '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>' +
            '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>' +
          '</svg>' +
          '<p class="text-sm">Generating quiz…</p>' +
        '</div>' +
      '</div>';
  }
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
      htmx.ajax('GET', '/quiz/' + data.attempt_id + '/partial', { target: '#chat-messages', swap: 'innerHTML' });
      if (data.quiz_session_id) window.setActiveSession(data.quiz_session_id);
      const sl = document.getElementById('session-list');
      if (sl) htmx.ajax('GET', `/sessions/partial?expand=${sessionId}`, { target: sl, swap: 'innerHTML' });
      if (onLoading) onLoading(false);
      if (onDone) onDone();
    })
    .catch((err) => {
      _setContentBusy(false);
      if (messages) messages.innerHTML = '<div class="text-center py-10 text-gray-400 text-sm">Could not generate quiz. Please try again.</div>';
      Toast.error(typeof err === 'string' ? err : 'Could not generate quiz');
      if (onLoading) onLoading(false);
    });
};

// Generate a follow-up quiz targeting weak areas from a completed attempt.
window.generateFollowupQuiz = function (attemptId, parentSessionId, onLoading, onDone) {
  _setContentBusy(true);
  const messages = document.getElementById('chat-messages');
  if (messages) {
    messages.innerHTML =
      '<div class="flex items-center justify-center h-full">' +
        '<div class="text-center space-y-3 text-gray-400">' +
          '<svg class="animate-spin w-8 h-8 mx-auto text-purple-500" fill="none" viewBox="0 0 24 24">' +
            '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>' +
            '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>' +
          '</svg>' +
          '<p class="text-sm">Generating follow-up quiz…</p>' +
        '</div>' +
      '</div>';
  }
  if (onLoading) onLoading(true);
  fetch('/quiz/generate-followup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ attempt_id: attemptId }),
  })
    .then((r) => {
      if (!r.ok) return r.json().then((d) => Promise.reject(d.error || 'Follow-up quiz generation failed'));
      return r.json();
    })
    .then((data) => {
      htmx.ajax('GET', '/quiz/' + data.attempt_id + '/partial', { target: '#chat-messages', swap: 'innerHTML' });
      if (data.quiz_session_id) window.setActiveSession(data.quiz_session_id);
      const sl = document.getElementById('session-list');
      const expandId = parentSessionId || data.session_id;
      if (sl && expandId) htmx.ajax('GET', `/sessions/partial?expand=${expandId}`, { target: sl, swap: 'innerHTML' });
      if (onLoading) onLoading(false);
      if (onDone) onDone();
    })
    .catch((err) => {
      _setContentBusy(false);
      if (messages) messages.innerHTML = '<div class="text-center py-10 text-gray-400 text-sm">Could not generate follow-up quiz. Please try again.</div>';
      Toast.error(typeof err === 'string' ? err : 'Could not generate follow-up quiz');
      if (onLoading) onLoading(false);
    });
};

// Regenerate a learn_more or quiz sub-thread with a fresh LLM response.
window.regenerateSession = function (sessionId, sessionType) {
  window.KnrConfirm({
    title: 'Regenerate response?',
    message: 'The current response will be permanently replaced with a fresh one.',
    confirmText: 'Regenerate',
    danger: false,
  }).then(function (ok) {
    if (!ok) return;
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
  });
};

// =============================================================================
// Wall — vote, comment, follow helpers
// =============================================================================

window.shareSession = function (sessionId) {
  const data = window._getAppData ? _getAppData() : null;
  if (!data) return;
  data.shareModal.sessionId = sessionId;
  data.shareModal.visibility = 'public';
  data.shareModal.description = '';
  data.shareModal.open = true;
};

window.wallVote = function (shareId, vote, component) {
  // vote: 1 | -1
  // If clicking the same vote again, remove it (toggle to 0)
  var newVote = component.myVote === vote ? 0 : vote;
  fetch('/wall/shares/' + shareId + '/vote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vote: newVote }),
  })
    .then(function (r) { if (!r.ok) throw new Error('Vote failed'); return r.json(); })
    .then(function (data) {
      component.myVote = data.my_vote;
      component.upvotes = data.upvotes;
      component.downvotes = data.downvotes;
    })
    .catch(function () { Toast.error('Could not record vote'); });
};

window.wallLoadComments = function (shareId, component) {
  fetch('/wall/shares/' + shareId + '/comments')
    .then(function (r) { return r.json(); })
    .then(function (data) { component.comments = data; })
    .catch(function () {});
};

window.wallPostComment = function (shareId, content, component, parentCommentId) {
  if (!content || !content.trim()) return;
  component.submitting = true;
  var body = { content: content };
  if (parentCommentId) body.parent_comment_id = parentCommentId;
  fetch('/wall/shares/' + shareId + '/comments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
    .then(function (r) { if (!r.ok) throw new Error('Comment failed'); return r.json(); })
    .then(function (comment) {
      // SSE may have already pushed this comment (arrived before HTTP response)
      var alreadyPushed = component.comments.some(function (c) { return c.id === comment.id; });
      if (!alreadyPushed) {
        component.comments.push(comment);
        component.commentCount = (component.commentCount || 0) + 1;
      }
      component.commentText = '';
      component.replyingTo = null;
      component.replyText = '';
    })
    .catch(function () { Toast.error('Could not post comment'); })
    .finally(function () { component.submitting = false; });
};

window.wallDeleteComment = function (commentId, component) {
  fetch('/wall/comments/' + commentId, { method: 'DELETE' })
    .then(function (r) { if (!r.ok) throw new Error('Delete failed'); })
    .then(function () {
      // Remove the comment and any replies to it; decrement count accordingly.
      // SSE comment_deleted will sync other visible cards on this page.
      var removed = component.comments.filter(function (c) {
        return c.id === commentId || c.parent_comment_id === commentId;
      }).length;
      component.comments = component.comments.filter(function (c) {
        return c.id !== commentId && c.parent_comment_id !== commentId;
      });
      component.commentCount = Math.max(0, (component.commentCount || 0) - removed);
    })
    .catch(function () { Toast.error('Could not delete comment'); });
};

window.wallFollow = function (userId, component) {
  var method = component.isFollowing ? 'DELETE' : 'POST';
  fetch('/wall/follow/' + userId, { method: method })
    .then(function (r) { if (!r.ok) throw new Error('Follow failed'); })
    .then(function () { component.isFollowing = !component.isFollowing; })
    .catch(function () { Toast.error('Could not update follow status'); });
};

// Alpine component for preview quiz (ephemeral, no server save)
function previewQuizState() {
  return {
    questions: [],
    answers: {},
    submitted: false,
    score: 0,
    init() {
      const el = document.getElementById('preview-qdata');
      if (el) {
        try { this.questions = JSON.parse(el.textContent); } catch (_) {}
      }
    },
    submitPreviewQuiz() {
      var s = 0;
      for (var i = 0; i < this.questions.length; i++) {
        if (this.answers[i] === this.questions[i].correct) s++;
      }
      this.score = s;
      this.submitted = true;
    },
  };
}

window.wallOpenPreview = function (shareId) {
  var portal = document.getElementById('share-preview-portal');
  if (!portal) return;
  htmx.ajax('GET', '/wall/shares/' + shareId + '/preview/partial', {
    target: '#share-preview-portal',
    swap: 'innerHTML',
  });
};

// Follow / unfollow / cancel — updates Alpine followStatus on the card.
window.wallFollowAction = function (userId, action, componentData) {
  if (action === 'follow') {
    fetch('/wall/follow/' + userId, { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        componentData.followStatus = d.status === 'self' ? null : d.status;
        if (d.status === 'pending') Toast.success('Follow request sent');
        else if (d.status === 'accepted') Toast.success('Now following');
      })
      .catch(function () { Toast.error('Could not send follow request'); });
  } else {
    fetch('/wall/follow/' + userId, { method: 'DELETE' })
      .then(function (r) {
        if (r.ok) {
          componentData.followStatus = null;
          Toast.success(action === 'cancel' ? 'Follow request cancelled' : 'Unfollowed');
        } else {
          Toast.error('Action failed');
        }
      })
      .catch(function () { Toast.error('Action failed'); });
  }
};

// Accept or reject an incoming follow request (called from profile_main.html).
window.wallRespondToFollowRequest = function (requesterId, action, btn) {
  var row = document.getElementById('follow-req-' + requesterId);
  fetch('/wall/follow-requests/' + requesterId + '/' + action, { method: 'POST' })
    .then(function (r) {
      if (!r.ok) throw new Error('Failed');
      if (row) row.remove();
      // Decrement badge in the bottom nav
      var appData = window._getAppData && window._getAppData();
      if (appData && appData.pendingFollowCount > 0) appData.pendingFollowCount--;
      Toast.success(action === 'accept' ? 'Follow request accepted' : 'Request declined');
      // Reload profile so follower count updates
      htmx.ajax('GET', '/wall/profile/partial', { target: '#chat-messages', swap: 'innerHTML' });
    })
    .catch(function () { Toast.error('Could not process request'); });
};

// Save a public wall post to the viewer's private wall (or unsave if already saved).
window.wallSaveToWall = function (shareId, component) {
  var alreadySaved = component.savedToWall;
  var method = alreadySaved ? 'DELETE' : 'POST';
  fetch('/wall/shares/' + shareId + '/save', { method: method })
    .then(function (r) {
      if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Failed'); });
    })
    .then(function () {
      if (alreadySaved) {
        component.savedToWall = false;
        htmx.ajax('GET', '/wall/private/partial', { target: '#right-panel', swap: 'innerHTML' });
        Toast.success('Removed from your wall');
      } else {
        component.savedToWall = true;
        Toast.success('Saved to your wall');
        // Immediately refresh My Wall so the saved post appears in the right pane.
        // Only do this while on the Wall tab (right pane belongs to My Wall there).
        var appData = window._getAppData && window._getAppData();
        if (appData && appData.activeTab === 'wall') {
          htmx.ajax('GET', '/wall/private/partial', { target: '#right-panel', swap: 'innerHTML' });
        }
      }
    })
    .catch(function (err) { Toast.error(err.message || 'Could not update wall'); });
};

window.wallImport = function (shareId, component) {
  component.importLoading = true;
  fetch('/wall/shares/' + shareId + '/import', { method: 'POST' })
    .then(function (r) {
      if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Import failed'); });
      return r.json();
    })
    .then(function () {
      component.importDone = true;
      Toast.success('Imported! Find it in your Root section.');
      var sl = document.getElementById('session-list');
      if (sl) htmx.trigger(sl, 'sessionListRefresh');
    })
    .catch(function (err) {
      Toast.error(err.message || 'Could not import');
    })
    .finally(function () { component.importLoading = false; });
};

// Show a confirmation dialog then import if user confirms.
window.wallImportWithConfirm = function (shareId, component) {
  window.KnrConfirm({
    title: 'Import to your Root?',
    message: 'This copies the entire knowledge tree into your Root section. You can then explore, expand, and share it with the community.',
    confirmText: 'Import',
    danger: false,
  }).then(function (ok) {
    if (!ok) return;
    window.wallImport(shareId, component);
  });
};

// =============================================================================
// SSE — real-time wall updates (comments, follow requests, follow accepts)
// =============================================================================

window.wallInitSSE = function () {
  if (window._wallSSE) return;
  var es = new EventSource('/events/stream');

  es.addEventListener('comment_added', function (e) {
    var data = JSON.parse(e.data);
    window.wallHandleNewComment && window.wallHandleNewComment(data);
  });

  es.addEventListener('follow_request_received', function (e) {
    var appData = window._getAppData && window._getAppData();
    if (appData) appData.pendingFollowCount = (appData.pendingFollowCount || 0) + 1;
  });

  es.addEventListener('follow_accepted', function (e) {
    var data = JSON.parse(e.data);
    window.wallHandleFollowAccepted && window.wallHandleFollowAccepted(data.accepted_by.id);
  });

  es.addEventListener('vote_updated', function (e) {
    var data = JSON.parse(e.data);
    window.wallHandleVoteUpdated && window.wallHandleVoteUpdated(data);
  });

  es.addEventListener('share_created', function (e) {
    var data = JSON.parse(e.data);
    // Don't notify for own shares — submitShare already reloads the wall
    if (window._currentUserId && data.user_id === window._currentUserId) return;
    var appData = window._getAppData && window._getAppData();
    if (appData) appData.newWallPosts = (appData.newWallPosts || 0) + 1;
  });

  es.addEventListener('comment_deleted', function (e) {
    var data = JSON.parse(e.data);
    window.wallHandleCommentDeleted && window.wallHandleCommentDeleted(data);
  });

  es.onerror = function () { es.close(); window._wallSSE = null; };
  window._wallSSE = es;
};

window.wallDestroySSE = function () {
  if (window._wallSSE) { window._wallSSE.close(); window._wallSSE = null; }
};

window.wallHandleNewComment = function (data) {
  document.querySelectorAll('[data-share-id="' + data.share_id + '"]').forEach(function (card) {
    var component = window.Alpine && window.Alpine.$data(card);
    if (!component) return;
    var alreadyPresent = component.comments.some(function (c) { return c.id === data.comment.id; });
    if (alreadyPresent) return; // poster's own card: already updated by HTTP response
    component.commentCount = (component.commentCount || 0) + 1;
    if (component.commentsOpen) {
      // Section is visible — reload full list so order and nesting are correct.
      window.wallLoadComments(data.share_id, component);
    } else if (component.comments.length > 0) {
      // Section is collapsed but was previously loaded — append so re-opening
      // shows fresh data without a round-trip (toggleComments always re-fetches anyway).
      component.comments = component.comments.concat([data.comment]);
    }
  });
};

window.wallHandleFollowAccepted = function (userId) {
  document.querySelectorAll('[data-author-id="' + userId + '"]').forEach(function (card) {
    var component = window.Alpine && window.Alpine.$data(card);
    if (component) component.followStatus = 'accepted';
  });
};

window.wallHandleVoteUpdated = function (data) {
  document.querySelectorAll('[data-share-id="' + data.share_id + '"]').forEach(function (card) {
    var component = window.Alpine && window.Alpine.$data(card);
    if (!component) return;
    component.upvotes = data.upvotes;
    component.downvotes = data.downvotes;
    // Sync the voter's own vote state across all their visible cards for this share
    if (window._currentUserId && data.voter_user_id === window._currentUserId) {
      component.myVote = data.my_vote;
    }
  });
};

window.wallHandleCommentDeleted = function (data) {
  document.querySelectorAll('[data-share-id="' + data.share_id + '"]').forEach(function (card) {
    var component = window.Alpine && window.Alpine.$data(card);
    if (!component) return;
    // Count how many entries will be removed (comment + its replies, cascaded by DB)
    var removed = component.comments.filter(function (c) {
      return c.id === data.comment_id || c.parent_comment_id === data.comment_id;
    }).length;
    if (removed === 0) return;
    component.comments = component.comments.filter(function (c) {
      return c.id !== data.comment_id && c.parent_comment_id !== data.comment_id;
    });
    component.commentCount = Math.max(0, (component.commentCount || 0) - removed);
  });
};
