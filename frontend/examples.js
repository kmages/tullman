// Minimal JS for export + recover + list
const $ = (id) => document.getElementById(id);
const toast = $('toast');

function say(msg, ms = 1800) {
  toast.textContent = msg;
  if (ms) setTimeout(() => (toast.textContent = ''), ms);
}

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { 'Content-Type':'application/json' }, ...opts });
  if (!r.ok) throw new Error(await r.text().catch(()=>r.statusText));
  // /api/examples/export returns text (JSONL) — handle separately
  const ctype = r.headers.get('content-type') || '';
  return ctype.includes('application/json') ? r.json() : r.text();
}

function disable(btn, on=true) { btn.disabled = !!on; }

async function loadList() {
  try {
    const data = await api('/api/examples');
    $('count').textContent = `(${data.count} total)`;
    const list = $('examplesList');
    list.innerHTML = '';
    // Show newest first
    data.items.slice().reverse().forEach(ex => {
      const d = document.createElement('div');
      d.innerHTML = `
        <div class="meta">ID ${ex.id} • ${ex.locked ? 'locked' : 'unlocked'} • ${ex.active ? 'active' : 'inactive'}</div>
        <div><b>Q:</b> ${ex.primary_question}</div>
        <div style="margin-top:6px;"><b>A:</b> ${ex.answer}</div>
      `;
      list.appendChild(d);
    });
  } catch (e) {
    say('Load failed: ' + e.message, 2500);
  }
}

// ---- Export JSONL ----
$('btnExport').addEventListener('click', async () => {
  const btn = $('btnExport');
  try {
    disable(btn, true);
    const text = await api('/api/examples/export');
    const blob = new Blob([text], { type: 'application/jsonl;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'examples_backup.jsonl';
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    say('Exported examples_backup.jsonl');
  } catch (e) {
    say('Export failed: ' + e.message, 2500);
  } finally {
    disable(btn, false);
  }
});

// ---- Recover from Log ----
$('btnRecover').addEventListener('click', async () => {
  const btn = $('btnRecover');
  try {
    disable(btn, true);
    const body = {
      min_count: Math.max(1, parseInt($('minCount').value || '2', 10)),
      limit_max: Math.max(1, parseInt($('limitMax').value || '1000', 10)),
      include_excluded: $('includeExcluded').checked
    };
    const res = await api('/api/examples/recover_from_log', {
      method: 'POST',
      body: JSON.stringify(body)
    });
    say(`Recovered: +${res.created} created, ${res.updated} updated (considered ${res.considered})`, 2500);
    await loadList();
  } catch (e) {
    say('Recover failed: ' + e.message, 3000);
  } finally {
    disable(btn, false);
  }
});

document.addEventListener('DOMContentLoaded', loadList);
