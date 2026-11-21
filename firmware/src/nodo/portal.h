// Página del portal Wi-Fi del nodo de albergue. Todo va incluido: no usa internet.
#pragma once
#include <Arduino.h>

static const char PORTAL_HTML[] PROGMEM = R"HTML(<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Red de Emergencia</title>
<style>
:root{--r:#d62828;--b:#2563eb;--t:#1b2130;--m:#5f6878;--l:#e2e5ea;--bg:#f6f7f9}
*{box-sizing:border-box}body{margin:0;font:16px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--t)}
header{background:var(--r);color:#fff;padding:14px 16px}header h1{margin:0;font-size:19px}
header p{margin:2px 0 0;font-size:13px;opacity:.9}main{padding:14px 16px;max-width:520px;margin:0 auto}
.card{background:#fff;border:1px solid var(--l);border-radius:12px;padding:12px;margin-bottom:12px}
.e{display:flex;justify-content:space-between;font-size:14px;color:var(--m)}
.q{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}
button{font:inherit;border:1px solid var(--l);background:#fff;border-radius:10px;padding:11px}
.sos{background:var(--r);color:#fff;border:0;font-weight:700;font-size:20px;width:100%;padding:16px}
.env{background:var(--b);color:#fff;border:0}textarea{width:100%;font:inherit;border:1px solid var(--l);border-radius:10px;padding:10px;resize:none}
.row{display:flex;gap:8px;align-items:center}.row>*{flex:1}small{color:var(--m)}
#estado{font-size:14px;margin:6px 0 0}.ok{color:#2f9e44}.err{color:var(--r)}
ul{list-style:none;padding:0;margin:0}li{border-top:1px solid var(--l);padding:8px 0;font-size:15px}
li b{font-size:13px;color:var(--m);display:block}
</style></head><body>
<header><h1 id="nombre">Red de Emergencia</h1><p>Sin internet: tu mensaje viaja por radio al puesto de mando</p></header>
<main>
<div class="card"><div class="e"><span id="bat">🔋 —</span><span id="panel">☀️ —</span><span id="con">📱 —</span></div></div>
<div class="card">
<button class="sos" onclick="enviar('SOS Necesito ayuda')">🆘 SOS — Necesito ayuda</button>
<div class="q">
<button onclick="enviar('SOS Herido')">🩸 Herido</button><button onclick="enviar('SOS Atrapado')">🧱 Atrapado</button>
<button onclick="enviar('Necesito agua')">💧 Agua</button><button onclick="enviar('Necesito medicina')">💊 Medicina</button>
<button onclick="enviar('Evacuando')">🏃 Evacuando</button><button onclick="enviar('Estoy bien')">✅ Estoy bien</button>
</div>
<textarea id="txt" rows="2" placeholder="Escribe un reporte corto…" oninput="contar()"></textarea>
<div class="row"><small id="cnt">0/36</small><button class="env" onclick="enviar(document.getElementById('txt').value)">Enviar</button></div>
<p id="estado"></p>
</div>
<div class="card"><b>Mensajes</b><ul id="lista"></ul></div>
</main>
<script>
var MAX=36,ult=0,enc=new TextEncoder();
function $(i){return document.getElementById(i)}
function contar(){var n=enc.encode($('txt').value.trim()).length;$('cnt').textContent=n+'/'+MAX;$('cnt').className=n>MAX?'err':''}
function estado(t,ok){$('estado').textContent=t;$('estado').className=ok?'ok':'err'}
function enviar(t){t=(t||'').trim();if(!t)return;if(enc.encode(t).length>MAX){estado('Máximo '+MAX+' caracteres',false);return}
if(t.indexOf('SOS')===0&&!confirm('¿Enviar "'+t+'" al puesto de mando?'))return;
estado('Enviando por radio…',true);
fetch('/api/mensaje',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({msg:t})})
.then(function(r){return r.json()}).then(function(d){if(d.ok){estado('✓ Recibido por la red',true);$('txt').value='';contar();cargar()}else estado('✗ '+(d.error||'No se pudo enviar'),false)})
.catch(function(){estado('✗ Sin conexión con el nodo',false)})}
function quien(m){return m.propio?'Este albergue':m.de===1?'Puesto de mando':'Nodo '+m.de}
function cargar(){fetch('/api/mensajes?desde='+ult).then(function(r){return r.json()}).then(function(d){
d.mensajes.forEach(function(m){var li=document.createElement('li'),b=document.createElement('b');
b.textContent=quien(m)+' · hace '+m.hace+' s';li.appendChild(b);li.appendChild(document.createTextNode(m.msg));
$('lista').insertBefore(li,$('lista').firstChild)});ult=d.ultimo}).catch(function(){})}
function est(){fetch('/api/estado').then(function(r){return r.json()}).then(function(d){
$('nombre').textContent=d.nombre;MAX=d.max_texto||MAX;$('bat').textContent='🔋 '+d.carga+'% ('+d.bat.toFixed(1)+' V)';
$('panel').textContent=d.panel>1?'☀️ '+d.panel.toFixed(1)+' V':'🌙 sin sol';$('con').textContent='📱 '+d.conectados;contar()}).catch(function(){})}
est();cargar();setInterval(cargar,4000);setInterval(est,15000);
</script></body></html>)HTML";
