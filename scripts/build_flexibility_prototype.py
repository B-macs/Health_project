"""Generate mockups/flexibility_prototype.html from the LIVE cluster modules.

The prototype cannot drift from the app: labels, locks, setups, measurements,
input hints, slot thresholds, the exercise library and the stacks are all read
out of cluster_a_battery.py, cluster_a_mechanics.py and cluster_a_prescription.py
at generation time. Only the readings are invented, and they are chosen so the
EARLY EXIT is visible — gate 0 and both leverages pass, the tilt fails, and the
flow stops at slot 2 with Pattern F, which is what this athlete's own baseline
predicts.

The JS mirrors the evaluators, including the two 2026-08-07 rules: the
turned-out attempt is skipped while the neutral reading sits above the 15 cm
relevance line, and the tilt is degrees-bigger-is-better with own-power first.

Run after any change to the three cluster modules:

    python scripts/build_flexibility_prototype.py
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cluster_a_battery as cb          # noqa: E402
import cluster_a_mechanics as cm        # noqa: E402
import cluster_a_prescription as cp     # noqa: E402
import flexibility_baselines as fb      # noqa: E402
from services import battery as b       # noqa: E402

FAKE = {
    "gate0_neutral":      {"": 28.0},
    # Never reached in the demo path: 28 cm is above the relevance line, so the
    # turned-out step skips itself — which is the behaviour being demonstrated.
    "gate0_turned_out":   {"": 25.0},
    "leverage_bent":      {"left": 8.0, "right": 9.5},
    "leverage_straight":  {"left": 95.0, "right": 94.0},
    "tilt_production":    {"": 4.0},
    "tilt_range":         {"": 8.0},
    "spectrum_active":    {"left": 38.0, "right": 35.0},
    "spectrum_isometric": {"": 30.0},
    "spectrum_passive":   {"": 12.0},
}

#: The setup number each trial was taken at, where the test has one.
SETUP_FAKE = {"leverage_bent": 34.0, "tilt_production": 92.0}

tests = []
for key in cb.AVAILABLE_TESTS:
    t = cb.TESTS[key]
    tests.append({
        "key": key, "slot": t.slot, "slotLabel": b.SLOT_LABELS[t.slot],
        "label": t.label, "unit": t.unit, "bilateral": t.bilateral,
        "setup": t.setup, "lock": t.lock, "measurement": t.measurement,
        "hint": t.input_hint,
        "testing": t.what_youre_testing, "safety": t.safety,
        "adapted": t.adapted_from, "setupInput": t.setup_input,
        "setupFake": SETUP_FAKE.get(key), "fake": FAKE.get(key, {}),
    })


def _ex(name):
    return cm.exercise(name)


stacks = {}
for pattern, stack in cp.STACKS.items():
    items = []
    for i in stack.items:
        ex = _ex(i.exercise)
        items.append({
            "name": i.exercise, "dose": i.dose, "note": i.note, "deferred": i.deferred,
            "spectrum": ex.spectrum if ex else "",
            "why": ex.note if ex else "",
            "position": ex.position if ex else "",
            "movement": ex.movement if ex else "",
            "feel": ex.feel if ex else "",
            "stopRule": ex.stop if ex else "",
            "progress": ex.progress if ex else "",
            "adapted": ex.adapted_from if ex else "",
            "reverts": ex.reverts_when if ex else "",
        })
    stacks[pattern] = {"limiter": stack.limiter, "intro": stack.intro,
                       "outro": stack.outro, "items": items}

release = [{"name": r.name, "dose": r.dose, "laterality": r.laterality}
           for r in cp.release_block(hip_focused=True, right_hip_loaded=True)]

DATA = json.dumps({
    "clusterLabel": cm.CLUSTER_LABEL,
    "tests": tests,
    "ladderInfo": [dict(i) for i in cb.LADDER_INFO],
    "order": list(cb.AVAILABLE_TESTS),
    "skipNotes": cb.SKIP_NOTES,
    "patterns": cb.PATTERNS,
    "stacks": stacks,
    "release": release,
    "slots": {str(k): {"label": v, "question": b.SLOT_QUESTIONS[k],
                       "decides": b.SLOT_DECIDES[k]} for k, v in b.SLOT_LABELS.items()},
    "measures": [list(m) for m in fb.MEASURES_EXPLAINED],
    "gap": fb.GAP_EXPLAINED,
    "lock": fb.LOCK_EXPLAINED,
    "frozen": [list(f) for f in fb.FROZEN_CONSTANTS],
    "progression": list(fb.PROGRESSION_VARIABLE),
    "nerve": cb.NERVE_CHECK,
    "deferredTests": [{"label": cb.TESTS[k].label, "why": cb.TESTS[k].safety}
                      for k in cb.DEFERRED_TESTS],
    "baselinesRequired": b.BASELINE_SESSIONS_REQUIRED,
    "th": {"gate0Gain": cb.GATE0_ORIENTATION_GAIN_CM,
           "bone": cb.GATE0_BONE_RELEVANT_CM,
           "bent": cb.LEVERAGE_TARGETS["leverage_bent"],
           "straight": cb.LEVERAGE_TARGETS["leverage_straight"],
           "tilt": cb.TILT_TARGET_DEG,
           "gap": cb.SPECTRUM_GAP_CM},
}, indent=1)

HTML = r"""<title>Flexibility — Cluster A prototype</title>

<style>
  :root {
    color-scheme: dark;
    --bg:#0B0F1A; --panel:#0E1018; --ink:#F4F6FB; --ink2:#9AA3B2; --ink3:#5A6377;
    --accent:#22C3E6; --good:#6BAF8B; --warn:#BFA06A; --bad:#C47878;
    --hair:rgba(255,255,255,0.07);
  }
  *{box-sizing:border-box}
  html{background:var(--bg)}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:14px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;-webkit-font-smoothing:antialiased}
  .wrap{max-width:780px;margin:0 auto;padding:26px 18px 90px}
  .bar{display:flex;align-items:center;justify-content:space-between;
    padding-bottom:14px;border-bottom:1px solid var(--hair);margin-bottom:20px}
  .bar b{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}
  .bar .rs{font-size:11px;cursor:pointer;border:1px solid var(--hair);
    padding:5px 11px;border-radius:8px;background:transparent;color:var(--ink3);font-family:inherit}
  .bar .rs:hover{color:var(--ink2);border-color:var(--ink3)}
  .card{background:var(--panel);border:1px solid var(--hair);border-radius:14px;
    padding:16px 18px;margin-bottom:10px}
  .card.hi{border-color:rgba(196,120,120,.45);background:rgba(196,120,120,.07)}
  .card.ok{border-color:rgba(107,175,139,.45);background:rgba(107,175,139,.07)}
  .cap{font-size:9px;letter-spacing:.13em;text-transform:uppercase;color:var(--ink3);font-weight:700}
  .huge{font-size:36px;font-weight:800;line-height:1.08;margin-top:8px}
  .big{font-size:26px;font-weight:800;line-height:1.12;margin-top:6px}
  .sm{font-size:12px;color:var(--ink2);margin-top:8px;line-height:1.65}
  .row{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
  .nm{font-size:15px;font-weight:650;color:var(--ink)}
  .kv{display:flex;gap:16px;flex-wrap:wrap;margin-top:9px;font-size:11.5px;color:var(--ink3)}
  .kv b{color:var(--ink2);font-weight:650}
  .steps{display:flex;gap:3px;margin-bottom:14px}
  .steps i{height:3px;flex:1;border-radius:2px;background:rgba(255,255,255,.10)}
  .steps i.done{background:var(--good)} .steps i.now{background:var(--accent)}
  .lock{background:rgba(191,160,106,.11);border:1px solid rgba(191,160,106,.32);
    color:#E2CB9B;border-radius:10px;padding:11px 13px;font-size:11.5px;line-height:1.65;margin:12px 0}
  details{background:var(--panel);border:1px solid var(--hair);border-radius:11px;
    padding:10px 14px;margin-bottom:10px}
  details summary{cursor:pointer;font-size:12px;color:var(--ink2)}
  details .sm{margin-top:10px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px}
  .grid.one{grid-template-columns:1fr}
  .fld{background:rgba(255,255,255,.04);border:1px solid var(--hair);border-radius:9px;
    padding:8px 11px;margin-top:7px}
  .fld .l{font-size:9px;letter-spacing:.11em;text-transform:uppercase;color:var(--ink3);font-weight:650}
  .fld input{width:100%;background:transparent;border:0;color:var(--ink);
    font:650 17px/1.4 ui-monospace,Menlo,monospace;margin-top:4px;
    font-variant-numeric:tabular-nums;outline:none}
  .chk{display:flex;align-items:center;gap:9px;margin:14px 0 4px;font-size:12px;
    color:var(--ink2);cursor:pointer}
  .chk input{width:15px;height:15px;accent-color:var(--bad);cursor:pointer}
  .btns{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
  button.b{flex:1;min-width:110px;padding:13px 14px;border-radius:11px;border:0;
    font:800 13.5px/1 ui-monospace,Menlo,monospace;cursor:pointer;background:var(--accent);color:#04222B}
  button.b.ghost{background:transparent;border:1px solid var(--hair);color:var(--ink2);font-weight:600}
  button.b:hover{filter:brightness(1.08)}
  .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:9.5px;font-weight:700}
  .note{font-size:11px;color:var(--ink3);margin-top:8px;line-height:1.6}
  @media(max-width:620px){.grid{grid-template-columns:1fr}}
</style>

<div class="wrap">
  <div class="bar">
    <b>Flexibility &middot; Cluster A &middot; prototype</b>
    <button class="rs" onclick="reset()">Reset</button>
  </div>
  <div id="app"></div>
  <div class="note" id="foot"></div>
</div>

<script>
const DATA = __DATA__;
let S = null;

function reset(){ S = {screen:'intro', step:0, cold:true, r:{}, forced:false}; render(); }
function md(t){ return String(t||'').replace(/\*\*([^*]+)\*\*/g,'<b style="color:var(--ink2)">$1</b>'); }
function el(h){ document.getElementById('app').innerHTML = h; }
function T(k){ return DATA.tests.find(t=>t.key===k); }

// ── the slot logic, mirroring cluster_a_battery.py's evaluators ─────────────
function val(k,side){ const v=(S.r[k]||{})[side===undefined?'':side]; return (v===''||v==null)?null:Number(v); }
function worst(k){ const o=S.r[k]||{}; const v=Object.values(o).filter(x=>x!==''&&x!=null).map(Number);
  return v.length?Math.max.apply(null,v):null; }
function best(k){ const o=S.r[k]||{}; const v=Object.values(o).filter(x=>x!==''&&x!=null).map(Number);
  return v.length?Math.min.apply(null,v):null; }

// The LIVE order: above the relevance line the turned-out comparison answers
// nothing and its step skips itself — mirroring cluster_a_battery.applicable_tests.
function liveOrder(){ const n=val('gate0_neutral');
  return (n!==null && n>DATA.th.bone)
    ? DATA.order.filter(function(k){return k!=='gate0_turned_out';})
    : DATA.order; }

function evaluate(){
  const out=[];
  const n=val('gate0_neutral'), t=val('gate0_turned_out');
  if(n===null) return {slots:out, pattern:null, stopped:0, indet:true};
  if(n>DATA.th.bone){
    out.push({slot:0,pass:true,reason:'At '+n.toFixed(1)+' cm off the floor, bone cannot be what stops you — '
      +'that contact only happens in the last few centimetres of a full split. The two-orientation check '
      +'starts mattering under '+DATA.th.bone.toFixed(0)+' cm; it comes back by itself once you are inside that line.'});
  } else {
    if(t===null) return {slots:out, pattern:null, stopped:0, indet:true};
    const gain=n-t;
    if(gain>=DATA.th.gate0Gain){ out.push({slot:0,pass:false,pattern:'B',
        reason:'Turning the legs out gained '+gain.toFixed(1)+' cm. Orientation is the limiter, not tissue length.'});
      return {slots:out, pattern:'B', stopped:0}; }
    out.push({slot:0,pass:true,reason:'Turning out changed the depth by '+gain.toFixed(1)+' cm — below the threshold, so this is a genuine tissue restriction.'});
  }

  const bent=worst('leverage_bent'), str=best('leverage_straight');
  if(bent===null||str===null) return {slots:out, pattern:null, stopped:1, indet:true};
  const bf=bent>DATA.th.bent, sf=str<DATA.th.straight;
  if(bf&&sf){ out.push({slot:1,pass:false,pattern:'C',reason:'Both leverages short — the whole group.'}); return {slots:out,pattern:'C',stopped:1}; }
  if(bf){ out.push({slot:1,pass:false,pattern:'D',reason:'Short bent, better straight — adductors and rotators.'}); return {slots:out,pattern:'D',stopped:1}; }
  if(sf){ out.push({slot:1,pass:false,pattern:'E',reason:'Fine bent, poor straight. Gracilis is the only one of the group crossing the knee, so that difference names it.'}); return {slots:out,pattern:'E',stopped:1}; }
  out.push({slot:1,pass:true,reason:'Length is adequate at both available leverages.'});

  // Degrees of pelvic tip, BIGGER is better — own power first, then helped.
  const rg=val('tilt_range'), pr=val('tilt_production');
  if(rg===null||pr===null) return {slots:out, pattern:null, stopped:2, indet:true};
  if(rg<DATA.th.tilt){ out.push({slot:2,pass:false,pattern:'F',reason:'The position is not available even with help. Tilt work goes FIRST in the session and starts assisted.'}); return {slots:out,pattern:'F',stopped:2}; }
  if(pr<DATA.th.tilt){ out.push({slot:2,pass:false,pattern:'G',reason:'You can reach it, you cannot produce it. Tilt work moves to the END and becomes strength work.'}); return {slots:out,pattern:'G',stopped:2}; }
  out.push({slot:2,pass:true,reason:'The tilt is available and producible — not your limiter.'});

  const act=worst('spectrum_active'), iso=val('spectrum_isometric'), pas=val('spectrum_passive');
  if(act===null||iso===null||pas===null) return {slots:out, pattern:null, stopped:3, indet:true};
  if(!(iso>pas)){ out.push({slot:3,pass:false,indet:true,reason:'The isometric reading is as deep as the passive one, so the load was too light — you measured passive twice.'}); return {slots:out,pattern:null,stopped:3,indet:true}; }
  const g=iso-pas;
  if(g>=DATA.th.gap){ out.push({slot:3,pass:false,pattern:'H',reason:'Passive goes '+g.toFixed(1)+' cm deeper than you can hold. The range exists and is not defended.'}); return {slots:out,pattern:'H',stopped:3}; }
  out.push({slot:3,pass:false,pattern:'I',reason:'You hold what you can reach, but cannot open the legs under your own power.'});
  return {slots:out,pattern:'I',stopped:3};
}

// ── the ladder, mirroring cluster_a_battery.ladder() ────────────────────────
function frac(m,t,smaller){ if(m==null||t==null||m<=0||t<=0) return null;
  var f = smaller ? t/m : m/t; return Math.max(0, Math.min(1, f)); }

function ladderRungs(ev){
  const ran={}; ev.slots.forEach(function(s){ ran[s.slot]=s; });
  const n=val('gate0_neutral');
  const bent=worst('leverage_bent'), str=best('leverage_straight');
  const rg=val('tilt_range'), pr=val('tilt_production');
  const iso=val('spectrum_isometric'), pas=val('spectrum_passive');
  const act=S.r['spectrum_active']||{};
  const sum=(act['left']!=null&&act['left']!==''&&act['right']!=null&&act['right']!=='')
    ? Number(act['left'])+Number(act['right']) : null;
  function info(k){ return DATA.ladderInfo.find(function(i){return i.key===k;}); }
  const out=[];
  function add(k,state,m,t,f,pat){ const i=info(k);
    out.push({key:k,label:i.label,muscle:i.muscle,unit:i.unit,provisional:i.provisional,
              state:state,measured:m,target:t,fraction:f,pattern:pat||''}); }

  if(!(0 in ran)) add('bone','unmeasured',null,null,null);
  else if(!ran[0].pass) add('bone','limiting',n,null,null,'B');
  else add('bone','passed',n,null,null);

  const s1=ran[1], bf=frac(bent,DATA.th.bent,true), sf=frac(str,DATA.th.straight,false);
  if(s1){ const p=s1.pattern||'';
    add('group_length',(p==='C'||p==='D')?'limiting':'passed',bent,DATA.th.bent,bf,(p==='C'||p==='D')?p:'');
    add('gracilis',(p==='C'||p==='E')?'limiting':'passed',str,DATA.th.straight,sf,(p==='C'||p==='E')?p:'');
  } else {
    add('group_length',bent!=null?'context':'unmeasured',bent,DATA.th.bent,bent!=null?bf:null);
    add('gracilis',str!=null?'context':'unmeasured',str,DATA.th.straight,str!=null?sf:null);
  }

  const s2=ran[2], rf=frac(rg,DATA.th.tilt,false), pf=frac(pr,DATA.th.tilt,false);
  if(s2){ const p=s2.pattern||'';
    if(p==='F'){ add('tilt_range','limiting',rg,DATA.th.tilt,rf,'F');
                 add('tilt_production','context',pr,DATA.th.tilt,pf); }
    else if(p==='G'){ add('tilt_range','passed',rg,DATA.th.tilt,rf);
                      add('tilt_production','limiting',pr,DATA.th.tilt,pf,'G'); }
    else { add('tilt_range','passed',rg,DATA.th.tilt,rf);
           add('tilt_production','passed',pr,DATA.th.tilt,pf); }
  } else {
    add('tilt_range',rg!=null?'context':'unmeasured',rg,DATA.th.tilt,rg!=null?rf:null);
    add('tilt_production',pr!=null?'context':'unmeasured',pr,DATA.th.tilt,pr!=null?pf:null);
  }

  const s3=ran[3];
  const df=(iso!=null&&pas!=null&&iso>0)?Math.max(0,Math.min(1,pas/iso)):null;
  const opf=frac(sum,180,false);
  if(s3&&s3.indet){ add('end_range','unreadable',iso,pas,null);
    add('pullers',sum!=null?'context':'unmeasured',sum,180,sum!=null?opf:null); }
  else if(s3){ add('end_range',s3.pattern==='H'?'limiting':'passed',iso,pas,df,s3.pattern==='H'?'H':'');
    add('pullers',s3.pattern==='I'?'limiting':'passed',sum,180,opf,s3.pattern==='I'?'I':''); }
  else { add('end_range',(iso!=null&&pas!=null)?'context':'unmeasured',iso,pas,df);
    add('pullers',sum!=null?'context':'unmeasured',sum,180,sum!=null?opf:null); }
  return out;
}

// Seed ONE test, and only when its step is reached. Prefilling everything up
// front made the battery reach its answer before the first step was shown,
// which is correct behaviour and a useless demonstration of it.
function seed(t){
  S.r[t.key]=S.r[t.key]||{};
  Object.keys(t.fake).forEach(function(side){
    if(S.r[t.key][side]===undefined) S.r[t.key][side]=t.fake[side]; });
}

function render(){
  document.getElementById('foot').innerHTML =
    'Prototype only — readings are pre-filled and nothing is saved. Tests, locks, slot thresholds, '
    + 'the exercise library and the stacks are the real ones, read out of cluster_a_*.py at build time '
    + '(scripts/build_flexibility_prototype.py).';
  if(S.screen==='intro') return intro();
  if(S.screen==='cold')  return cold();
  if(S.screen==='step')  return step();
  return done();
}

function intro(){
  el('<div class="card"><div class="cap">Standing goal &middot; no deadline</div>'
    +'<div class="huge" style="color:var(--accent)">Not measured</div>'
    +'<div class="sm">'+DATA.clusterLabel+' &middot; up to '+DATA.order.length+' tests &middot; '
    +'measured <b style="color:var(--ink2)">cold</b>, no warm-up.<br>'
    +'Every four weeks. It usually stops early — the first failing slot is your answer, '
    +'and nothing below it is worth measuring.</div></div>'
    +'<div class="btns"><button class="b" onclick="S.screen=\'cold\';render()">Start assessment</button></div>'
    +'<div class="card" style="margin-top:12px"><div class="cap">What this produces</div>'
    +'<div class="sm">One <b style="color:var(--ink2)">pattern label</b>, and nothing else. Not a score. '
    +'The label is what the training stack is looked up by — and a stack without a label is a guess, '
    +'so the app refuses to produce one.</div></div>'
    +'<details><summary>The four slots, and why they run in order</summary>'
    + Object.keys(DATA.slots).map(function(k){ var v=DATA.slots[k];
        return '<div class="sm"><b style="color:var(--ink2)">'+k+'. '+v.label+'</b> — '+v.question+'</div>'
             + '<div class="sm">Decides: '+v.decides+'</div>'; }).join('')
    +'<div class="sm">Stop at the first failure. There is no value in measuring a spectrum profile '
    +'for a skill that a bony block had already made unavailable.</div></details>'
    +'<details><summary>Held back for now &middot; '+DATA.deferredTests.length+'</summary>'
    + DATA.deferredTests.map(function(d){ return '<div class="sm"><b style="color:var(--ink2)">'+d.label+'</b></div>'
        +'<div class="sm">'+md(d.why)+'</div>'; }).join('')+'</details>');
}

function cold(){
  el('<div class="card"><div class="cap">Before you start</div>'
    +'<div class="big" style="color:var(--accent)">Measure cold</div>'
    +'<div class="sm">No warm-up, no session beforehand, first thing. A warm reading measures a '
    +'viscoelastic effect that is gone within hours — a cold one isolates the durable change.</div></div>'
    +'<label class="chk"><input type="radio" name="c" checked onchange="S.cold=true"> Cold — no warm-up</label>'
    +'<label class="chk"><input type="radio" name="c" onchange="S.cold=false"> Warm — I have trained today</label>'
    +'<details open><summary>How to understand the three numbers</summary>'
    + DATA.measures.map(function(m){ return '<div class="sm"><b style="color:var(--ink2)">'
        +m[0].charAt(0).toUpperCase()+m[0].slice(1)+' — '+m[1]+'</b></div><div class="sm">'+m[2]+'</div>'; }).join('')
    +'<div class="sm">'+md(DATA.gap)+'</div>'
    +'<div class="sm">Assisted work always comes after unassisted: the spectrum runs '
    +'<b style="color:var(--ink2)">active → isometric → passive</b>, and the tilt runs '
    +'<b style="color:var(--ink2)">own power before helped</b>. Help and passive work leave everything '
    +'looser, so taking either first would flatter what follows it.</div></details>'
    +'<details><summary>What a LOCK is, and what to do if you lose it</summary>'
    +'<div class="sm">'+md(DATA.lock)+'</div></details>'
    +'<details><summary>Measure these once, then re-use them forever</summary>'
    + DATA.frozen.map(function(f){ return '<div class="sm"><b style="color:var(--ink2)">'
        +f[0].replace(/_/g,' ')+'</b> — '+f[1]+'</div>'; }).join('')
    +'<div class="sm"><b style="color:var(--good)">'+DATA.progression[0].replace(/_/g,' ')+'</b> — '
    +'<i>this one is meant to move.</i> '+DATA.progression[1]+'</div></details>'
    +'<details><summary>The nerve check</summary><div class="sm">'+md(DATA.nerve)+'</div></details>'
    +'<div class="btns">'
    +'<button class="b" onclick="S.screen=\'step\';S.step=0;render()">Begin</button>'
    +'<button class="b ghost" onclick="S.screen=\'intro\';render()">Cancel</button></div>');
}

function step(){
  const ev = evaluate();
  if(ev.pattern && !S.forced){
    const last = ev.slots[ev.slots.length-1];
    el('<div class="card ok"><div class="cap" style="color:var(--good)">That is your answer — stop here</div>'
      +'<div class="big" style="color:var(--accent)">Pattern '+ev.pattern+' &middot; '+DATA.patterns[ev.pattern]+'</div>'
      +'<div class="sm">'+last.reason+'</div>'
      +'<div class="sm">The remaining tests measure things below the slot that stopped you, and a reading '
      +'taken below a failure cannot be interpreted. There is nothing more to collect today.</div></div>'
      +'<div class="btns">'
      +'<button class="b" onclick="S.screen=\'done\';render()">Save assessment</button>'
      +'<button class="b ghost" onclick="S.forced=true;render()">Keep going anyway</button></div>');
    return;
  }

  const ORD = liveOrder();
  if(S.step>ORD.length-1) S.step=ORD.length-1;
  const t = T(ORD[S.step]);
  seed(t);
  const skipped = DATA.order.filter(function(k){return ORD.indexOf(k)<0;})
    .map(function(k){return DATA.skipNotes[k]||'';}).filter(Boolean);
  const sides = t.bilateral ? ['left','right'] : [''];
  const ticks = ORD.map(function(k,i){
    return '<i class="'+(i===S.step?'now':((S.r[k]&&Object.keys(S.r[k]).length)?'done':''))+'"></i>'; }).join('');
  const fields = sides.map(function(s){
    var v = (S.r[t.key]||{})[s];
    return '<div><div class="fld"><div class="l">'+(s||'value')+' ('+t.unit+')</div>'
      +'<input type="number" step="0.5" value="'+(v===undefined?'':v)+'" '
      +'oninput="S.r[\''+t.key+'\']=S.r[\''+t.key+'\']||{};S.r[\''+t.key+'\'][\''+s+'\']=this.value"></div></div>';
  }).join('');

  el('<div class="steps">'+ticks+'</div>'
    + skipped.map(function(n){return '<div class="note">'+n+'</div>';}).join('')
    +'<div class="row"><span class="nm">'+t.label+'</span>'
    +'<span class="cap">'+(S.step+1)+' of '+ORD.length+' &middot; slot '+t.slot+' '+t.slotLabel+'</span></div>'
    +'<div class="lock"><b>LOCK</b> &mdash; '+md(t.lock)+'</div>'
    +'<div class="card"><div class="sm" style="color:var(--ink2)">'+md(t.setup)+'</div></div>'
    +'<details><summary>How to read it</summary>'
    +'<div class="sm">'+md(t.measurement)+'</div>'
    +'<div class="sm"><b style="color:var(--ink2)">What you are testing</b></div>'
    +'<div class="sm">'+t.testing+'</div>'
    +(t.adapted?'<div class="sm"><i>Adapted for you — '+t.adapted+'.</i></div>':'')
    +(t.safety?'<div class="sm" style="color:#E2CB9B">'+md(t.safety)+'</div>':'')
    +'</details>'
    +(t.hint?'<div class="sm"><b style="color:var(--ink2)">What to type:</b> '+md(t.hint)+'</div>':'')
    +'<div class="grid'+(sides.length===1?' one':'')+'">'+fields+'</div>'
    +(t.setupInput?'<div class="fld"><div class="l">'+t.setupInput+'</div>'
      +'<input type="number" step="0.5" value="'+(t.setupFake==null?'':t.setupFake)+'" '
      +'placeholder="recorded beside the reading — they are one datum"></div>':'')
    +'<label class="chk"><input type="checkbox"> The lock was lost — void this trial</label>'
    +'<div class="btns">'
    +'<button class="b" onclick="next()">'+(S.step===ORD.length-1?'Save &amp; finish':'Save &amp; next')+'</button>'
    +'<button class="b ghost" onclick="next()">Skip</button>'
    +(S.step>0?'<button class="b ghost" onclick="S.step--;render()">Back</button>':'')+'</div>');
}

function next(){
  if(S.step>=liveOrder().length-1){ S.screen='done'; } else { S.step++; }
  render();
}

function done(){
  const ev = evaluate();
  if(!ev.pattern){
    el('<div class="card"><div class="cap">Assessed today</div>'
      +'<div class="big" style="color:var(--ink3)">No pattern reached</div>'
      +'<div class="sm">'+((ev.slots[ev.slots.length-1]||{}).reason||'Not enough readings.')+'</div>'
      +'<div class="sm">A missing measurement is not a pass. Re-run the slot that stopped, rather than '
      +'reading this as nothing being wrong.</div></div>'
      +'<div class="btns"><button class="b ghost" onclick="reset()">Start again</button></div>');
    return;
  }
  const st = DATA.stacks[ev.pattern];
  const last = ev.slots[ev.slots.length-1];
  let h = '<div class="card hi">'
    +'<div class="cap">'+DATA.clusterLabel+' &middot; assessed today'
    +(S.cold?'':' &middot; <b style="color:var(--warn)">WARM — not comparable with a cold reading</b>')+'</div>'
    +'<div class="cap" style="color:var(--bad);margin-top:8px">What is stopping you</div>'
    +'<div class="big" style="color:var(--bad)">'+DATA.patterns[ev.pattern]+'</div>'
    +'<div class="kv"><span>pattern <b>'+ev.pattern+'</b></span>'
    +'<span>stopped at <b>'+DATA.slots[String(ev.stopped)].label+'</b></span>'
    +'<span><b>'+ev.slots.length+'</b> of 4 slots run</span></div></div>'
    +'<div class="sm">'+last.reason+'</div>'
    +'<div class="card" style="border-color:rgba(191,160,106,.4)">'
    +'<div class="sm" style="color:#E2CB9B"><b>This is a hypothesis, not a verdict.</b> '
    +'A pattern is trusted after '+DATA.baselinesRequired+' baseline mornings; there is 1. '
    +'Until then every threshold is provisional and no single reading is a reason to change anything.</div></div>';

  h += '<div class="cap" style="margin:18px 0 8px">The ladder &mdash; tightest at the bottom, work the marked rung first</div>';
  ladderRungs(ev).slice().reverse().forEach(function(r){
    var tag='not measured', tcol='var(--ink3)', fill=null, fcol='var(--good)', box='';
    if(r.state==='limiting'){ tag='▶ work this first'+(r.pattern?' · §'+r.pattern:'');
      tcol='var(--accent)'; fill=r.fraction||0; fcol='var(--accent)';
      box='border-color:var(--accent);background:rgba(34,195,230,.06);'; }
    else if(r.state==='passed'){ tag='✓ climbed'; tcol='var(--good)';
      fill=(r.fraction==null?1:r.fraction); }
    else if(r.state==='context'){ tag='context, not diagnosis'; tcol='var(--warn)';
      fill=r.fraction||0; fcol='var(--warn)'; }
    else if(r.state==='unreadable'){ tag='botched — repeat'; tcol='var(--bad)'; }
    var v = r.fraction!=null
      ? (r.measured+r.unit+' of '+r.target+r.unit+' · '+Math.round(r.fraction*100)+'%'
         +(r.provisional?' · provisional':''))
      : (r.measured!=null?(r.measured+r.unit):'—');
    h += '<div class="card" style="padding:10px 13px;margin-bottom:6px;'+box+'">'
      +'<div class="row"><span style="font-size:12px"><b>'+r.label+'</b> '
      +'<span style="color:var(--ink3);font-size:10.5px">· '+r.muscle+'</span></span>'
      +'<span style="font-size:11px;color:var(--ink2);white-space:nowrap">'+v+'</span></div>'
      +'<div style="height:5px;border-radius:3px;background:rgba(255,255,255,.08);margin-top:6px;overflow:hidden">'
      +(fill!=null?'<i style="display:block;height:5px;width:'+Math.round(fill*100)+'%;background:'+fcol+'"></i>':'')
      +'</div>'
      +'<div class="cap" style="color:'+tcol+';margin-top:6px">'+tag+'</div></div>';
  });
  h += '<div class="note">A grey rung is unknown, not zero — the battery stops at the first failure. No rung is ever averaged with another.</div>';

  // The release block is the TRAINING PLAN's business (athlete's review,
  // 2026-08-07) and stack intros are why-material — neither renders here.
  h += '<div class="cap" style="margin:18px 0 8px">Your stack &mdash; &sect;'+ev.pattern+', '+st.limiter+'</div>';
  st.items.filter(function(i){return !i.deferred;}).forEach(function(i,n){
    var tint = i.spectrum==='resisted' ? 'var(--good)' : 'var(--ink3)';
    h += '<details><summary>'+(n+1)+'. '+i.name+' &middot; '+i.dose+'</summary>'
      +'<div class="sm"><span class="pill" style="color:'+tint+'">'+i.spectrum+'</span></div>'
      +(i.position?'<div class="sm"><b style="color:var(--ink2)">Position</b> — '+md(i.position)+'</div>'
        +'<div class="sm"><b style="color:var(--ink2)">The movement</b> — '+md(i.movement)+'</div>'
        +'<div class="sm"><b style="color:var(--ink2)">You should feel</b> — '+md(i.feel)+'</div>'
        +'<div class="sm"><b style="color:var(--ink2)">Stop rule</b> — '+md(i.stopRule)+'</div>'
        +'<div class="sm"><b style="color:var(--ink2)">Progress is</b> — '+md(i.progress)+'</div>':'')
      +(i.why?'<div class="sm">Why — '+md(i.why)+'</div>':'')
      +(i.note?'<div class="sm">'+md(i.note)+'</div>':'')
      +(i.adapted?'<div class="sm"><i>Adapted — replaces '+i.adapted+'. Reverts when '+i.reverts+'.</i></div>':'')
      +'</details>';
  });
  var held = st.items.filter(function(i){return i.deferred;});
  if(held.length) h += '<details><summary>Held back for now &middot; '+held.length+'</summary>'
    + held.map(function(i){ return '<div class="sm"><b style="color:var(--ink2)">'+i.name+'</b></div>'
        +'<div class="sm">'+(i.reverts||'')+'</div>'; }).join('')+'</details>';
  if(st.outro) h += '<div class="sm">'+md(st.outro)+'</div>';

  h += '<details><summary>How that was reached &middot; '+ev.slots.length+' slot(s) run</summary>'
    + ev.slots.map(function(s){ return '<div class="sm"><b style="color:var(--ink2)">'
        +(s.pass?'&#10003;':(s.indet?'&mdash;':'&#10007;'))+' Slot '+s.slot+' &middot; '
        +DATA.slots[String(s.slot)].label+'</b> — '+DATA.slots[String(s.slot)].question+'</div>'
        +'<div class="sm">'+s.reason+'</div>'; }).join('')
    +'<div class="sm">'+(4-ev.slots.length)+' slot(s) below the failure were NOT measured. That is the method, '
    +'not an omission — a reading taken below a failing slot cannot be interpreted.</div></details>';

  h += '<div class="btns"><button class="b ghost" onclick="reset()">Start again</button></div>';
  el(h);
}

reset();
</script>
"""

out = HTML.replace("__DATA__", DATA)
path = os.path.join(ROOT, "mockups", "flexibility_prototype.html")
io.open(path, "w", encoding="utf-8", newline="\n").write(out)
print("written", path)
print("tests:", len(tests), "stacks:", len(stacks), "release:", len(release))
