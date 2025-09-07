import { refreshCounters, withSpinner } from '/frontend/public_extras.js';

const API_BASE = location.origin.replace(/:\d+$/, '') + ':5057';
const listEl = document.querySelector('#list');
const toast = document.querySelector('[data-toast]');

function showToast(text, ms = 1500) {
  if (!toast) return;
  toast.textContent = text;
  setTimeout(()=>toast.textContent='', ms);
}

async function api(path, opts={}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function renderRow(item) {
  const el = document.createElement('div');
  el.className = 'row';
  el.dataset.id = item.id;

  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.textContent = `${item.date_id} • queued: ${new Date(item.queued_at).toLocaleString()} • status: ${item.status}`;
  el.appendChild(meta);

  const q = document.createElement('div');
  q.className = 'qa';
  q.innerHTML = `<strong>Q:</strong> ${item.question}`;
  el.appendChild(q);

  const a = document.createElement('div');
  a.className = 'qa';
  a.innerHTML = `<strong>A:</strong> ${item.answer || '<em>(empty)</em>'}`;
  el.appendChild(a);

  const actions = document.createElement('div');
  actions.className = 'actions';

  const btnSend   = document.createElement('button'); btnSend.textContent   = 'Send to Loop2';
  const btnArchive= document.createElement('button'); btnArchive.textContent= 'Archive';
  const btnDelete = document.createElement('button'); btnDelete.textContent = 'Delete';
  const btnBack   = document.createElement('button'); btnBack.textContent   = 'Back';

  actions.append(btnSend, btnArchive, btnDelete, btnBack);
  el.appendChild(actions);

  // Highlight/select toggle (one click lights; second click unlights)
  el.addEventListener('click', (ev) => {
    if (ev.target.tagName === 'BUTTON') return;
    el.classList.toggle('selected');
  });

  // Actions per Request 2: Send to Loop2; plus Archive/Delete; Back-to-top UX
  const doSend = async () => {
    const r = await api(`/api/review-queue/send/${item.id}`, { method: 'POST' });
    showToast(r.message || 'Sent to Loop2.');
    await refreshCounters();
    meta.textContent = `${r.qa.date_id} • status: ${r.qa.status}`;
    el.style.opacity = 0.5; // visually indicate it left the queue
  };

  const doArchive = async () => {
    const r = await api(`/api/log/${item.id}/action`, {
      method: 'PATCH',
      body: JSON.stringify({ action: 'archive' })
    });
    showToast(r.message || 'Archived.');
    await refreshCounters();
    meta.textContent = `${r.qa.date_id} • status: ${r.qa.status}`;
    el.style.opacity = 0.5;
  };

  const doDelete = async () => {
    const r = await api(`/api/log/${item.id}/action`, {
      method: 'PATCH',
      body: JSON.stringify({ action: 'delete' })
    });
    showToast(r.message || 'Deleted.');
    await refreshCounters();
    meta.textContent = `${r.qa.date_id} • status: ${r.qa.status}`;
    el.style.opacity = 0.5;
  };

  btnSend   .addEventListener('click', withSpinner(btnSend   , doSend));
  btnArchive.addEventListener('click', withSpinner(btnArchive, doArchive));
  btnDelete .addEventListener('click', withSpinner(btnDelete , doDelete));
  btnBack   .addEventListener('click', () => window.scrollTo({top:0, behavior:'smooth'}));

  return el;
}

async function load() {
  await refreshCounters();
  const data = await api('/api/review-queue'); // oldest-first provided by backend
  listEl.innerHTML = '';
  data.items.forEach(it => listEl.appendChild(renderRow(it)));
}

document.querySelector('#btnTop').addEventListener('click', ()=>window.scrollTo({top:0, behavior:'smooth'}));
document.addEventListener('DOMContentLoaded', load);
