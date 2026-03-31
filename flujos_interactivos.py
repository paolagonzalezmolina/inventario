"""
flujos_interactivos.py
----------------------
Mapas interactivos de flujos AWS embebidos en Streamlit con streamlit.components.
Cada función retorna el HTML completo del mapa para renderizar con st.components.v1.html()
"""

def html_flujo_login() -> str:
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, sans-serif; }
  body { background: transparent; padding: 8px; }
  .controls { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .play-btn { font-size: 12px; padding: 5px 14px; cursor: pointer; border-radius: 6px;
    border: 1px solid #555; background: #2a2d3a; color: #e8eaf0; }
  .step-btn { font-size: 12px; padding: 5px 12px; cursor: pointer; border-radius: 6px;
    border: 1px solid #3a3e52; background: #1a1d27; color: #c8ccd4; transition: background 0.15s; }
  .step-btn:hover { background: #2a2d3a; }
  .step-btn.active { background: #1a3a5c; color: #7fb8f0; border-color: #3a7bd5; }
  .counter { font-size: 12px; color: #5a5e72; margin-left: auto; }
  .detail { border: 1px solid #2a2d3a; border-radius: 10px; padding: 14px 18px;
    margin-top: 12px; background: #1a1d27; min-height: 88px; }
  .detail h3 { font-size: 14px; font-weight: 500; color: #e8eaf0; margin-bottom: 4px; }
  .detail p  { font-size: 13px; color: #8b8fa8; line-height: 1.55; }
  .meta { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
  .badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-family: monospace; }
  .b-blue   { background:#0c2a4a; color:#7fb8f0; }
  .b-teal   { background:#0a2a1f; color:#3ecf8e; }
  .b-amber  { background:#2a1a05; color:#d4a017; }
  .b-purple { background:#1a1040; color:#a09ee0; }
  .b-green  { background:#0a2010; color:#5ecf8e; }
  .b-red    { background:#2a0a0a; color:#e05252; }
  @keyframes dash-flow { to { stroke-dashoffset: -24; } }
  .flowing { stroke-dasharray: 6 6; animation: dash-flow 0.5s linear infinite; }
</style>
</head>
<body>
<div class="controls">
  <button class="play-btn" id="playBtn" onclick="togglePlay()">&#9654; Auto</button>
  <button class="step-btn" onclick="goTo(0)" id="b0">Inicio</button>
  <button class="step-btn" onclick="goTo(1)" id="b1">1</button>
  <button class="step-btn" onclick="goTo(2)" id="b2">2</button>
  <button class="step-btn" onclick="goTo(3)" id="b3">3</button>
  <button class="step-btn" onclick="goTo(4)" id="b4">4</button>
  <button class="step-btn" onclick="goTo(5)" id="b5">5</button>
  <button class="step-btn" onclick="goTo(6)" id="b6">6</button>
  <button class="step-btn" onclick="goTo(7)" id="b7">Fin</button>
  <span class="counter" id="ctr">Paso 0 / 7</span>
</div>

<svg width="100%" viewBox="0 0 680 300" style="display:block">
<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>
<!-- nodes -->
<g id="n0"><rect x="10" y="112" width="90" height="56" rx="8" fill="#0a2a1f" stroke="#0F6E56" stroke-width="1.5"/><text x="55" y="137" text-anchor="middle" font-size="13" font-weight="500" fill="#3ecf8e">Usuario</text><text x="55" y="155" text-anchor="middle" font-size="11" fill="#1D9E75">Navegador</text></g>
<g id="n1"><rect x="150" y="112" width="110" height="56" rx="8" fill="#0c2a4a" stroke="#185FA5" stroke-width="0.5"/><text x="205" y="137" text-anchor="middle" font-size="13" font-weight="500" fill="#7fb8f0">Auth API</text><text x="205" y="155" text-anchor="middle" font-size="11" fill="#378ADD">API Gateway</text></g>
<g id="n2"><rect x="314" y="112" width="140" height="56" rx="8" fill="#2a1a05" stroke="#854F0B" stroke-width="0.5"/><text x="384" y="137" text-anchor="middle" font-size="13" font-weight="500" fill="#d4a017">auth-validator</text><text x="384" y="155" text-anchor="middle" font-size="11" fill="#854F0B">Lambda</text></g>
<g id="n3"><rect x="514" y="112" width="140" height="56" rx="8" fill="#1a1040" stroke="#534AB7" stroke-width="0.5"/><text x="584" y="137" text-anchor="middle" font-size="13" font-weight="500" fill="#a09ee0">prod-postgres</text><text x="584" y="155" text-anchor="middle" font-size="11" fill="#534AB7">RDS</text></g>
<g id="n4"><rect x="314" y="230" width="140" height="44" rx="8" fill="#0a2010" stroke="#3B6D11" stroke-width="0.5"/><text x="384" y="256" text-anchor="middle" font-size="12" font-weight="500" fill="#5ecf8e">Token JWT emitido</text></g>
<g id="n5"><rect x="514" y="230" width="140" height="44" rx="8" fill="#2a0a0a" stroke="#A32D2D" stroke-width="0.5"/><text x="584" y="256" text-anchor="middle" font-size="12" font-weight="500" fill="#e05252">Acceso denegado</text></g>
<!-- arrows -->
<line id="a1" x1="101" y1="140" x2="148" y2="140" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a2" x1="261" y1="140" x2="312" y2="140" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a3" x1="455" y1="140" x2="512" y2="140" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a4" x1="512" y1="156" x2="455" y2="156" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a5" x1="384" y1="169" x2="384" y2="228" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a6" x1="584" y1="169" x2="584" y2="228" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<path id="a7" d="M205 169 Q205 295 55 295 Q55 295 55 169" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" fill="none" opacity="0.3"/>
<!-- labels -->
<text id="l1" x="125" y="130" text-anchor="middle" font-size="10" fill="#378ADD" opacity="0">POST /login</text>
<text id="l2" x="288" y="130" text-anchor="middle" font-size="10" fill="#d4a017" opacity="0">invoca</text>
<text id="l3" x="484" y="130" text-anchor="middle" font-size="10" fill="#a09ee0" opacity="0">consulta</text>
<text id="l4" x="484" y="163" text-anchor="middle" font-size="10" fill="#a09ee0" opacity="0">responde</text>
<text id="l5" x="415" y="210" text-anchor="middle" font-size="10" fill="#5ecf8e" opacity="0">creds OK</text>
<text id="l6" x="615" y="210" text-anchor="middle" font-size="10" fill="#e05252" opacity="0">creds KO</text>
<text id="l7" x="105" y="290" text-anchor="middle" font-size="10" fill="#7fb8f0" opacity="0">JWT al navegador</text>
</svg>

<div class="detail" id="det">
  <h3 id="dT">Flujo de autenticación / login</h3>
  <p id="dD">Selecciona un paso o usa Auto para ver el recorrido completo.</p>
  <div class="meta" id="dM"></div>
</div>

<script>
const S = [
  {t:"Flujo de autenticación / login",d:"Selecciona un paso o usa Auto para ver el recorrido completo.",m:[],n:[],a:[],l:[]},
  {t:"Paso 1 — Usuario envía credenciales",d:"El navegador hace un POST /login con email y contraseña cifrados por HTTPS.",m:[["b-blue","POST /login"],["b-teal","HTTPS"]],n:["n0","n1"],a:["a1"],l:["l1"]},
  {t:"Paso 2 — Auth API enruta la petición",d:"API Gateway valida formato y enruta a la función Lambda auth-validator.",m:[["b-blue","API Gateway"],["b-amber","Lambda"]],n:["n1","n2"],a:["a2"],l:["l2"]},
  {t:"Paso 3 — Lambda consulta la BD",d:"auth-validator busca el usuario en prod-postgres y compara el hash bcrypt.",m:[["b-amber","Lambda"],["b-purple","PostgreSQL"],["b-teal","bcrypt"]],n:["n2","n3"],a:["a3"],l:["l3"]},
  {t:"Paso 4 — Base de datos responde",d:"RDS devuelve el registro. Lambda recibe el resultado y toma la decisión.",m:[["b-purple","RDS responde"],["b-amber","Lambda decide"]],n:["n3","n2"],a:["a4"],l:["l4"]},
  {t:"Paso 5a — Credenciales correctas",d:"Lambda genera Token JWT firmado con expiración. Acceso concedido.",m:[["b-green","JWT generado"],["b-teal","exp: 8h"],["b-green","200 OK"]],n:["n2","n4"],a:["a5"],l:["l5"]},
  {t:"Paso 5b — Credenciales incorrectas",d:"Usuario no existe o contraseña inválida. Lambda retorna 401 sin token.",m:[["b-red","401 Unauthorized"],["b-red","Sin token"]],n:["n2","n5"],a:["a6"],l:["l6"]},
  {t:"Paso 6 — JWT al navegador",d:"Auth API devuelve el JWT. Cada petición futura incluye Authorization: Bearer.",m:[["b-blue","Authorization: Bearer"],["b-teal","Sesión activa"]],n:["n1","n0"],a:["a7"],l:["l7"]}
];
const AN=["n0","n1","n2","n3","n4","n5"],AA=["a1","a2","a3","a4","a5","a6","a7"],AL=["l1","l2","l3","l4","l5","l6","l7"];
let cur=0,playing=false,timer=null;
function goTo(i){
  cur=i; const s=S[i];
  AN.forEach(id=>{const r=document.getElementById(id).querySelector('rect');r.style.opacity=s.n.includes(id)?'1':'0.2';});
  AA.forEach(id=>{const e=document.getElementById(id);const on=s.a.includes(id);e.style.opacity=on?'1':'0.15';e.style.stroke=on?'#3a7bd5':'#3a3e52';e.style.strokeWidth=on?'2':'1';if(on)e.classList.add('flowing');else e.classList.remove('flowing');});
  AL.forEach(id=>{document.getElementById(id).style.opacity=s.l.includes(id)?'1':'0';});
  document.getElementById('dT').textContent=s.t;
  document.getElementById('dD').textContent=s.d;
  document.getElementById('dM').innerHTML=s.m.map(([c,t])=>`<span class="badge ${c}">${t}</span>`).join('');
  document.querySelectorAll('.step-btn').forEach((b,idx)=>b.classList.toggle('active',idx===i));
  document.getElementById('ctr').textContent=`Paso ${i} / ${S.length-1}`;
}
function togglePlay(){playing=!playing;document.getElementById('playBtn').textContent=playing?'⏸ Pausar':'▶ Auto';if(playing){if(cur>=S.length-1)goTo(0);timer=setInterval(()=>{if(cur<S.length-1)goTo(cur+1);else{playing=false;clearInterval(timer);document.getElementById('playBtn').textContent='▶ Auto';}},2000);}else clearInterval(timer);}
goTo(0);
</script>
</body></html>
"""


def html_flujo_pago() -> str:
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, sans-serif; }
  body { background: transparent; padding: 8px; }
  .controls { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .play-btn { font-size: 12px; padding: 5px 14px; cursor: pointer; border-radius: 6px; border: 1px solid #555; background: #2a2d3a; color: #e8eaf0; }
  .step-btn { font-size: 12px; padding: 5px 12px; cursor: pointer; border-radius: 6px; border: 1px solid #3a3e52; background: #1a1d27; color: #c8ccd4; transition: background 0.15s; }
  .step-btn:hover { background: #2a2d3a; }
  .step-btn.active { background: #1a3a5c; color: #7fb8f0; border-color: #3a7bd5; }
  .counter { font-size: 12px; color: #5a5e72; margin-left: auto; }
  .detail { border: 1px solid #2a2d3a; border-radius: 10px; padding: 14px 18px; margin-top: 12px; background: #1a1d27; min-height: 88px; }
  .detail h3 { font-size: 14px; font-weight: 500; color: #e8eaf0; margin-bottom: 4px; }
  .detail p  { font-size: 13px; color: #8b8fa8; line-height: 1.55; }
  .meta { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
  .badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-family: monospace; }
  .b-blue{background:#0c2a4a;color:#7fb8f0} .b-teal{background:#0a2a1f;color:#3ecf8e}
  .b-amber{background:#2a1a05;color:#d4a017} .b-purple{background:#1a1040;color:#a09ee0}
  .b-green{background:#0a2010;color:#5ecf8e} .b-red{background:#2a0a0a;color:#e05252}
  .b-coral{background:#2a1008;color:#e07050}
  @keyframes dash-flow { to { stroke-dashoffset: -24; } }
  .flowing { stroke-dasharray: 6 6; animation: dash-flow 0.5s linear infinite; }
</style>
</head>
<body>
<div class="controls">
  <button class="play-btn" id="playBtn" onclick="togglePlay()">&#9654; Auto</button>
  <button class="step-btn" onclick="goTo(0)" id="b0">Inicio</button>
  <button class="step-btn" onclick="goTo(1)" id="b1">1</button>
  <button class="step-btn" onclick="goTo(2)" id="b2">2</button>
  <button class="step-btn" onclick="goTo(3)" id="b3">3</button>
  <button class="step-btn" onclick="goTo(4)" id="b4">4</button>
  <button class="step-btn" onclick="goTo(5)" id="b5">5</button>
  <button class="step-btn" onclick="goTo(6)" id="b6">6</button>
  <button class="step-btn" onclick="goTo(7)" id="b7">7</button>
  <button class="step-btn" onclick="goTo(8)" id="b8">Fin</button>
  <span class="counter" id="ctr">Paso 0 / 8</span>
</div>

<svg width="100%" viewBox="0 0 680 320" style="display:block">
<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>
<!-- Row 1: Usuario → REST API → payment-processor → Pasarela externa -->
<g id="n0"><rect x="10" y="50" width="90" height="56" rx="8" fill="#0a2a1f" stroke="#0F6E56" stroke-width="1.5"/><text x="55" y="75" text-anchor="middle" font-size="13" font-weight="500" fill="#3ecf8e">Usuario</text><text x="55" y="93" text-anchor="middle" font-size="11" fill="#1D9E75">Navegador</text></g>
<g id="n1"><rect x="150" y="50" width="110" height="56" rx="8" fill="#0c2a4a" stroke="#185FA5" stroke-width="0.5"/><text x="205" y="75" text-anchor="middle" font-size="13" font-weight="500" fill="#7fb8f0">REST API v2</text><text x="205" y="93" text-anchor="middle" font-size="11" fill="#378ADD">API Gateway</text></g>
<g id="n2"><rect x="314" y="50" width="140" height="56" rx="8" fill="#2a1a05" stroke="#854F0B" stroke-width="0.5"/><text x="384" y="75" text-anchor="middle" font-size="13" font-weight="500" fill="#d4a017">payment-processor</text><text x="384" y="93" text-anchor="middle" font-size="11" fill="#854F0B">Lambda</text></g>
<g id="n3"><rect x="514" y="50" width="140" height="56" rx="8" fill="#2a1008" stroke="#993C1D" stroke-width="0.5"/><text x="584" y="75" text-anchor="middle" font-size="13" font-weight="500" fill="#e07050">Pasarela</text><text x="584" y="93" text-anchor="middle" font-size="11" fill="#993C1D">Stripe / Transbank</text></g>
<!-- Row 2: prod-postgres (left center), email-sender (right center) -->
<g id="n4"><rect x="200" y="200" width="140" height="56" rx="8" fill="#1a1040" stroke="#534AB7" stroke-width="0.5"/><text x="270" y="225" text-anchor="middle" font-size="13" font-weight="500" fill="#a09ee0">prod-postgres</text><text x="270" y="243" text-anchor="middle" font-size="11" fill="#534AB7">RDS — pagos</text></g>
<g id="n5"><rect x="400" y="200" width="140" height="56" rx="8" fill="#0c2a4a" stroke="#185FA5" stroke-width="0.5"/><text x="470" y="225" text-anchor="middle" font-size="13" font-weight="500" fill="#7fb8f0">email-sender</text><text x="470" y="243" text-anchor="middle" font-size="11" fill="#378ADD">Lambda</text></g>
<!-- Resultado OK -->
<g id="n6"><rect x="200" y="290" width="140" height="40" rx="8" fill="#0a2010" stroke="#3B6D11" stroke-width="0.5"/><text x="270" y="312" text-anchor="middle" font-size="12" font-weight="500" fill="#5ecf8e">Pago confirmado</text></g>
<!-- Resultado Error -->
<g id="n7"><rect x="400" y="290" width="140" height="40" rx="8" fill="#2a0a0a" stroke="#A32D2D" stroke-width="0.5"/><text x="470" y="312" text-anchor="middle" font-size="12" font-weight="500" fill="#e05252">Pago rechazado</text></g>

<!-- Arrows -->
<line id="a1" x1="101" y1="78" x2="148" y2="78" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a2" x1="261" y1="78" x2="312" y2="78" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a3" x1="455" y1="78" x2="512" y2="78" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a4" x1="512" y1="94" x2="455" y2="94" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a5" x1="384" y1="107" x2="270" y2="198" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a6" x1="350" y1="107" x2="460" y2="198" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a7" x1="270" y1="257" x2="270" y2="288" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a8" x1="470" y1="257" x2="470" y2="288" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>

<!-- Labels -->
<text id="l1" x="125" y="68" text-anchor="middle" font-size="10" fill="#378ADD" opacity="0">POST /pay</text>
<text id="l2" x="288" y="68" text-anchor="middle" font-size="10" fill="#d4a017" opacity="0">invoca</text>
<text id="l3" x="484" y="68" text-anchor="middle" font-size="10" fill="#e07050" opacity="0">autorizar</text>
<text id="l4" x="484" y="100" text-anchor="middle" font-size="10" fill="#e07050" opacity="0">OK / KO</text>
<text id="l5" x="295" y="165" text-anchor="middle" font-size="10" fill="#a09ee0" opacity="0">registra pago</text>
<text id="l6" x="450" y="165" text-anchor="middle" font-size="10" fill="#7fb8f0" opacity="0">envía email</text>
<text id="l7" x="270" y="280" text-anchor="middle" font-size="10" fill="#5ecf8e" opacity="0">200 OK</text>
<text id="l8" x="470" y="280" text-anchor="middle" font-size="10" fill="#e05252" opacity="0">notifica</text>
</svg>

<div class="detail" id="det">
  <h3 id="dT">Flujo de pago / transacción</h3>
  <p id="dD">Selecciona un paso o usa Auto para ver el recorrido completo.</p>
  <div class="meta" id="dM"></div>
</div>

<script>
const S=[
  {t:"Flujo de pago / transacción",d:"Selecciona un paso o usa Auto para ver el recorrido completo.",m:[],n:[],a:[],l:[]},
  {t:"Paso 1 — Usuario inicia el pago",d:"El navegador envía POST /pay con los datos de la tarjeta cifrados (TLS). Requiere JWT válido en el header.",m:[["b-blue","POST /pay"],["b-teal","TLS"],["b-teal","JWT requerido"]],n:["n0","n1"],a:["a1"],l:["l1"]},
  {t:"Paso 2 — REST API v2 enruta",d:"API Gateway valida el JWT del usuario y reenvía la petición a la función Lambda payment-processor.",m:[["b-blue","Valida JWT"],["b-amber","Lambda"]],n:["n1","n2"],a:["a2"],l:["l2"]},
  {t:"Paso 3 — Lambda contacta la pasarela",d:"payment-processor envía los datos de tarjeta a Stripe o Transbank para autorización. Nunca se almacena el número de tarjeta.",m:[["b-amber","Lambda"],["b-coral","Stripe/Transbank"],["b-teal","PCI-DSS"]],n:["n2","n3"],a:["a3"],l:["l3"]},
  {t:"Paso 4 — Pasarela responde",d:"La pasarela externa retorna aprobado o rechazado con un código de transacción único.",m:[["b-coral","Autorización"],["b-amber","Lambda recibe"]],n:["n3","n2"],a:["a4"],l:["l4"]},
  {t:"Paso 5a — Registro en base de datos",d:"Si el pago fue aprobado, Lambda registra la transacción en prod-postgres con estado, monto y código de autorización.",m:[["b-purple","INSERT BD"],["b-green","estado: approved"]],n:["n2","n4"],a:["a5"],l:["l5"]},
  {t:"Paso 5b — Notificación por email",d:"Lambda dispara email-sender para enviar el comprobante de pago al correo del usuario.",m:[["b-blue","email-sender"],["b-teal","Comprobante"]],n:["n2","n5"],a:["a6"],l:["l6"]},
  {t:"Paso 6a — Pago confirmado",d:"Se registra exitosamente en BD. El usuario recibe 200 OK con el detalle de la transacción.",m:[["b-green","200 OK"],["b-green","Pago registrado"]],n:["n4","n6"],a:["a7"],l:["l7"]},
  {t:"Paso 6b — Pago rechazado",d:"La pasarela rechazó el cargo. email-sender notifica al usuario. La BD registra el intento fallido.",m:[["b-red","Rechazado"],["b-blue","Email enviado"]],n:["n5","n7"],a:["a8"],l:["l8"]}
];
const AN=["n0","n1","n2","n3","n4","n5","n6","n7"],AA=["a1","a2","a3","a4","a5","a6","a7","a8"],AL=["l1","l2","l3","l4","l5","l6","l7","l8"];
let cur=0,playing=false,timer=null;
function goTo(i){cur=i;const s=S[i];AN.forEach(id=>{const r=document.getElementById(id).querySelector('rect');r.style.opacity=s.n.includes(id)?'1':'0.2';});AA.forEach(id=>{const e=document.getElementById(id);const on=s.a.includes(id);e.style.opacity=on?'1':'0.15';e.style.stroke=on?'#3a7bd5':'#3a3e52';e.style.strokeWidth=on?'2':'1';if(on)e.classList.add('flowing');else e.classList.remove('flowing');});AL.forEach(id=>{document.getElementById(id).style.opacity=s.l.includes(id)?'1':'0';});document.getElementById('dT').textContent=s.t;document.getElementById('dD').textContent=s.d;document.getElementById('dM').innerHTML=s.m.map(([c,t])=>`<span class="badge ${c}">${t}</span>`).join('');document.querySelectorAll('.step-btn').forEach((b,idx)=>b.classList.toggle('active',idx===i));document.getElementById('ctr').textContent=`Paso ${i} / ${S.length-1}`;}
function togglePlay(){playing=!playing;document.getElementById('playBtn').textContent=playing?'⏸ Pausar':'▶ Auto';if(playing){if(cur>=S.length-1)goTo(0);timer=setInterval(()=>{if(cur<S.length-1)goTo(cur+1);else{playing=false;clearInterval(timer);document.getElementById('playBtn').textContent='▶ Auto';}},2000);}else clearInterval(timer);}
goTo(0);
</script>
</body></html>
"""


def html_flujo_web() -> str:
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, sans-serif; }
  body { background: transparent; padding: 8px; }
  .controls { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .play-btn { font-size: 12px; padding: 5px 14px; cursor: pointer; border-radius: 6px; border: 1px solid #555; background: #2a2d3a; color: #e8eaf0; }
  .step-btn { font-size: 12px; padding: 5px 12px; cursor: pointer; border-radius: 6px; border: 1px solid #3a3e52; background: #1a1d27; color: #c8ccd4; transition: background 0.15s; }
  .step-btn:hover { background: #2a2d3a; }
  .step-btn.active { background: #1a3a5c; color: #7fb8f0; border-color: #3a7bd5; }
  .counter { font-size: 12px; color: #5a5e72; margin-left: auto; }
  .detail { border: 1px solid #2a2d3a; border-radius: 10px; padding: 14px 18px; margin-top: 12px; background: #1a1d27; min-height: 88px; }
  .detail h3 { font-size: 14px; font-weight: 500; color: #e8eaf0; margin-bottom: 4px; }
  .detail p  { font-size: 13px; color: #8b8fa8; line-height: 1.55; }
  .meta { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
  .badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-family: monospace; }
  .b-blue{background:#0c2a4a;color:#7fb8f0} .b-teal{background:#0a2a1f;color:#3ecf8e}
  .b-amber{background:#2a1a05;color:#d4a017} .b-purple{background:#1a1040;color:#a09ee0}
  .b-green{background:#0a2010;color:#5ecf8e} .b-red{background:#2a0a0a;color:#e05252}
  @keyframes dash-flow { to { stroke-dashoffset: -24; } }
  .flowing { stroke-dasharray: 6 6; animation: dash-flow 0.5s linear infinite; }
</style>
</head>
<body>
<div class="controls">
  <button class="play-btn" id="playBtn" onclick="togglePlay()">&#9654; Auto</button>
  <button class="step-btn" onclick="goTo(0)" id="b0">Inicio</button>
  <button class="step-btn" onclick="goTo(1)" id="b1">1</button>
  <button class="step-btn" onclick="goTo(2)" id="b2">2</button>
  <button class="step-btn" onclick="goTo(3)" id="b3">3</button>
  <button class="step-btn" onclick="goTo(4)" id="b4">4</button>
  <button class="step-btn" onclick="goTo(5)" id="b5">5</button>
  <button class="step-btn" onclick="goTo(6)" id="b6">6</button>
  <button class="step-btn" onclick="goTo(7)" id="b7">Fin</button>
  <span class="counter" id="ctr">Paso 0 / 7</span>
</div>

<svg width="100%" viewBox="0 0 680 280" style="display:block">
<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>
<!-- Fila superior: Usuario → web-prod-01 → REST API v2 → api-server-01 -->
<g id="n0"><rect x="10" y="40" width="90" height="56" rx="8" fill="#0a2a1f" stroke="#0F6E56" stroke-width="1.5"/><text x="55" y="65" text-anchor="middle" font-size="13" font-weight="500" fill="#3ecf8e">Usuario</text><text x="55" y="83" text-anchor="middle" font-size="11" fill="#1D9E75">Navegador</text></g>
<g id="n1"><rect x="150" y="40" width="110" height="56" rx="8" fill="#0c2a4a" stroke="#185FA5" stroke-width="0.5"/><text x="205" y="65" text-anchor="middle" font-size="13" font-weight="500" fill="#7fb8f0">web-prod-01</text><text x="205" y="83" text-anchor="middle" font-size="11" fill="#378ADD">EC2 web server</text></g>
<g id="n2"><rect x="314" y="40" width="110" height="56" rx="8" fill="#0c2a4a" stroke="#185FA5" stroke-width="0.5"/><text x="369" y="65" text-anchor="middle" font-size="13" font-weight="500" fill="#7fb8f0">REST API v2</text><text x="369" y="83" text-anchor="middle" font-size="11" fill="#378ADD">API Gateway</text></g>
<g id="n3"><rect x="484" y="40" width="120" height="56" rx="8" fill="#0c2a4a" stroke="#185FA5" stroke-width="0.5"/><text x="544" y="65" text-anchor="middle" font-size="13" font-weight="500" fill="#7fb8f0">api-server-01</text><text x="544" y="83" text-anchor="middle" font-size="11" fill="#378ADD">EC2 backend</text></g>
<!-- Fila inferior: auth-validator → prod-postgres → prod-replica -->
<g id="n4"><rect x="80" y="180" width="130" height="56" rx="8" fill="#2a1a05" stroke="#854F0B" stroke-width="0.5"/><text x="145" y="205" text-anchor="middle" font-size="13" font-weight="500" fill="#d4a017">auth-validator</text><text x="145" y="223" text-anchor="middle" font-size="11" fill="#854F0B">Lambda</text></g>
<g id="n5"><rect x="270" y="180" width="140" height="56" rx="8" fill="#1a1040" stroke="#534AB7" stroke-width="0.5"/><text x="340" y="205" text-anchor="middle" font-size="13" font-weight="500" fill="#a09ee0">prod-postgres</text><text x="340" y="223" text-anchor="middle" font-size="11" fill="#534AB7">RDS escritura</text></g>
<g id="n6"><rect x="470" y="180" width="140" height="56" rx="8" fill="#1a1040" stroke="#534AB7" stroke-width="0.5"/><text x="540" y="205" text-anchor="middle" font-size="13" font-weight="500" fill="#a09ee0">prod-replica</text><text x="540" y="223" text-anchor="middle" font-size="11" fill="#534AB7">RDS solo lectura</text></g>

<!-- Arrows -->
<line id="a1" x1="101" y1="68" x2="148" y2="68" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a2" x1="261" y1="68" x2="312" y2="68" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a3" x1="425" y1="68" x2="482" y2="68" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a4" x1="205" y1="97" x2="145" y2="178" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a5" x1="544" y1="97" x2="370" y2="178" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<line id="a6" x1="544" y1="97" x2="540" y2="178" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" opacity="0.3"/>
<path id="a7" d="M205 97 Q205 260 55 260 Q55 260 55 97" stroke="#3a3e52" stroke-width="1" marker-end="url(#arr)" fill="none" opacity="0.3"/>

<!-- Labels -->
<text id="l1" x="125" y="58" text-anchor="middle" font-size="10" fill="#378ADD" opacity="0">GET página</text>
<text id="l2" x="288" y="58" text-anchor="middle" font-size="10" fill="#378ADD" opacity="0">GET /data</text>
<text id="l3" x="454" y="58" text-anchor="middle" font-size="10" fill="#378ADD" opacity="0">petición</text>
<text id="l4" x="155" y="150" text-anchor="middle" font-size="10" fill="#d4a017" opacity="0">verifica JWT</text>
<text id="l5" x="420" y="155" text-anchor="middle" font-size="10" fill="#a09ee0" opacity="0">escribe</text>
<text id="l6" x="575" y="150" text-anchor="middle" font-size="10" fill="#a09ee0" opacity="0">lee datos</text>
<text id="l7" x="95" y="255" text-anchor="middle" font-size="10" fill="#7fb8f0" opacity="0">HTML al navegador</text>
</svg>

<div class="detail" id="det">
  <h3 id="dT">Flujo de carga de página web principal</h3>
  <p id="dD">Selecciona un paso o usa Auto para ver el recorrido completo.</p>
  <div class="meta" id="dM"></div>
</div>

<script>
const S=[
  {t:"Flujo de carga de página web principal",d:"Selecciona un paso o usa Auto para ver el recorrido completo.",m:[],n:[],a:[],l:[]},
  {t:"Paso 1 — Usuario solicita la página",d:"El navegador hace GET a la URL. La petición llega a web-prod-01 (EC2), que sirve el HTML/JS inicial.",m:[["b-blue","GET /"],["b-teal","HTTPS"],["b-blue","EC2"]],n:["n0","n1"],a:["a1"],l:["l1"]},
  {t:"Paso 2 — Frontend pide datos a la API",d:"El JavaScript cargado hace GET a REST API v2 para obtener los datos dinámicos de la página.",m:[["b-blue","GET /api/data"],["b-blue","REST API v2"]],n:["n1","n2"],a:["a2"],l:["l2"]},
  {t:"Paso 3 — API Gateway enruta al backend",d:"REST API v2 valida la petición y la reenvía a api-server-01 (EC2 backend) para procesarla.",m:[["b-blue","API Gateway"],["b-blue","api-server-01"]],n:["n2","n3"],a:["a3"],l:["l3"]},
  {t:"Paso 4 — Validación del token",d:"web-prod-01 llama a auth-validator (Lambda) para verificar el JWT del usuario antes de mostrar contenido protegido.",m:[["b-amber","Lambda"],["b-teal","Verifica JWT"],["b-teal","Token válido"]],n:["n1","n4"],a:["a4"],l:["l4"]},
  {t:"Paso 5a — Escritura en base de datos",d:"Si la acción del usuario requiere guardar datos (ej: guardar preferencias), api-server-01 escribe en prod-postgres.",m:[["b-purple","RDS escritura"],["b-purple","prod-postgres"]],n:["n3","n5"],a:["a5"],l:["l5"]},
  {t:"Paso 5b — Lectura de datos",d:"Para consultas y listados, api-server-01 lee desde prod-replica (réplica de solo lectura) para no sobrecargar el master.",m:[["b-purple","RDS lectura"],["b-purple","prod-replica"],["b-teal","Solo lectura"]],n:["n3","n6"],a:["a6"],l:["l6"]},
  {t:"Paso 6 — Página renderizada al usuario",d:"web-prod-01 combina HTML estático + datos de la API y devuelve la página completa al navegador.",m:[["b-blue","200 OK"],["b-green","Página lista"],["b-teal","~145ms latencia"]],n:["n1","n0"],a:["a7"],l:["l7"]}
];
const AN=["n0","n1","n2","n3","n4","n5","n6"],AA=["a1","a2","a3","a4","a5","a6","a7"],AL=["l1","l2","l3","l4","l5","l6","l7"];
let cur=0,playing=false,timer=null;
function goTo(i){cur=i;const s=S[i];AN.forEach(id=>{const r=document.getElementById(id).querySelector('rect');r.style.opacity=s.n.includes(id)?'1':'0.2';});AA.forEach(id=>{const e=document.getElementById(id);const on=s.a.includes(id);e.style.opacity=on?'1':'0.15';e.style.stroke=on?'#3a7bd5':'#3a3e52';e.style.strokeWidth=on?'2':'1';if(on)e.classList.add('flowing');else e.classList.remove('flowing');});AL.forEach(id=>{document.getElementById(id).style.opacity=s.l.includes(id)?'1':'0';});document.getElementById('dT').textContent=s.t;document.getElementById('dD').textContent=s.d;document.getElementById('dM').innerHTML=s.m.map(([c,t])=>`<span class="badge ${c}">${t}</span>`).join('');document.querySelectorAll('.step-btn').forEach((b,idx)=>b.classList.toggle('active',idx===i));document.getElementById('ctr').textContent=`Paso ${i} / ${S.length-1}`;}
function togglePlay(){playing=!playing;document.getElementById('playBtn').textContent=playing?'⏸ Pausar':'▶ Auto';if(playing){if(cur>=S.length-1)goTo(0);timer=setInterval(()=>{if(cur<S.length-1)goTo(cur+1);else{playing=false;clearInterval(timer);document.getElementById('playBtn').textContent='▶ Auto';}},2000);}else clearInterval(timer);}
goTo(0);
</script>
</body></html>
"""
