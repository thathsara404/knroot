// quiz.js — Alpine component for the full quiz page (/quiz/<attempt_id>)

function quizState(questions, attemptId, savedAnswers, alreadyCompleted, savedScore) {
  return {
    questions: questions,
    attemptId: attemptId,
    answers: savedAnswers || {},
    submitted: alreadyCompleted || false,
    score: savedScore || 0,
    loading: false,
    saveTimeout: null,

    init() {
      // Completed attempts already have 'correct' field from server — nothing to fetch.
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
          window.location.href = '/quiz/' + data.attempt_id;
        })
        .catch(() => alert('Could not create retry. Please try again.'));
    },

    loadRelearn(questionId, panelData) {
      panelData.loading = true;
      fetch('/quiz/attempt/' + this.attemptId + '/relearn/' + questionId)
        .then((r) => r.json())
        .then((data) => {
          panelData.explanation = data.explanation || 'No explanation available.';
          panelData.loading = false;
        })
        .catch(() => {
          panelData.explanation = 'Could not load explanation.';
          panelData.loading = false;
        });
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
