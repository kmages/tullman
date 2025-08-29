(function(){
  try{
    var $  = function(sel, root){ return (root||document).querySelector(sel); };
    var $$ = function(sel, root){ return Array.prototype.slice.call((root||document).querySelectorAll(sel)); };

    function findCard(prefix){
      var hs = $$(".card .h");
      for (var i=0;i<hs.length;i++){
        var t=(hs[i].textContent||"").trim().toLowerCase();
        if (t.indexOf(prefix.toLowerCase())===0) return hs[i].closest(".card");
      }
      return null;
    }

    // Box 5 textarea
    var box5 = findCard("Box 5 - Ask Again");
    if (box5 && !$("#loopQ2", box5)){
      var ta=document.createElement("textarea");
      ta.id="loopQ2"; ta.rows=2;
      ta.placeholder="(optional) rephrase or leave blank to reuse Box 1…";
      ta.style.margin="8px 0";
      var row=$(".row", box5);
      box5.insertBefore(ta, row?row:box5.lastChild);
    }

    // Box 6 actions
    var box6 = findCard("Box 6 - New System Response");
    if (box6 && !$("#box6Actions")){
      var actions=document.createElement("div");
      actions.className="card"; actions.id="box6Actions"; actions.style.marginTop="8px";
      actions.innerHTML =
        '<div class="h">Box 6 — Actions</div>' +
        '<div class="row">' +
          '<button id="b6Accept" class="btn ok" type="button">Accept</button>' +
          '<button id="b6Edit" class="btn" type="button">Edit</button>' +
          '<button id="b6AddVP" class="btn" type="button">Add to Voiceprint</button>' +
          '<span id="b6Msg" class="status"></span>' +
        '</div>';
      box6.parentNode.insertBefore(actions, box6.nextSibling);
    }

    // spacing between Box6 columns
    var tw = (box6 && box6.querySelector(".twocol")) || document.querySelector(".twocol");
    if (tw){ tw.style.gap="14px"; tw.style.columnGap="14px"; }

    // helpers
    function getQ1(){ return $("#loopQ") || $("#q") || $("input[type=text]"); }
    function getQ2(){ return $("#loopQ2"); }
    function getBox2(){ return findCard("Box 2 - System Response") || findCard("Box 2"); }
    function getA1(){
      var b2=getBox2(); if(b2){ var tas=$$("textarea", b2); if(tas.length) return tas[0]; }
      var tas2=$$("textarea"); return tas2.length>1?tas2[1]:null;
    }
    function getA2(){
      if(!box6) return null; var tas=$$("textarea", box6); return tas.length?tas[tas.length-1]:null;
    }
    function getA2Prev(){
      if(!box6) return null; var tas=$$("textarea", box6); return tas.length?tas[0]:null;
    }

    // Box 5 re-ask
    (function(){
      if(!box5) return;
      var askBtn=$("button", box5) || $(".btn", box5);
      if(!askBtn) return;
      askBtn.addEventListener("click", function(){
        var msg=$("#b6Msg") || $(".status", $("#box6Actions")||document);
        var q2=(getQ2()&&getQ2().value.trim()) || (getQ1()&&getQ1().value.trim()) || "";
        if(!q2){ if(msg) msg.textContent="Enter a question"; return; }
        if(msg) msg.textContent="Re-asking…";
        fetch("/retrieve",{
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({prompt:q2})
        }).then(function(r){return r.text();}).then(function(txt){
          var j={}; try{ j=JSON.parse(txt);}catch(e){ if(msg) msg.textContent="Bad JSON"; return; }
          var prev=getA2Prev(), oldA=getA1(); if(prev && oldA) prev.value=(oldA.value||"").trim();
          var a2=getA2(); if(a2) a2.value=(j.answer||"").trim();
          if(msg) msg.textContent="Done.";
        }).catch(function(){ if(msg) msg.textContent="Network error"; });
      });
    })();

    // Box 6 actions
    (function(){
      var bAccept=$("#b6Accept"), bEdit=$("#b6Edit"), bAddVP=$("#b6AddVP"), msg=$("#b6Msg");

      if(bAccept){
        bAccept.addEventListener("click", function(){
          var q=(getQ1()&&getQ1().value.trim())||"";
          var a=(getA2()&&getA2().value.trim())||"";
          if(!q||!a){ if(msg) msg.textContent="Nothing to save"; return; }
          if(msg) msg.textContent="Saving…";
          fetch("/admin/api/examples_text",{
            method:"POST", headers:{"Content-Type":"application/json"},
            body:JSON.stringify({text:"Q: "+q+"\nA: "+a+"\n"})
          }).then(function(r){return r.json();}).then(function(j){
            if(msg) msg.textContent=(j&&j.ok)?"Saved to examples.":"Error";
          }).catch(function(){ if(msg) msg.textContent="Network error"; });
        });
      }

      if(bEdit){
        var editing=false;
        bEdit.addEventListener("click", function(){
          var a2=getA2(); if(!a2) return;
          if(!editing){ a2.removeAttribute("readonly"); a2.focus(); bEdit.textContent="Save"; editing=true; }
          else{ a2.setAttribute("readonly","readonly"); bEdit.textContent="Edit"; editing=false; }
        });
      }

      if(bAddVP){
        bAddVP.addEventListener("click", function(){
          var a=(getA2()&&getA2().value.trim())||"";
          if(!a){ if($("#b6Msg")) $("#b6Msg").textContent="Nothing to append"; return; }
          if($("#b6Msg")) $("#b6Msg").textContent="Appending…";
          fetch("/admin/api/voiceprint",{
            method:"POST", headers:{"Content-Type":"application/json"},
            body:JSON.stringify({text:a, mode:"append"})
          }).then(function(r){return r.json();}).then(function(j){
            if($("#b6Msg")) $("#b6Msg").textContent=(j&&j.ok)?"Appended to voiceprint.":"Error";
          }).catch(function(){ if($("#b6Msg")) $("#b6Msg").textContent="Network error"; });
        });
      }
    })();

  }catch(e){}
})();
</script>
/* ensure Edit button exists even if actions card was static */
(function(){
  try{
    var row = document.querySelector("#box6Actions .row");
    if (row && !document.getElementById("b6Edit")) {
      var btn = document.createElement("button");
      btn.id = "b6Edit";
      btn.className = "btn";
      btn.type = "button";
      btn.textContent = "Edit";
      var add = document.getElementById("b6AddVP");
      if (add) row.insertBefore(btn, add); else row.appendChild(btn);

      // simple toggle for the NEW (right) Box 6 textarea
      var editing = false;
      btn.addEventListener("click", function(){
        var a2 = document.querySelector('#box6 textarea:last-of-type')
              || document.querySelector('[data-box="6"] textarea:last-of-type');
        if (!a2) return;
        if (!editing) { a2.removeAttribute("readonly"); a2.focus(); btn.textContent = "Save"; editing = true; }
        else { a2.setAttribute("readonly","readonly"); btn.textContent = "Edit"; editing = false; }
      });
    }
  }catch(e){}
})();
/* Move Box 6 Actions inside Box 6 and dedupe buttons */
(function(){
  try{
    // find the Box 6 card by its heading
    function findCard(prefix){
      var hs = document.querySelectorAll(".card .h");
      for (var i=0;i<hs.length;i++){
        var t = (hs[i].textContent||"").trim().toLowerCase();
        if (t.indexOf(prefix.toLowerCase()) === 0) return hs[i].closest(".card");
      }
      return null;
    }
    var box6 = findCard("Box 6 - New System Response");
    var actions = document.getElementById("box6Actions");
    if (box6 && actions) {
      // put actions as the last child inside Box 6
      if (actions.parentNode !== box6) box6.appendChild(actions);

      // make actions look like a simple row (not a full card)
      actions.className = "";
      actions.style.background = "transparent";
      actions.style.border = "0";
      actions.style.padding = "8px 0 0";
      actions.style.margin = "8px 0 0 0";

      // ensure only one Edit button
      var edits = document.querySelectorAll("#b6Edit");
      for (var i=1;i<edits.length;i++){
        if (edits[i] && edits[i].parentNode) edits[i].parentNode.removeChild(edits[i]);
      }
    }
  }catch(e){}
})();
