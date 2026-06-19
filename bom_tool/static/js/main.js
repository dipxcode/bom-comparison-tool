'use strict';

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : '';
}

function showToast(message, type = 'info', duration = 4200) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const icons   = { success: '✓', error: '✗', info: 'ℹ', warning: '⚠' };
  const titles  = { success: 'Success', error: 'Error', info: 'Info', warning: 'Warning' };

  const t = document.createElement('div');
  t.className = `bom-toast toast-${type}`;
  t.innerHTML = `
    <span class="toast-icon">${icons[type] || 'ℹ'}</span>
    <div class="toast-body">
      <div class="toast-title">${titles[type]}</div>
      <div class="toast-msg">${message}</div>
    </div>
    <button class="toast-close" onclick="dismissToast(this.parentElement)">✕</button>`;
  container.appendChild(t);

  if (duration > 0) setTimeout(() => dismissToast(t), duration);
}

function dismissToast(el) {
  if (!el || el.classList.contains('hiding')) return;
  el.classList.add('hiding');
  setTimeout(() => el.remove(), 300);
}

function showLoading(msg = 'Processing BOM files…') {
  let ov = document.getElementById('loadingOverlay');
  if (!ov) {
    ov = document.createElement('div');
    ov.id = 'loadingOverlay';
    ov.className = 'loading-overlay';
    ov.innerHTML = `<div class="spinner-ring"></div><p id="loadingMsg"></p>`;
    document.body.appendChild(ov);
  }
  document.getElementById('loadingMsg').textContent = msg;
  ov.classList.add('active');
}

function hideLoading() {
  const ov = document.getElementById('loadingOverlay');
  if (ov) ov.classList.remove('active');
}

function initSidebar() {
  const toggle  = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (!toggle || !sidebar) return;

  function openSidebar() {
    sidebar.classList.add('open');
    if (overlay) overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }
  function closeSidebar() {
    sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
    document.body.style.overflow = '';
  }

  toggle.addEventListener('click', () => {
    sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
  });
  if (overlay) overlay.addEventListener('click', closeSidebar);

  window.addEventListener('resize', () => {
    if (window.innerWidth > 768) closeSidebar();
  });
}

function clearAuthErrors(formId) {
  document.querySelectorAll(`#${formId} .is-invalid`).forEach(el => el.classList.remove('is-invalid'));
  document.querySelectorAll(`#${formId} .invalid-feedback`).forEach(el => {
    el.textContent = ''; el.style.display = 'none';
  });
  const box = document.querySelector(`#${formId}`).closest('.modal-body')?.querySelector('.auth-error-box');
  if (box) { box.style.display = 'none'; box.textContent = ''; }
}

function showAuthErrors(formId, errors) {
  clearAuthErrors(formId);
  const form = document.getElementById(formId);
  const body = form?.closest('.modal-body');
  const box  = body?.querySelector('.auth-error-box');

  const nonField = errors.__all__ || errors.non_field_errors || [];
  if (nonField.length && box) {
    box.textContent = nonField.join(' ');
    box.style.display = 'block';
  }

  Object.entries(errors).forEach(([field, msgs]) => {
    if (field === '__all__' || field === 'non_field_errors') return;
    const input = form?.querySelector(`[name="${field}"]`);
    if (!input) return;
    input.classList.add('is-invalid');
    const fb = input.parentElement.querySelector('.invalid-feedback')
            || input.closest('.col-6, .col-12, .mb-3')?.querySelector('.invalid-feedback');
    if (fb) { fb.textContent = Array.isArray(msgs) ? msgs.join(' ') : msgs; fb.style.display = 'block'; }
  });
}

async function submitAuthForm(formId, url, btnId) {
  const form = document.getElementById(formId);
  const btn  = document.getElementById(btnId);
  if (!form || !btn) return;

  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" style="width:14px;height:14px;border-width:2px;"></span>Please wait…';

  const fd = new FormData(form);
  fd.set('csrfmiddlewaretoken', getCsrf());

  try {
    const res  = await fetch(url, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'XMLHttpRequest' } });
    const data = await res.json();

    if (data.success) {
      showToast(data.message || 'Redirecting…', 'success');
      setTimeout(() => { window.location.href = data.redirect_url; }, 650);
    } else {
      showAuthErrors(formId, data.errors || {});
      if (!data.errors || !Object.keys(data.errors).length) {
        showToast(data.message || 'Something went wrong.', 'error');
      }
    }
  } catch {
    showToast('Network error — please try again.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
  }
}

function initAuthForms() {
  const lf = document.getElementById('loginForm');
  if (lf) {
    lf.addEventListener('submit', e => {
      e.preventDefault();
      submitAuthForm('loginForm', '/accounts/login/', 'loginBtn');
    });
  }

  const rf = document.getElementById('registerForm');
  if (rf) {
    rf.addEventListener('submit', e => {
      e.preventDefault();
      submitAuthForm('registerForm', '/accounts/register/', 'registerBtn');
    });
  }
}

const ALLOWED_MASTER  = ['.xlsx'];
const ALLOWED_TARGET  = ['.csv', '.xlsx', '.xls', '.docx', '.pdf', '.txt'];
const MAX_SIZE        = 25 * 1024 * 1024;

function fmtBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1048576).toFixed(1) + ' MB';
}

function getExt(name) {
  return '.' + name.split('.').pop().toLowerCase();
}

function initMasterZone() {
  const zone  = document.getElementById('masterZone');
  const input = document.getElementById('masterFileInput');
  const rmBtn = document.getElementById('masterRemoveBtn');
  if (!zone || !input) return;

  zone.addEventListener('click', e => {
    if (e.target === rmBtn || rmBtn?.contains(e.target)) return;
    input.click();
  });

  ['dragenter', 'dragover'].forEach(ev =>
    zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('dragover'); })
  );
  ['dragleave', 'drop'].forEach(ev =>
    zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove('dragover'); })
  );
  zone.addEventListener('drop', e => {
    const f = e.dataTransfer?.files[0];
    if (f) applyMasterFile(f);
  });

  input.addEventListener('change', () => {
    if (input.files[0]) applyMasterFile(input.files[0]);
  });

  if (rmBtn) {
    rmBtn.addEventListener('click', e => {
      e.stopPropagation();
      input.value = '';
      zone.classList.remove('has-file');
    });
  }
}

function applyMasterFile(file) {
  const zone  = document.getElementById('masterZone');
  const input = document.getElementById('masterFileInput');
  const ext   = getExt(file.name);

  if (!ALLOWED_MASTER.includes(ext)) {
    showToast(`Master BOM must be XLSX (got "${ext}").`, 'error'); return;
  }
  if (file.size > MAX_SIZE) {
    showToast(`"${file.name}" exceeds the 25 MB limit.`, 'error'); return;
  }

  const nameEl = zone.querySelector('.fi-name');
  const metaEl = zone.querySelector('.fi-meta');
  if (nameEl) nameEl.textContent = file.name;
  if (metaEl) metaEl.textContent = `XLSX · ${fmtBytes(file.size)}`;
  zone.classList.add('has-file');

  const dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;
}

let optFiles = [];

function initOptZone() {
  const btn  = document.getElementById('addOptBtn');
  const zone = document.getElementById('optZone');
  if (!btn) return;

  btn.addEventListener('click', () => {
    const tmp = document.createElement('input');
    tmp.type = 'file';
    tmp.multiple = true;
    tmp.accept = ALLOWED_TARGET.join(',');
    tmp.addEventListener('change', () => Array.from(tmp.files).forEach(addOptFile));
    tmp.click();
  });

  if (zone) {
    ['dragenter', 'dragover'].forEach(ev =>
      zone.addEventListener(ev, e => {
        e.preventDefault();
        zone.style.borderColor = 'var(--teal)';
        zone.style.background  = 'var(--teal-dim)';
      })
    );
    ['dragleave', 'drop'].forEach(ev =>
      zone.addEventListener(ev, e => {
        e.preventDefault();
        zone.style.borderColor = '';
        zone.style.background  = '';
      })
    );
    zone.addEventListener('drop', e => {
      Array.from(e.dataTransfer?.files || []).forEach(addOptFile);
    });
  }
}

function addOptFile(file) {
  if (optFiles.length >= 5) {
    showToast('Maximum 5 target files allowed.', 'warning'); return;
  }
  const ext = getExt(file.name);
  if (!ALLOWED_TARGET.includes(ext)) {
    showToast(`"${file.name}": unsupported format. Use CSV, XLSX, XLS, DOCX, PDF or TXT.`, 'error'); return;
  }
  if (file.size > MAX_SIZE) {
    showToast(`"${file.name}" exceeds the 25 MB limit.`, 'error'); return;
  }
  if (optFiles.find(f => f.name === file.name)) {
    showToast(`"${file.name}" is already added.`, 'warning'); return;
  }
  optFiles.push(file);
  renderOptFiles();
}

function removeOptFile(idx) {
  optFiles.splice(idx, 1);
  renderOptFiles();
}

function renderOptFiles() {
  const grid    = document.getElementById('optGrid');
  const counter = document.getElementById('optCounter');
  const addBtn  = document.getElementById('addOptBtn');

  if (counter) counter.textContent = optFiles.length;
  if (addBtn)  addBtn.disabled = optFiles.length >= 5;

  if (!grid) return;

  if (!optFiles.length) {
    grid.innerHTML = '<p style="text-align:center;color:var(--text-muted);font-size:0.82rem;font-family:var(--font-mono);padding:8px 0;margin:0;">No files added yet</p>';
    return;
  }

  grid.innerHTML = optFiles.map((f, i) => {
    const ext = getExt(f.name).replace('.', '').toUpperCase();
    return `
      <div class="opt-file-row">
        <span class="ext-badge">${ext}</span>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:600;font-size:0.86rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${f.name}</div>
          <div style="font-size:0.73rem;color:var(--text-muted);font-family:var(--font-mono);">${fmtBytes(f.size)}</div>
        </div>
        <button type="button" class="opt-remove" onclick="removeOptFile(${i})" title="Remove">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>`;
  }).join('');
}

function initUploadForm() {
  const form = document.getElementById('uploadForm');
  if (!form) return;

  form.addEventListener('submit', async e => {
    e.preventDefault();

    const masterInput = document.getElementById('masterFileInput');
    if (!masterInput?.files?.length) {
      showToast('Please select a master BOM file (XLSX).', 'error'); return;
    }
    if (!optFiles.length) {
      showToast('Please add at least one target file.', 'error'); return;
    }

    showLoading('Uploading and comparing BOM files…');

    const fd = new FormData(form);
    fd.delete('optional_files');
    optFiles.forEach(f => fd.append('optional_files', f));
    fd.set('csrfmiddlewaretoken', getCsrf());

    try {
      const res  = await fetch(form.action || '/comparison/new/', {
        method: 'POST', body: fd,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const data = await res.json();
      hideLoading();

      if (data.success) {
        showToast('Comparison complete! Loading results…', 'success');
        setTimeout(() => { window.location.href = data.redirect_url; }, 700);
      } else {
        const msgs = Array.isArray(data.errors)
          ? data.errors
          : Object.values(data.errors).flat();
        msgs.forEach(m => showToast(m, 'error'));
      }
    } catch {
      hideLoading();
      showToast('Upload failed — please try again.', 'error');
    }
  });
}

function confirmDeleteSession(sessionId, name) {
  if (!confirm(`Delete "${name}"?\n\nThis cannot be undone.`)) return;

  fetch(`/comparison/delete/${sessionId}/`, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCsrf() },
  })
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        showToast('Session deleted.', 'success');
        const card = document.getElementById(`session-card-${sessionId}`);
        if (card) {
          card.style.transition = 'opacity 0.3s, transform 0.3s';
          card.style.opacity    = '0';
          card.style.transform  = 'translateX(-10px)';
          setTimeout(() => card.remove(), 320);
        }
      } else {
        showToast('Delete failed.', 'error');
      }
    })
    .catch(() => showToast('Delete failed.', 'error'));
}

document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
  initAuthForms();
  initMasterZone();
  initOptZone();
  renderOptFiles();
  initUploadForm();
});