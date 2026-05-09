// quiz.js — Alpine components for quiz (full page + inline in chat pane)

function quizStateInline(scriptId) {
  const raw = JSON.parse(document.getElementById(scriptId).textContent);
  const state = quizState(
    raw.questions, raw.attempt_id,
    raw.answers || {}, raw.completed || false, raw.score || 0,
    raw.quiz_session_id || '', raw.session_id || '',
  );
  state.inline = true;
  return state;
}

function quizStateFullPage(scriptId) {
  const raw = JSON.parse(document.getElementById(scriptId).textContent);
  // inline stays false — retryQuiz() navigates via window.location.href
  return quizState(
    raw.questions, raw.attempt_id,
    raw.answers || {}, raw.completed || false, raw.score || 0,
    raw.quiz_session_id || '', raw.session_id || '',
  );
}

function quizState(questions, attemptId, savedAnswers, alreadyCompleted, savedScore, quizSessionId, parentSessionId) {
  return {
    questions: questions,
    attemptId: attemptId,
    quizSessionId: quizSessionId || '',
    parentSessionId: parentSessionId || '',
    answers: savedAnswers || {},
    submitted: alreadyCompleted || false,
    score: savedScore || 0,
    loading: false,
    inline: false,
    saveTimeout: null,
    relearn: {},  // { questionId: { open, loading, explanation, exploreLoading, exploreOpened } }

    _dispatchViewState() {
      window.dispatchEvent(new CustomEvent('quiz-view-changed', {
        detail: {
          isQuiz: true,
          attemptId: this.attemptId,
          quizSessionId: this.quizSessionId,
          parentSessionId: this.parentSessionId,
          submitted: this.submitted,
          score: this.score,
        },
      }));
    },

    init() {
      this._dispatchViewState();
    },

    _panel(questionId) {
      if (!this.relearn[questionId]) {
        this.relearn[questionId] = {
          open: false, loading: false, explanation: '',
          exploreLoading: false, exploreOpened: false,
        };
      }
      return this.relearn[questionId];
    },

    openRelearn(questionId) {
      const panel = this._panel(questionId);
      if (panel.open) return;
      panel.open = true;
      panel.loading = true;
      fetch('/quiz/attempt/' + this.attemptId + '/relearn/' + questionId)
        .then((r) => r.json())
        .then((d) => {
          panel.explanation = d.explanation || 'No explanation available.';
          panel.loading = false;
        })
        .catch(() => {
          panel.explanation = 'Could not load explanation.';
          panel.loading = false;
        });
    },

    exploreRelearn(questionId, questionTopic) {
      if (!this.quizSessionId) {
        window.Toast && Toast.error('Cannot explore: quiz session not found');
        return;
      }
      const panel = this._panel(questionId);
      panel.exploreLoading = true;
      window.exploreSection(
        this.quizSessionId,
        questionTopic || 'quiz question topic',
        null,
        (ok) => {
          panel.exploreLoading = false;
          if (ok) panel.exploreOpened = true;
        },
      );
    },

    selectAnswer(questionId, optionIndex) {
      if (this.submitted) return;
      this.answers[questionId] = optionIndex;
      this.scheduleSave();
    },

    scheduleSave() {
      clearTimeout(this.saveTimeout);
      this.saveTimeout = setTimeout(() => this.autoSave(), 500);
    },

    autoSave() {
      fetch('/quiz/attempt/' + this.attemptId, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: this.answers }),
      }).catch(() => {});
    },

    submitQuiz() {
      clearTimeout(this.saveTimeout);
      this.loading = true;
      fetch('/quiz/attempt/' + this.attemptId, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: this.answers, completed: true }),
      })
        .then((r) => r.json())
        .then((data) => {
          this.score = data.score;
          if (data.questions) this.questions = data.questions;
          this.submitted = true;
          this.loading = false;
          this._dispatchViewState();
          window.scrollTo({ top: 0, behavior: 'smooth' });
        })
        .catch(() => {
          this.loading = false;
          alert('Could not submit. Please try again.');
        });
    },

    retryQuiz() {
      fetch('/quiz/retry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ attempt_id: this.attemptId }),
      })
        .then((r) => r.json())
        .then((data) => {
          if (this.inline) {
            htmx.ajax('GET', '/quiz/' + data.attempt_id + '/partial', {
              target: '#chat-messages',
              swap: 'innerHTML',
            });
          } else {
            window.location.href = '/quiz/' + data.attempt_id;
          }
        })
        .catch(() => alert('Could not create retry. Please try again.'));
    },

    optionClass(questionId, optionIndex, correctIndex) {
      if (!this.submitted) {
        return this.answers[questionId] === optionIndex
          ? 'bg-indigo-50 border-indigo-400 text-indigo-700'
          : 'border-gray-200 text-gray-600 hover:bg-gray-50';
      }
      if (optionIndex === correctIndex) return 'bg-green-50 border-green-400 text-green-700';
      if (this.answers[questionId] === optionIndex) return 'bg-red-50 border-red-300 text-red-600';
      return 'border-gray-200 text-gray-400';
    },
  };
}
