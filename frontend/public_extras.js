// ~/tullman/frontend/public_extras.js
// Front page helper: Example guardrail, counters, CLEAR CHAT, invisible "CHICAGO" button.
// Specs: Exclude locked-in Examples from Log; optionally capture Q; show Review Queue count; CLEAR CHAT; invisible button to queue pending Q&A

const API_BASE = location.origin.replace(/:\d+$/, '') + ':5057'; // assumes backend on 5057 locally

async function api(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// --- Example Guardrail ---
export async function checkExamples(question) {
  // 1) Try to match
  const r = await api(`/api/examples/match?q=${encodeURIComponent(question)}`, { method: 'GET' });
  if (r.matched && r.example && r.example.locked && r.example.active) {
    // 2) Immediately show canonical answer on the page (you likely have your own rendering function)
    const canonicalAnswer = r.example.answer;

    // 3) Send excluded ingest (capture Q only per config). This keeps Examples out of the Log.
    await api('/api/log/ingest', {
      method: 'POST',
      body: JSON.stringify({
        question,
        matched_example_id: r.example.id,
        source: 'front_page'
      })
    });

    return { handled: true, answer: canonicalAnswer };
  }
  return { handled: false };
}

// --- Submit flow wrapper ---
// Example usage:
//   const {handled, answer} = await guardedSubmit(question);
//   if (handled) { show(answer); } else { const modelAns = await callModel(question); ingestNormal(question, modelAns); show(modelAns); }
export async function guardedSubmit(question) {
  const ex = await checkExamples(question);
  if (ex.handled) return ex;
  return { handled: false };
}

// --- Normal ingest after non-Example answers ---
export async function ingestNormal(question, answer) {
  return api('/api/log/ingest', {
    method: 'POST',
    body: JSON.stringify({ question, answer, source: 'front_page' })
  });
}

// --- Counters + badges ("Review Queue (XX items pending)") ---
export async function refreshCounters() {
  const c = await api('/api/counters', { method: 'GET' });
  const badgeEls = document.querySelectorAll('[data-review-queue-badge]');
  badgeEls.forEach(el => el.textContent = `Review Queue (${c.review_queue} items pending)`);
  const headerCount = document.querySelector('[data-review-queue-header]');
  if (headerCount) headerCount.textContent = `Review Queue (${c.review_queue} items pending)`;
}

// --- CLEAR CHAT button (visible to all users) ---
export function wireClearChat(btnSelector, chatContainerSelector) {
  const btn = document.querySelector(btnSelector);
  const chat = document.querySelector(chatContainerSelector);
  if (!btn || !chat) return;
  btn.addEventListener('click', () => {
    chat.innerHTML = '';
    btn.blur();
    // Optionally also clear your local state store
    const msg = document.querySelector('[data-toast]');
    if (msg) { msg.textContent = 'Chat cleared.'; setTimeout(()=>msg.textContent='', 1500); }
  });
}

// --- Invisible "CHICAGO" button: move pending Q&A to Review Queue ---
// Behavior: find newest non-excluded "active" item and queue it.
export function wireInvisibleChicagoButton(hotspotSelector) {
  const hs = document.querySelector(hotspotSelector);
  if (!hs) return;
  hs.style.cursor = 'pointer';
  hs.title = ''; // keep invisible
  hs.addEventListener('click', async () => {
    let toast = document.querySelector('[data-toast]');
    try {
      // Get latest non-excluded item
      const log = await api('/api/log?limit=1', { method: 'GET' });
      if (!log.items || !log.items.length) throw new Error('No items to queue.');
      const latest = log.items[0];
      if (latest.status !== 'active') throw new Error(`Latest item status is "${latest.status}".`);
      // Queue it
      const r = await api(`/api/log/${latest.id}/action`, {
        method: 'PATCH',
        body: JSON.stringify({ action: 'queue' })
      });
      if (toast) toast.textContent = `Queued #${latest.date_id} for review.`;
      await refreshCounters();
      setTimeout(()=>{ if(toast) toast.textContent=''; }, 1500);
    } catch (e) {
      if (toast) toast.textContent = `Queue failed: ${e.message}`;
      setTimeout(()=>{ if(toast) toast.textContent=''; }, 2500);
    }
  });
}

// --- Spinner helpers for any button action (consistent UX) ---
export function withSpinner(btn, fn) {
  return async (...args) => {
    const old = btn.textContent;
    btn.disabled = true;
    btn.classList.add('spinning'); // your CSS can show a spinner next to text
    try { return await fn(...args); }
    finally {
      btn.disabled = false;
      btn.classList.remove('spinning');
      btn.textContent = old;
    }
  };
}

// Auto-refresh counters every 30s
setInterval(()=>refreshCounters().catch(()=>{}), 30000);
document.addEventListener('DOMContentLoaded', ()=>refreshCounters().catch(()=>{}));
