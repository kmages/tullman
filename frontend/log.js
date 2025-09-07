import { refreshCounters, withSpinner } from "/frontend/public_extras.js";
const API_BASE = location.origin.replace(/:\d+$/, "") + ":5057";
const listEl = document.querySelector("#list");
const toast = document.querySelector("[data-toast]");

function showToast(t,ms=1500){ if(!toast)return; toast.textContent=t; setTimeout(()=>toast.textContent="",ms); }

async function api(p,o={}) {
  const r=await fetch(`${API_BASE}${p}`,{headers:{"Content-Type":"application/json"},...o});
  if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

function renderRow(item){
  const el=document.createElement("div"); el.className="row"; el.dataset.id=item.id;
  const meta=document.createElement("div"); meta.className="meta";
  meta.textContent = `${item.date_id} • ${new Date(item.created_at).toLocaleString()} • status: ${item.status}`;
  el.appendChild(meta);
  const q=document.createElement("div"); q.className="qa"; q.innerHTML = `<strong>Q:</strong> ${item.question}`; el.appendChild(q);
  const a=document.createElement("div"); a.className="qa"; a.innerHTML = `<strong>A:</strong> ${item.answer || "<em>(empty)</em>"}`; el.appendChild(a);

  const actions=document.createElement("div"); actions.className="actions";
  const btnA=document.createElement("button"); btnA.textContent="Archive";
  const btnD=document.createElement("button"); btnD.textContent="Delete";
  const btnQ=document.createElement("button"); btnQ.textContent="Queue";
  const btnR=document.createElement("button"); btnR.textContent="Restore";
  const btnB=document.createElement("button"); btnB.textContent="Back";
  actions.append(btnA,btnD,btnQ,btnR,btnB); el.appendChild(actions);

  el.addEventListener("click",(ev)=>{ if(ev.target.tagName==="BUTTON")return; el.classList.toggle("selected"); });

  const doAction=async(action)=> {
    const r=await api(`/api/log/${item.id}/action`,{method:"PATCH",body:JSON.stringify({action})});
    showToast(r.message||`OK: ${action}`); await refreshCounters();
    meta.textContent = `${r.qa.date_id} • ${new Date(r.qa.created_at).toLocaleString()} • status: ${r.qa.status}`;
    if(action==="delete") el.style.opacity=0.5;
  };

  btnA.addEventListener("click",withSpinner(btnA,()=>doAction("archive")));
  btnD.addEventListener("click",withSpinner(btnD,()=>doAction("delete")));
  btnQ.addEventListener("click",withSpinner(btnQ,()=>doAction("queue")));
  btnR.addEventListener("click",withSpinner(btnR,()=>doAction("restore")));
  btnB.addEventListener("click",()=>window.scrollTo({top:0,behavior:"smooth"}));

  return el;
}

async function load(){
  await refreshCounters();
  const data=await api("/api/log?limit=100");
  listEl.innerHTML="";
  data.items.forEach(it=>listEl.appendChild(renderRow(it)));
}
document.querySelector("#btnTop").addEventListener("click",()=>window.scrollTo({top:0,behavior:"smooth"}));
document.addEventListener("DOMContentLoaded",load);
