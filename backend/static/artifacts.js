// Shared artifact renderer — KaTeX formulas, Mermaid diagrams, Chart.js charts.
// Runs on DOMContentLoaded and re-runs after every HTMX swap via htmx:afterSettle.
// Artifacts inside collapsed toggles are lazily initialised on first open via
// window.initArtifacts($refs.panel) called from the Alpine @click handler.

(function () {
  'use strict';

  // Indigo-first palette matching the app's colour scheme
  const CHART_PALETTE = [
    { border: '#6366f1', bg: 'rgba(99,102,241,0.15)' },
    { border: '#f59e0b', bg: 'rgba(245,158,11,0.15)' },
    { border: '#10b981', bg: 'rgba(16,185,129,0.15)' },
    { border: '#ef4444', bg: 'rgba(239,68,68,0.15)' },
  ];

  // ── Mermaid ────────────────────────────────────────────────────────────────

  let _mermaidReady = false;

  function _ensureMermaid() {
    if (_mermaidReady || typeof mermaid === 'undefined') return;
    mermaid.initialize({
      startOnLoad: false,
      theme: 'base',
      themeVariables: {
        primaryColor: '#6366f1',
        primaryTextColor: '#ffffff',
        primaryBorderColor: '#4f46e5',
        lineColor: '#6366f1',
        secondaryColor: '#f5f3ff',
        tertiaryColor: '#ede9fe',
        fontFamily: 'ui-sans-serif, system-ui, sans-serif',
        fontSize: '13px',
      },
      flowchart: { useMaxWidth: true, curve: 'basis', htmlLabels: true },
      // loose needed so SVG nodes can receive JS click events
      securityLevel: 'loose',
    });
    _mermaidReady = true;
  }

  async function _initMermaid(container) {
    // Step 1 — materialise wrapper divs into live .mermaid elements using
    // textContent (not innerHTML) so no XSS risk from LLM-generated definitions.
    container.querySelectorAll('.mermaid-wrapper:not([data-processed])').forEach(wrapper => {
      const def = wrapper.getAttribute('data-mermaid');
      if (!def) return;
      const div = document.createElement('div');
      div.className = 'mermaid';
      if (wrapper.classList.contains('hierarchy-diagram-wrapper')) {
        div.classList.add('hierarchy-diagram');
      }
      div.textContent = def;
      wrapper.appendChild(div);
      wrapper.setAttribute('data-processed', 'true');
    });

    const nodes = Array.from(container.querySelectorAll('.mermaid:not([data-mermaid-done])'));
    if (!nodes.length) return;

    _ensureMermaid();
    if (typeof mermaid === 'undefined') return;

    nodes.forEach(n => n.setAttribute('data-mermaid-done', 'true'));
    try {
      await mermaid.run({ nodes });
      // Wire click-to-scroll on hierarchy diagrams after render completes
      nodes.forEach(n => {
        if (n.classList.contains('hierarchy-diagram')) _wireHierarchyClicks(n);
      });
    } catch (e) {
      console.warn('[artifacts] Mermaid render error:', e);
    }
  }

  function _wireHierarchyClicks(diagramEl) {
    // Walk up to the message container that owns both the diagram and the section cards
    const msgContainer = diagramEl.closest('.ai-message-container');
    if (!msgContainer) return;

    // Build label → card map from section data attributes
    const sectionMap = {};
    msgContainer.querySelectorAll('[data-section-title]').forEach(card => {
      const title = card.getAttribute('data-section-title');
      if (title) sectionMap[title] = card;
    });

    // Small delay — Mermaid finishes SVG painting asynchronously after run()
    setTimeout(() => {
      diagramEl.querySelectorAll('.node').forEach(node => {
        // Mermaid renders labels inside various elements depending on shape/theme
        const labelEl = node.querySelector('.label span, .nodeLabel, .label');
        const label = labelEl ? labelEl.textContent.trim() : '';
        const target = sectionMap[label];
        if (!target) return;

        node.style.cursor = 'pointer';
        node.setAttribute('title', `Jump to: ${label}`);
        node.addEventListener('click', () => {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          // Brief ring pulse to confirm the navigation
          target.classList.add('ring-2', 'ring-indigo-400', 'ring-offset-1');
          setTimeout(() => target.classList.remove('ring-2', 'ring-indigo-400', 'ring-offset-1'), 1400);
        });
      });
    }, 180);
  }

  // ── KaTeX ──────────────────────────────────────────────────────────────────

  function _initKaTeX(container) {
    // Auto-render $...$ and $$...$$ inside section content / key-point text
    if (typeof renderMathInElement !== 'undefined') {
      container.querySelectorAll('.katex-render:not([data-katex-done])').forEach(el => {
        el.setAttribute('data-katex-done', 'true');
        renderMathInElement(el, {
          delimiters: [
            { left: '$$', right: '$$', display: true },
            { left: '$',  right: '$',  display: false },
          ],
          throwOnError: false,
        });
      });
    }

    // Block formula artifacts rendered via katex.render()
    if (typeof katex !== 'undefined') {
      container.querySelectorAll('.katex-block:not([data-katex-done])').forEach(el => {
        el.setAttribute('data-katex-done', 'true');
        const latex = el.getAttribute('data-latex');
        if (!latex) return;
        try {
          katex.render(latex, el, { displayMode: true, throwOnError: false });
        } catch (_) {
          // Fallback: show raw LaTeX so the content is not silently lost
          el.textContent = latex;
        }
      });
    }
  }

  // ── Chart.js ───────────────────────────────────────────────────────────────

  function _buildChartConfig(spec) {
    const isPolar = ['pie', 'doughnut'].includes(spec.chart_type);
    const datasets = (spec.datasets || []).map((ds, i) => {
      const p = CHART_PALETTE[i % CHART_PALETTE.length];
      return {
        label:           ds.label || '',
        data:            ds.data  || [],
        borderColor:     isPolar ? CHART_PALETTE.map(c => c.border) : p.border,
        backgroundColor: isPolar ? CHART_PALETTE.map(c => c.bg)     : p.bg,
        borderWidth: 2,
        tension:     0.4,
        pointRadius: 3,
        fill: spec.chart_type === 'line',
      };
    });

    return {
      type: spec.chart_type || 'bar',
      data: { labels: spec.labels || [], datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: datasets.length > 1,
            labels: { font: { size: 11 }, boxWidth: 12 },
          },
          title: spec.title
            ? { display: true, text: spec.title, font: { size: 12, weight: '500' }, padding: { bottom: 10 } }
            : { display: false },
        },
        scales: isPolar ? {} : {
          x: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { font: { size: 11 } } },
          y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { font: { size: 11 } } },
        },
      },
    };
  }

  function _initCharts(container) {
    if (typeof Chart === 'undefined') return;
    container.querySelectorAll('canvas.artifact-chart:not([data-chart-done])').forEach(canvas => {
      canvas.setAttribute('data-chart-done', 'true');
      const specStr = canvas.getAttribute('data-chart-spec');
      if (!specStr) return;
      try {
        const spec = JSON.parse(specStr);
        new Chart(canvas, _buildChartConfig(spec));
      } catch (e) {
        console.warn('[artifacts] Chart.js init failed:', e);
      }
    });
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  async function initArtifacts(container) {
    const el = (container instanceof Element || container instanceof Document)
      ? container
      : document;
    await _initMermaid(el);
    _initKaTeX(el);
    _initCharts(el);
  }

  // Initial load
  document.addEventListener('DOMContentLoaded', () => initArtifacts(document));

  // After every HTMX swap (chat responses, wall preview modal lazy-loads, etc.)
  document.addEventListener('htmx:afterSettle', evt => initArtifacts(evt.detail.elt));

  // Exposed so Alpine @click handlers can trigger lazy init on reveal
  window.initArtifacts = initArtifacts;
})();
