// static/js/app.js
// AI Code Manager Studio Pro v2 – Frontend Application Logic

(function () {
  'use strict';

  // ---------- State ----------
  const state = {
    currentSessionId: null,
    currentPlan: null,
    generatedFiles: [],
    sessions: [],
    isGenerating: false,
    theme: localStorage.getItem('theme') || 'light',
  };

  // ---------- DOM References ----------
  const DOM = {
    sidebar: document.getElementById('sidebar'),
    sessionsList: document.getElementById('sessions-list'),
    newSessionBtn: document.getElementById('new-session-btn'),
    mainContent: document.getElementById('main-content'),
    projectInput: document.getElementById('project-input'),
    analyzeBtn: document.getElementById('analyze-btn'),
    planArea: document.getElementById('plan-area'),
    planContent: document.getElementById('plan-content'),
    editPlanBtn: document.getElementById('edit-plan-btn'),
    generateBtn: document.getElementById('generate-btn'),
    progressArea: document.getElementById('progress-area'),
    progressBar: document.getElementById('progress-bar'),
    progressMessage: document.getElementById('progress-message'),
    filesArea: document.getElementById('files-area'),
    fileList: document.getElementById('file-list'),
    filePreview: document.getElementById('file-preview'),
    fileContent: document.getElementById('file-content'),
    downloadAllBtn: document.getElementById('download-all-btn'),
    pushBtn: document.getElementById('push-btn'),
    pushModal: document.getElementById('push-modal'),
    pushForm: document.getElementById('push-form'),
    pushCancel: document.getElementById('push-cancel'),
    themeToggle: document.getElementById('theme-toggle'),
    toastContainer: document.getElementById('toast-container'),
  };

  // ---------- Utility Functions ----------
  function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    DOM.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('toast-exit');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  function setLoading(btn, loading) {
    if (loading) {
      btn.disabled = true;
      btn.dataset.originalText = btn.textContent;
      btn.textContent = '...';
    } else {
      btn.disabled = false;
      btn.textContent = btn.dataset.originalText || btn.textContent;
    }
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function formatPlan(plan) {
    // Convert plan object or string to HTML
    if (typeof plan === 'string') {
      return `<pre>${escapeHtml(plan)}</pre>`;
    }
    if (plan && plan.phases) {
      let html = '<div class="plan-phases">';
      plan.phases.forEach((phase, idx) => {
        html += `<div class="plan-phase">
          <h3>Phase ${idx + 1}: ${escapeHtml(phase.name || '')}</h3>
          <ul>`;
        if (phase.tasks) {
          phase.tasks.forEach(task => {
            html += `<li>${escapeHtml(task)}</li>`;
          });
        }
        html += '</ul></div>';
      });
      html += '</div>';
      return html;
    }
    return `<pre>${escapeHtml(JSON.stringify(plan, null, 2))}</pre>`;
  }

  function highlightAll() {
    if (typeof hljs !== 'undefined') {
      document.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
      });
    }
  }

  // ---------- Theme ----------
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    state.theme = theme;
    if (DOM.themeToggle) {
      DOM.themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
  }

  function toggleTheme() {
    applyTheme(state.theme === 'dark' ? 'light' : 'dark');
  }

  // ---------- Session Management ----------
  async function loadSessions() {
    try {
      const res = await fetch('/api/sessions');
      if (!res.ok) throw new Error('Failed to load sessions');
      const data = await res.json();
      state.sessions = data.sessions || [];
      renderSessions();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  function renderSessions() {
    DOM.sessionsList.innerHTML = '';
    state.sessions.forEach(session => {
      const li = document.createElement('li');
      li.className = 'session-item';
      if (session.id === state.currentSessionId) li.classList.add('active');
      li.innerHTML = `
        <span class="session-name">${escapeHtml(session.name || session.id)}</span>
        <button class="session-delete" data-id="${session.id}">×</button>
      `;
      li.addEventListener('click', () => selectSession(session.id));
      li.querySelector('.session-delete').addEventListener('click', (e) => {
        e.stopPropagation();
        deleteSession(session.id);
      });
      DOM.sessionsList.appendChild(li);
    });
  }

  async function createSession() {
    try {
      setLoading(DOM.newSessionBtn, true);
      const res = await fetch('/api/new-session', { method: 'POST' });
      if (!res.ok) throw new Error('Failed to create session');
      const data = await res.json();
      state.sessions.unshift(data.session);
      renderSessions();
      selectSession(data.session.id);
      showToast('New session created', 'success');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setLoading(DOM.newSessionBtn, false);
    }
  }

  async function selectSession(sessionId) {
    if (state.isGenerating) return;
    try {
      state.currentSessionId = sessionId;
      renderSessions();
      // Load session data
      const res = await fetch(`/api/session/${sessionId}`);
      if (!res.ok) throw new Error('Failed to load session');
      const data = await res.json();
      state.currentPlan = data.plan || null;
      state.generatedFiles = data.files || [];
      renderPlan();
      renderFiles();
      DOM.mainContent.classList.remove('empty');
      DOM.mainContent.classList.add('active');
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function deleteSession(sessionId) {
    if (!confirm('Delete this session?')) return;
    try {
      const res = await fetch(`/api/session/${sessionId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete session');
      state.sessions = state.sessions.filter(s => s.id !== sessionId);
      if (state.currentSessionId === sessionId) {
        state.currentSessionId = null;
        state.currentPlan = null;
        state.generatedFiles = [];
        DOM.mainContent.classList.remove('active');
        DOM.mainContent.classList.add('empty');
      }
      renderSessions();
      renderPlan();
      renderFiles();
      showToast('Session deleted', 'info');
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  // ---------- Project Analyze ----------
  async function analyzeProject() {
    const description = DOM.projectInput.value.trim();
    if (!description) {
      showToast('Please enter a project description', 'warning');
      return;
    }
    if (!state.currentSessionId) {
      showToast('Please select or create a session first', 'warning');
      return;
    }
    try {
      setLoading(DOM.analyzeBtn, true);
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.currentSessionId,
          description: description,
        }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || 'Analyze failed');
      }
      const data = await res.json();
      state.currentPlan = data.plan || data;
      renderPlan();
      showToast('Project analyzed successfully', 'success');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setLoading(DOM.analyzeBtn, false);
    }
  }

  function renderPlan() {
    if (!state.currentPlan) {
      DOM.planArea.style.display = 'none';
      DOM.generateBtn.disabled = true;
      return;
    }
    DOM.planArea.style.display = 'block';
    DOM.planContent.innerHTML = formatPlan(state.currentPlan);
    DOM.generateBtn.disabled = false;
    if (typeof hljs !== 'undefined') {
      highlightAll();
    }
  }

  // ---------- Edit Plan ----------
  function enablePlanEditing() {
    if (!state.currentPlan) return;
    // Replace plan content with a textarea containing raw plan (JSON or text)
    const raw = typeof state.currentPlan === 'string'
      ? state.currentPlan
      : JSON.stringify(state.currentPlan, null, 2);
    const textarea = document.createElement('textarea');
    textarea.id = 'plan-editor';
    textarea.value = raw;
    textarea.style.width = '100%';
    textarea.style.minHeight = '300px';
    textarea.style.fontFamily = 'monospace';
    DOM.planContent.innerHTML = '';
    DOM.planContent.appendChild(textarea);
    DOM.editPlanBtn.textContent = 'Save Plan';
    DOM.editPlanBtn.dataset.editing = 'true';
  }

  function savePlanEdit() {
    const textarea = document.getElementById('plan-editor');
    if (!textarea) return;
    const raw = textarea.value;
    try {
      // Try to parse as JSON, otherwise keep as string
      state.currentPlan = JSON.parse(raw);
    } catch {
      state.currentPlan = raw; // keep as plain text
    }
    renderPlan();
    DOM.editPlanBtn.textContent = 'Edit Plan';
    DOM.editPlanBtn.dataset.editing = 'false';
    // Optionally send updated plan to server
    updatePlanOnServer();
  }

  async function updatePlanOnServer() {
    try {
      await fetch(`/api/session/${state.currentSessionId}/plan`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan: state.currentPlan }),
      });
    } catch (err) {
      // silent – local still updated
    }
  }

  // ---------- Code Generation (SSE) ----------
  function startCodeGeneration() {
    if (!state.currentSessionId || !state.currentPlan) {
      showToast('No plan to generate from', 'warning');
      return;
    }
    if (state.isGenerating) return;
    state.isGenerating = true;
    DOM.generateBtn.disabled = true;
    DOM.progressArea.style.display = 'block';
    DOM.progressBar.style.width = '0%';
    DOM.progressMessage.textContent = 'Initializing...';
    DOM.filesArea.style.display = 'none';
    state.generatedFiles = [];

    const eventSource = new EventSource(`/api/generate?session=${state.currentSessionId}`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
          DOM.progressBar.style.width = `${data.percent || 0}%`;
          DOM.progressMessage.textContent = data.message || 'Generating...';
        } else if (data.type === 'file') {
          state.generatedFiles.push({
            name: data.name,
            content: data.content,
            language: data.language || 'plaintext',
          });
          renderFileList();
        } else if (data.type === 'complete') {
          DOM.progressBar.style.width = '100%';
          DOM.progressMessage.textContent = 'Generation complete!';
          DOM.filesArea.style.display = 'block';
          renderFiles();
          eventSource.close();
          state.isGenerating = false;
          DOM.generateBtn.disabled = false;
          showToast('Code generation finished', 'success');
        } else if (data.type === 'error') {
          showToast(data.message, 'error');
          eventSource.close();
          state.isGenerating = false;
          DOM.generateBtn.disabled = false;
          DOM.progressArea.style.display = 'none';
        }
      } catch (err) {
        // ignore malformed
      }
    };

    eventSource.onerror = () => {
      showToast('Connection error – generation may be incomplete', 'error');
      eventSource.close();
      state.isGenerating = false;
      DOM.generateBtn.disabled = false;
      DOM.progressArea.style.display = 'none';
    };
  }

  // ---------- Files ----------
  function renderFileList() {
    DOM.fileList.innerHTML = '';
    state.generatedFiles.forEach((file, index) => {
      const li = document.createElement('li');
      li.className = 'file-item';
      li.textContent = file.name;
      li.dataset.index = index;
      li.addEventListener('click', () => previewFile(index));
      DOM.fileList.appendChild(li);
    });
    if (state.generatedFiles.length > 0) {
      previewFile(0);
    } else {
      DOM.filePreview.style.display = 'none';
    }
  }

  function renderFiles() {
    if (state.generatedFiles.length === 0) {
      DOM.filesArea.style.display = 'none';
      return;
    }
    DOM.filesArea.style.display = 'block';
    renderFileList();
  }

  function previewFile(index) {
    const file = state.generatedFiles[index];
    if (!file) return;
    DOM.filePreview.style.display = 'block';
    DOM.fileContent.innerHTML = `<pre><code class="language-${file.language}">${escapeHtml(file.content)}</code></pre>`;
    // Highlight
    if (typeof hljs !== 'undefined') {
      DOM.fileContent.querySelectorAll('pre code').forEach(block => hljs.highlightElement(block));
    }
    // Set copy and download actions
    DOM.filePreview.dataset.currentIndex = index;
  }

  // ---------- Copy File ----------
  async function copyFileContent(index) {
    const file = state.generatedFiles[index];
    if (!file) return;
    try {
      await navigator.clipboard.writeText(file.content);
      showToast('Copied to clipboard', 'success');
    } catch {
      showToast('Failed to copy', 'error');
    }
  }

  // ---------- Download All (JSZip) ----------
  function downloadAll() {
    if (state.generatedFiles.length === 0) {
      showToast('No files to download', 'warning');
      return;
    }
    if (typeof JSZip === 'undefined') {
      showToast('JSZip library not loaded', 'error');
      return;
    }
    const zip = new JSZip();
    state.generatedFiles.forEach(file => {
      zip.file(file.name, file.content);
    });
    zip.generateAsync({ type: 'blob' }).then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `project_${state.currentSessionId || 'export'}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('Download started', 'success');
    }).catch(() => {
      showToast('Failed to create zip', 'error');
    });
  }

  // ---------- GitHub Push ----------
  function showPushModal() {
    DOM.pushModal.style.display = 'flex';
  }

  function hidePushModal() {
    DOM.pushModal.style.display = 'none';
  }

  async function pushToGitHub(event) {
    event.preventDefault();
    const formData = new FormData(DOM.pushForm);
    const repoUrl = formData.get('repoUrl')?.trim();
    const branch = formData.get('branch')?.trim() || 'main';
    const token = formData.get('token')?.trim();
    if (!repoUrl || !token) {
      showToast('Repository URL and token are required', 'warning');
      return;
    }
    try {
      setLoading(DOM.pushBtn, true);
      const res = await fetch('/api/push', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.currentSessionId,
          repo_url: repoUrl,
          branch: branch,
          token: token,
          files: state.generatedFiles,
        }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || 'Push failed');
      }
      const data = await res.json();
      showToast(`Pushed to GitHub: ${data.commit_url || 'success'}`, 'success');
      hidePushModal();
      DOM.pushForm.reset();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setLoading(DOM.pushBtn, false);
    }
  }

  // ---------- Event Listeners ----------
  function initEventListeners() {
    // Theme toggle
    DOM.themeToggle.addEventListener('click', toggleTheme);

    // New session
    DOM.newSessionBtn.addEventListener('click', createSession);

    // Analyze
    DOM.analyzeBtn.addEventListener('click', analyzeProject);

    // Edit / Save Plan
    DOM.editPlanBtn.addEventListener('click', () => {
      if (DOM.editPlanBtn.dataset.editing === 'true') {
        savePlanEdit();
      } else {
        enablePlanEditing();
      }
    });

    // Generate code
    DOM.generateBtn.addEventListener('click', startCodeGeneration);

    // Copy file (delegated)
    DOM.filePreview.addEventListener('click', (e) => {
      const copyBtn = e.target.closest('.copy-btn');
      if (copyBtn) {
        const index = parseInt(DOM.filePreview.dataset.currentIndex, 10);
        copyFileContent(index);
      }
    });

    // Download all
    DOM.downloadAllBtn.addEventListener('click', downloadAll);

    // Push modal
    DOM.pushBtn.addEventListener('click', showPushModal);
    DOM.pushCancel.addEventListener('click', hidePushModal);
    DOM.pushModal.addEventListener('click', (e) => {
      if (e.target === DOM.pushModal) hidePushModal();
    });
    DOM.pushForm.addEventListener('submit', pushToGitHub);
  }

  // ---------- Initialization ----------
  function init() {
    applyTheme(state.theme);
    initEventListeners();
    loadSessions();

    // If there is a current session from localStorage, try to select it
    const storedSession = localStorage.getItem('currentSessionId');
    if (storedSession) {
      selectSession(storedSession);
    }

    // Show empty state
    DOM.mainContent.classList.add('empty');
  }

  // ---------- Persist current session ----------
  // Update localStorage on session select
  const originalSelect = selectSession;
  selectSession = function (sessionId) {
    localStorage.setItem('currentSessionId', sessionId);
    return originalSelect.call(this, sessionId);
  };

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();