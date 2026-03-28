// ═══════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════
let carrito = []; // [{producto_id, nombre, codigo, categoria, precio, cantidad, imagen_url, descuento:{tipo,valor}, es_custom, observaciones}]
let productos = [];
let categorias = [];
let vistaActual = localStorage.getItem('pos_vista_catalogo') || 'grid';
let ivaActivo = false;
let iepsActivo = false;
let descGlobal = null; // {tipo:'%'|'$', valor:X}
let ordenTipo = null; // mostrador|domicilio|recoger|funeral
let clienteSel = null; // {id, nombre, telefono, primera_compra}
let funerariaSel = null; // {id, nombre, zona, costo_envio}
let geoData = null; // {lat, lng, ruta, zona_envio, tarifa_envio}
let dirVerificada = false;
let selHorario = null;
let horaEspecifica = '';
let selectedPays = {}; // {nombre: monto}
let lastResult = null;
let lastCarritoSnap = [];
let allFunerarias = [];
let editingPedidoId = null; // when editing a pending order
let contadorPendientes = 0;
let debounceTimer = null;
let debounceCliTimer = null;
let debounceCliSearchTimer = null;

// ═══════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════
function navTo(sec) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.sb-item').forEach(s => s.classList.remove('active'));
  document.getElementById('sec-' + sec).classList.add('active');
  document.getElementById('sb-' + sec).classList.add('active');
  if (sec === 'pendientes') loadPendientes();
  if (sec === 'transacciones') loadTransacciones();
}

function goWin(n) {
  document.querySelectorAll('.venta-win').forEach(w => w.classList.remove('active'));
  document.getElementById('win' + n).classList.add('active');
  if (n === 3) { buildW3Form(); updateSummary(); }
}

function selTipo(t) {
  ordenTipo = t;
  goWin(3);
}

// ═══════════════════════════════════════════
// CATALOG
// ═══════════════════════════════════════════
function setView(v) {
  vistaActual = v;
  localStorage.setItem('pos_vista_catalogo', v);
  document.getElementById('vt-grid').classList.toggle('active', v === 'grid');
  document.getElementById('vt-list').classList.toggle('active', v === 'lista');
  renderProds();
}

function debounceFetchProds() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(fetchProds, 300);
}

async function fetchProds() {
  const q = document.getElementById('cat-search').value;
  const cat = document.getElementById('cat-filter').value;
  try {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (cat) params.set('categoria', cat);
    const r = await fetch('/pos/productos?' + params);
    productos = await r.json();
    renderProds();
  } catch(e) { console.error('Error fetching products', e); }
}

async function fetchCategorias() {
  try {
    const r = await fetch('/pos/productos/categorias');
    categorias = await r.json();
    const sel = document.getElementById('cat-filter');
    sel.innerHTML = '<option value="">Todas</option>';
    categorias.forEach(c => {
      sel.innerHTML += `<option value="${c.categoria}">${c.categoria} (${c.count})</option>`;
    });
  } catch(e) { console.error(e); }
}

function renderProds() {
  const c = document.getElementById('prod-container');
  if (vistaActual === 'grid') {
    c.className = 'prod-grid';
    c.innerHTML = productos.map(p => {
      const nostock = p.disponible_hoy === false ? ' sinstock' : '';
      const price = p.precio_descuento
        ? `<span class="old">$${(p.precio/100).toLocaleString()}</span><span class="offer">$${(p.precio_descuento/100).toLocaleString()}</span>`
        : `$${(p.precio/100).toLocaleString()}`;
      return `<div class="pcard${nostock}" onclick="addToCart(${p.id})">
        <img src="${p.imagen_url}" loading="lazy" alt="">
        <div class="pinfo"><div class="pname">${p.nombre}</div><div class="pprice">${price}</div></div>
      </div>`;
    }).join('');
  } else {
    c.className = 'prod-grid lista';
    c.innerHTML = productos.map(p => {
      const nostock = p.disponible_hoy === false ? ' sinstock' : '';
      const pr = p.precio_descuento || p.precio;
      const stockVal = p.stock != null ? p.stock : (p.disponible_hoy === false ? 0 : null);
      let stockHtml = '';
      if (stockVal === 0 || p.disponible_hoy === false) {
        stockHtml = '<div class="plstock" style="color:var(--rojo);font-weight:600">Sin stock</div>';
      } else if (stockVal != null && stockVal <= 3) {
        stockHtml = `<div class="plstock" style="color:#e65100;font-weight:600">${stockVal}</div>`;
      } else if (stockVal != null) {
        stockHtml = `<div class="plstock" style="color:var(--texto2)">${stockVal}</div>`;
      } else {
        stockHtml = '<div class="plstock" style="color:var(--texto2)">—</div>';
      }
      const btnDisabled = (stockVal === 0 || p.disponible_hoy === false);
      return `<div class="pcard-list${nostock}" onclick="${btnDisabled ? '' : `addToCart(${p.id})`}">
        <img src="${p.imagen_url}" alt="">
        <div class="plname">${p.nombre}</div>
        <div class="plcode">${p.codigo||''}</div>
        <div class="plprice">$${(pr/100).toLocaleString()}</div>
        ${stockHtml}
        <button class="plbtn"${btnDisabled ? ' disabled style="opacity:.4;cursor:not-allowed"' : ''}>+</button>
      </div>`;
    }).join('');
  }
}

// ═══════════════════════════════════════════
// CART
// ═══════════════════════════════════════════
function addToCart(prodId) {
  const p = productos.find(x => x.id === prodId);
  if (!p) return;
  const existing = carrito.find(x => x.producto_id === prodId && !x.es_custom);
  if (existing) { existing.cantidad++; }
  else {
    carrito.push({
      producto_id: p.id, nombre: p.nombre, codigo: p.codigo, categoria: p.categoria,
      precio: p.precio_descuento || p.precio, cantidad: 1, imagen_url: p.imagen_url,
      descuento: null, es_custom: false, observaciones: null
    });
  }
  renderCart();
}

function abrirModalRayo() { document.getElementById('modal-rayo').classList.add('active'); }
function agregarRayo() {
  const nombre = document.getElementById('rayo-nombre').value.trim();
  const precio = Math.round(parseFloat(document.getElementById('rayo-precio').value || 0) * 100);
  const obs = document.getElementById('rayo-obs').value.trim();
  if (!nombre || precio <= 0) return;
  carrito.push({
    producto_id: null, nombre, codigo: null, categoria: 'Custom', precio, cantidad: 1,
    imagen_url: null, descuento: null, es_custom: true, observaciones: obs || null
  });
  document.getElementById('rayo-nombre').value = '';
  document.getElementById('rayo-precio').value = '';
  document.getElementById('rayo-obs').value = '';
  document.getElementById('modal-rayo').classList.remove('active');
  renderCart();
}

function changeQty(idx, delta) {
  carrito[idx].cantidad += delta;
  if (carrito[idx].cantidad < 1) carrito.splice(idx, 1);
  renderCart();
}

function removeItem(idx) { carrito.splice(idx, 1); renderCart(); }

function toggleItemDisc(idx) {
  const row = document.getElementById('ci-disc-' + idx);
  row.style.display = row.style.display === 'none' ? 'flex' : 'none';
}

function applyItemDisc(idx) {
  const val = parseFloat(document.getElementById('cid-val-' + idx).value || 0);
  const tipo = document.getElementById('cid-tipo-' + idx).value;
  if (val <= 0) return;
  carrito[idx].descuento = { tipo, valor: val };
  renderCart();
}

function clearItemDisc(idx) {
  carrito[idx].descuento = null;
  renderCart();
}

function getItemFinalPrice(item) {
  let price = item.precio * item.cantidad;
  if (item.descuento) {
    if (item.descuento.tipo === '%') price = Math.round(price * (1 - item.descuento.valor / 100));
    else price = price - Math.round(item.descuento.valor * 100);
  }
  return Math.max(0, price);
}

function calcTotals() {
  const subtotal = carrito.reduce((s, it) => s + getItemFinalPrice(it), 0);
  const iva = ivaActivo ? Math.round(subtotal * 0.16) : 0;
  const ieps = iepsActivo ? Math.round(subtotal * 0.08) : 0; // display only
  let descGlobalAmt = 0;
  if (descGlobal) {
    if (descGlobal.tipo === '%') descGlobalAmt = Math.round(subtotal * descGlobal.valor / 100);
    else descGlobalAmt = Math.round(descGlobal.valor * 100);
  }
  // Shipping
  let envio = 0;
  if (ordenTipo === 'domicilio') {
    if (geoData && geoData.tarifa_envio) envio = geoData.tarifa_envio;
    else {
      const zonaEl = document.getElementById('f-zona');
      if (zonaEl) {
        const z = zonaEl.value;
        const tarifas = {Morada: 9900, Azul: 15900, Verde: 19900};
        envio = tarifas[z] || 0;
      }
    }
  }
  if (ordenTipo === 'funeral' && funerariaSel) envio = funerariaSel.costo_envio;
  // Link pago commission
  let comision = 0;
  if (selectedPays['Link de pago']) comision = Math.round((selectedPays['Link de pago'] || 0) * 0.04);
  // Cargo hora específica
  let cargoHora = 0;
  if (selHorario === 'hora_especifica') cargoHora = 8000; // $80 en centavos
  const total = subtotal + iva - descGlobalAmt + envio + comision + cargoHora;
  return { subtotal, iva, ieps, descGlobalAmt, envio, comision, cargoHora, total };
}

function renderCart() {
  const container = document.getElementById('cart-items');
  if (carrito.length === 0) {
    container.innerHTML = '<div class="cart-empty"><span class="ico">🛒</span>Selecciona productos del catalogo</div>';
  } else {
    container.innerHTML = carrito.map((it, i) => {
      const fp = getItemFinalPrice(it);
      const orig = it.precio * it.cantidad;
      const hasDisc = it.descuento && fp < orig;
      const priceHtml = hasDisc
        ? `<span class="old">$${(orig/100).toLocaleString()}</span><span class="disc">$${(fp/100).toLocaleString()}</span>`
        : `$${(fp/100).toLocaleString()}`;
      const discBtn = it.descuento
        ? `<button class="ci-disc-btn" onclick="clearItemDisc(${i})">× Quitar descuento</button>`
        : `<button class="ci-disc-btn" onclick="toggleItemDisc(${i})">Descuento</button>`;
      return `<div class="ci">
        <div class="ciinfo">
          <div class="ciname">${it.nombre}${it.es_custom?' ⚡':''}</div>
          ${it.codigo ? `<div class="cicode">${it.codigo}</div>` : ''}
          <div class="ciprice">${priceHtml}</div>
          ${discBtn}
          <div class="ci-disc-row" id="ci-disc-${i}" style="display:none">
            <input type="number" id="cid-val-${i}" placeholder="0" step="any">
            <select id="cid-tipo-${i}"><option value="%">%</option><option value="$">$</option></select>
            <button onclick="applyItemDisc(${i})">OK</button>
          </div>
        </div>
        <div class="ci-qty">
          <button onclick="changeQty(${i},-1)">−</button>
          <span>${it.cantidad}</span>
          <button onclick="changeQty(${i},1)">+</button>
        </div>
        <button class="ci-del" onclick="removeItem(${i})">×</button>
      </div>`;
    }).join('');
  }
  renderCartTotals();
}

function renderCartTotals() {
  const t = calcTotals();
  const n = carrito.reduce((s, it) => s + it.cantidad, 0);
  let html = `<div class="ct-line"><span>${n} items</span><span>Subtotal: $${(t.subtotal/100).toLocaleString()}</span></div>`;
  html += '<div class="ct-chips">';
  html += `<span class="ct-chip${ivaActivo?' active':''}" onclick="toggleIva()">× IVA (16%): $${(t.iva/100).toLocaleString()}</span>`;
  html += `<span class="ct-chip ieps${iepsActivo?' active':''}" onclick="toggleIeps()">× IEPS (8%): $${(t.ieps/100).toLocaleString()}</span>`;
  html += '</div>';
  if (descGlobal) {
    html += `<div class="ct-line" style="color:var(--dorado)"><span>Descuento ${descGlobal.tipo==='%'?descGlobal.valor+'%':'$'+(descGlobal.valor).toLocaleString()}</span><span>-$${(t.descGlobalAmt/100).toLocaleString()}</span></div>`;
    html += `<button class="ct-disc-link" onclick="clearGlobalDisc()">× Quitar descuento global</button>`;
  } else {
    html += `<button class="ct-disc-link" onclick="toggleGlobalDiscInput()">Dar descuento</button>`;
    html += `<div class="ct-disc-row" id="gdisc-row" style="display:none"><input type="number" id="gdisc-val" placeholder="0" step="any"><select id="gdisc-tipo"><option value="%">%</option><option value="$">$</option></select><button onclick="applyGlobalDisc()">Aplicar</button></div>`;
  }
  html += `<div class="ct-line total"><span>TOTAL</span><span>$${(t.total/100).toLocaleString()}</span></div>`;
  html += `<button class="btn-continuar" ${carrito.length===0?'disabled':''} onclick="goWin(2)">Continuar orden →</button>`;
  document.getElementById('cart-totals').innerHTML = html;
}

function toggleIva() { ivaActivo = !ivaActivo; renderCart(); }
function toggleIeps() { iepsActivo = !iepsActivo; renderCart(); }
function toggleGlobalDiscInput() {
  const r = document.getElementById('gdisc-row');
  if (r) r.style.display = r.style.display === 'none' ? 'flex' : 'none';
}
function applyGlobalDisc() {
  const v = parseFloat(document.getElementById('gdisc-val').value || 0);
  const t = document.getElementById('gdisc-tipo').value;
  if (v > 0) { descGlobal = { tipo: t, valor: v }; renderCart(); }
}
function clearGlobalDisc() { descGlobal = null; renderCart(); }

// ═══════════════════════════════════════════
// WINDOW 3 — FORM BUILDER
// ═══════════════════════════════════════════
function buildW3Form() {
  const badge = document.getElementById('w3-tipo-badge');
  const labels = {mostrador:'🏪 Mostrador',domicilio:'🚚 Domicilio',recoger:'🛍 Recoger',funeral:'🌹 Funeral'};
  badge.textContent = labels[ordenTipo] || ordenTipo;
  let html = '';

  // Funeral warning
  if (ordenTipo === 'funeral') {
    const nonFun = carrito.filter(it => !it.es_custom && it.categoria && it.categoria.toLowerCase() !== 'funeral');
    if (nonFun.length) {
      html += `<div style="background:#fce4e4;color:var(--rojo);padding:10px;border-radius:8px;margin-bottom:12px;font-size:12px;font-weight:600">⚠ Productos no-funeral en el carrito: ${nonFun.map(x=>x.nombre).join(', ')}. Solo productos de categoria funeral son permitidos.</div>`;
    }
  }

  // Client box (domicilio, recoger, funeral)
  if (['domicilio','recoger','funeral'].includes(ordenTipo)) {
    html += '<div class="fbox"><h4>Cliente</h4>';
    html += '<div id="w3-cliente-box">';
    if (clienteSel) {
      html += `<div class="client-sel">
        <div><div class="cname">${clienteSel.nombre}</div><div class="cphone">${clienteSel.telefono}</div></div>
        <button class="cbtn" onclick="abrirBuscarCliente()">Cambiar</button>
      </div>`;
    } else {
      html += `<div class="client-box" onclick="abrirBuscarCliente()">Seleccionar o registrar cliente</div>`;
    }
    html += '</div></div>';
  }

  // Delivery data (domicilio)
  if (ordenTipo === 'domicilio') {
    html += `<div class="fbox"><h4>Datos de entrega</h4>
      <div class="frow" id="fr-rec-nombre"><label>Nombre de quien recibe *</label><input type="text" id="f-rec-nombre"><div class="errmsg">Campo obligatorio</div></div>
      <div class="frow" id="fr-rec-tel"><label>Telefono de quien recibe *</label><input type="tel" id="f-rec-tel"><div class="errmsg">Campo obligatorio</div></div>
      <div class="frow" id="fr-dir"><label>Direccion *</label>
        <div style="display:flex;gap:6px"><input type="text" id="f-dir" style="flex:1"><button onclick="verificarMaps()" style="padding:6px 10px;background:#fff;border:1px solid var(--borde);border-radius:6px;font-size:12px;white-space:nowrap">📍 Verificar</button></div>
        <div class="errmsg">Campo obligatorio</div>
      </div>
      <div style="margin:6px 0">
        <label style="font-size:12px;display:flex;align-items:center;gap:6px;cursor:pointer">
          <input type="checkbox" id="f-dir-check" onchange="onDirVerificada()"> ✓ Direccion verificada
        </label>
        <div id="geo-badge" style="margin-top:4px"></div>
      </div>
      <div class="frow"><label>Notas para el repartidor</label><textarea id="f-notas" rows="2" placeholder="Porton negro, tocar timbre..."></textarea></div>
      <div class="frow"><label>Dedicatoria</label><textarea id="f-dedicatoria" rows="2" placeholder="Opcional"></textarea></div>
    </div>`;

    // Date and schedule
    html += `<div class="fbox"><h4>Fecha y horario</h4>
      <div class="frow" id="fr-fecha"><label>Fecha de entrega *</label><input type="date" id="f-fecha" min="${todayStr()}" value="${todayStr()}"><div class="errmsg">Campo obligatorio</div></div>
      <div class="frow" id="fr-horario"><label>Horario de entrega *</label>
        <div class="hor-btns">
          <div class="hor-btn" onclick="selHorarioBtn(this,'manana')">Manana (9-2pm)</div>
          <div class="hor-btn" onclick="selHorarioBtn(this,'tarde')">Tarde (2-6pm)</div>
          <div class="hor-btn" onclick="selHorarioBtn(this,'noche')">Noche (6-9pm)</div>
          <div class="hor-btn" onclick="selHorarioBtn(this,'hora_especifica')">Hora especifica</div>
        </div>
        <div id="hora-esp-wrap" style="display:none;margin-top:6px">
          <select id="f-hora-esp" onchange="horaEspecifica=this.value" style="width:100%;padding:8px 10px;border:1px solid var(--borde);border-radius:6px;font-size:13px">${buildHoraOptions()}</select>
          <div style="font-size:11px;color:var(--texto2);margin-top:2px">Minimo 2 hrs de anticipacion</div>
        </div>
        <div class="errmsg">Selecciona un horario</div>
      </div>
    </div>`;

    // Zona de envio
    html += `<div class="fbox"><h4>Zona de envio</h4>
      <div id="zona-auto" style="margin-bottom:8px"></div>
      <div class="frow"><label>Zona</label>
        <select id="f-zona" onchange="onZonaChange()">
          <option value="">Seleccionar...</option>
          <option value="Morada">Morada — $99</option>
          <option value="Azul">Azul — $159</option>
          <option value="Verde">Verde — $199</option>
        </select>
      </div>
    </div>`;
  }

  // Funeral data
  if (ordenTipo === 'funeral') {
    html += `<div class="fbox"><h4>Datos del funeral</h4>
      <div class="frow" id="fr-funeraria"><label>Funeraria *</label>
        <div id="w3-fun-box">
          ${funerariaSel ? `<div class="client-sel"><div class="cname">${funerariaSel.nombre}</div><div class="cphone">${funerariaSel.zona} — $${funerariaSel.costo_envio/100}</div><button class="cbtn" onclick="abrirBuscarFuneraria()">Cambiar</button></div>` : `<div class="client-box" onclick="abrirBuscarFuneraria()">Seleccionar funeraria</div>`}
        </div>
        <div class="errmsg">Selecciona una funeraria</div>
      </div>
      <div class="frow" id="fr-fallecido"><label>Nombre del fallecido *</label><input type="text" id="f-fallecido"><div class="errmsg">Campo obligatorio</div></div>
      <div class="frow"><label>Sala</label><input type="text" id="f-sala"></div>
      <div class="frow"><label>Texto banda</label><input type="text" id="f-banda"></div>
      <div class="frow"><label>Dedicatoria</label><textarea id="f-dedicatoria-fun" rows="2" placeholder="Opcional"></textarea></div>
      <div class="frow" id="fr-fecha-fun"><label>Fecha de entrega *</label><input type="date" id="f-fecha-fun" min="${todayStr()}" value="${todayStr()}"><div class="errmsg">Campo obligatorio</div></div>
      <div class="frow"><label>Horario velacion</label>
        <div class="hor-btns">
          <div class="hor-btn" onclick="selHorVelacion(this,'ya_inicio')">Ya inicio</div>
          <div class="hor-btn" onclick="selHorVelacion(this,'hora')">Inicia a las...</div>
        </div>
        <div id="vel-hora-wrap" style="display:none;margin-top:6px"><select id="f-vel-hora" style="width:100%;padding:8px 10px;border:1px solid var(--borde);border-radius:6px;font-size:13px">${buildHoraOptions()}</select></div>
      </div>
    </div>`;
  }

  // Recoger data
  if (ordenTipo === 'recoger') {
    html += `<div class="fbox"><h4>Datos de recogida</h4>
      <div class="frow" id="fr-fecha-rec"><label>¿Cuando pasa a recoger? *</label><input type="date" id="f-fecha-rec" min="${todayStr()}" value="${todayStr()}"><div class="errmsg">Campo obligatorio</div></div>
      <div class="frow" id="fr-hora-rec"><label>Hora *</label><select id="f-hora-rec" style="width:100%;padding:8px 10px;border:1px solid var(--borde);border-radius:6px;font-size:13px">${buildHoraOptions()}</select><div class="errmsg">Campo obligatorio</div></div>
    </div>`;
  }

  // Payment (always)
  html += `<div class="fbox"><h4>Metodo de pago</h4>
    <div class="pay-chips" id="pay-chips">
      <div class="pay-chip" onclick="togglePay(this,'Efectivo')">Efectivo</div>
      <div class="pay-chip" onclick="togglePay(this,'Tarjeta debito')">Tarjeta debito</div>
      <div class="pay-chip" onclick="togglePay(this,'Tarjeta credito')">Tarjeta credito</div>
      <div class="pay-chip" onclick="togglePay(this,'Transferencia')">Transferencia</div>
      <div class="pay-chip" onclick="togglePay(this,'Link de pago')">Link de pago</div>
      <div class="pay-chip" onclick="togglePay(this,'OXXO')">OXXO</div>
    </div>
    <div id="pay-inputs"></div>
    <div id="pay-status"></div>
  </div>`;

  document.getElementById('w3-form').innerHTML = html;
  // Restore payment state if navigating back
  selectedPays = {};
  // Pre-fill fields if editing a pending order
  if (editingPedidoData) prefillFromEditing();
  updateSummary();
}

function todayStr() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}

// ─── Horario selection ───
function selHorarioBtn(el, val) {
  el.parentElement.querySelectorAll('.hor-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  selHorario = val;
  document.getElementById('hora-esp-wrap').style.display = val === 'hora_especifica' ? '' : 'none';
  if (val === 'hora_especifica') {
    const note = document.getElementById('hora-esp-wrap');
    if (note) note.insertAdjacentHTML('beforeend', '<div style="font-size:11px;color:var(--dorado);font-weight:600;margin-top:2px" id="cargo-hora-note">+$80 cargo hora especifica</div>');
  } else {
    const cn = document.getElementById('cargo-hora-note');
    if (cn) cn.remove();
  }
  updateSummary();
}

let velHorario = null;
function selHorVelacion(el, val) {
  el.parentElement.querySelectorAll('.hor-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  velHorario = val;
  document.getElementById('vel-hora-wrap').style.display = val === 'hora' ? '' : 'none';
}

// ─── Maps verification ───
function verificarMaps() {
  const dir = document.getElementById('f-dir').value;
  if (dir) window.open(`https://www.google.com/maps/search/${encodeURIComponent(dir + ', Chihuahua, Mexico')}`, '_blank');
}

async function onDirVerificada() {
  const checked = document.getElementById('f-dir-check').checked;
  dirVerificada = checked;
  if (!checked) { geoData = null; document.getElementById('geo-badge').innerHTML = ''; updateSummary(); return; }
  const dir = document.getElementById('f-dir').value;
  if (!dir) return;
  document.getElementById('geo-badge').innerHTML = '<span style="font-size:11px;color:var(--texto2)">Geocodificando...</span>';
  try {
    const r = await fetch('/pos/geocodificar', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({direccion: dir})
    });
    const data = await r.json();
    if (data.error) {
      document.getElementById('geo-badge').innerHTML = `<span style="font-size:11px;color:var(--rojo)">${data.error}</span>`;
      geoData = null;
    } else {
      geoData = data;
      document.getElementById('geo-badge').innerHTML =
        `<span class="zona-badge ${(data.zona_envio||'').toLowerCase()}" style="margin-right:6px">${data.zona_envio || '?'} — $${(data.tarifa_envio||0)/100}</span>` +
        `<span class="zona-badge" style="background:#e8eaed;color:var(--texto)">${data.ruta || '?'}</span>`;
      const zonaEl = document.getElementById('f-zona');
      if (zonaEl && data.zona_envio) zonaEl.value = data.zona_envio;
    }
  } catch(e) {
    document.getElementById('geo-badge').innerHTML = '<span style="font-size:11px;color:var(--rojo)">Error de red</span>';
    geoData = null;
  }
  updateSummary();
}

function onZonaChange() { updateSummary(); }

// ─── Client search ───
function abrirBuscarCliente() {
  document.getElementById('modal-cli-search').value = '';
  document.getElementById('modal-cli-results').innerHTML = '';
  document.getElementById('modal-cliente').classList.add('active');
}

function debounceModalCli() {
  clearTimeout(debounceCliTimer);
  debounceCliTimer = setTimeout(buscarClientesModal, 300);
}

async function buscarClientesModal() {
  const q = document.getElementById('modal-cli-search').value;
  if (q.length < 2) { document.getElementById('modal-cli-results').innerHTML = ''; return; }
  try {
    const r = await fetch('/pos/clientes/buscar?q=' + encodeURIComponent(q));
    const clientes = await r.json();
    document.getElementById('modal-cli-results').innerHTML = clientes.map(c =>
      `<div class="modal-item" onclick="selCliente(${c.id},'${esc(c.nombre)}','${c.telefono}',false)">
        <strong>${c.nombre}</strong> — ${c.telefono}
      </div>`
    ).join('') || '<div style="padding:10px;color:var(--texto2);font-size:12px">Sin resultados</div>';
  } catch(e) { console.error(e); }
}

function selCliente(id, nombre, telefono, primera) {
  clienteSel = {id, nombre, telefono, primera_compra: primera};
  document.getElementById('modal-cliente').classList.remove('active');
  buildW3Form();
}

function aplicarDescPrimera() {
  descGlobal = { tipo: '%', valor: 10 };
  buildW3Form();
}

function abrirModalRegistro() {
  document.getElementById('reg-nombre').value = '';
  document.getElementById('reg-tel').value = '';
  document.getElementById('reg-email').value = '';
  document.getElementById('reg-dir').value = '';
  document.getElementById('reg-err').style.display = 'none';
  document.getElementById('modal-registro').classList.add('active');
}

async function registrarCliente() {
  const nombre = document.getElementById('reg-nombre').value.trim();
  const tel = document.getElementById('reg-tel').value.trim();
  if (!nombre || !tel) {
    document.getElementById('reg-err').textContent = 'Nombre y telefono son obligatorios';
    document.getElementById('reg-err').style.display = '';
    return;
  }
  try {
    const r = await fetch('/pos/cliente', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        nombre, telefono: tel,
        email: document.getElementById('reg-email').value.trim() || null,
        direccion: document.getElementById('reg-dir').value.trim() || null
      })
    });
    if (!r.ok) {
      const err = await r.json();
      document.getElementById('reg-err').textContent = err.detail || 'Error';
      document.getElementById('reg-err').style.display = '';
      return;
    }
    const cli = await r.json();
    clienteSel = {id: cli.id, nombre: cli.nombre, telefono: cli.telefono, primera_compra: false};
    document.getElementById('modal-registro').classList.remove('active');
    document.getElementById('modal-cliente').classList.remove('active');
    buildW3Form();
  } catch(e) {
    document.getElementById('reg-err').textContent = 'Error de red';
    document.getElementById('reg-err').style.display = '';
  }
}

// ─── Funeraria search ───
function abrirBuscarFuneraria() {
  document.getElementById('modal-fun-search').value = '';
  document.getElementById('modal-fun-results').innerHTML = '';
  document.getElementById('modal-funeraria').classList.add('active');
  if (allFunerarias.length === 0) fetchFunerarias();
  else renderFunerarias('');
}

async function fetchFunerarias() {
  try {
    const r = await fetch('/funerarias/');
    allFunerarias = await r.json();
    renderFunerarias('');
  } catch(e) { console.error(e); }
}

function buscarFunerarias() {
  const q = document.getElementById('modal-fun-search').value.toLowerCase();
  renderFunerarias(q);
}

function renderFunerarias(q) {
  const filtered = q ? allFunerarias.filter(f => f.nombre.toLowerCase().includes(q)) : allFunerarias;
  document.getElementById('modal-fun-results').innerHTML = filtered.map(f =>
    `<div class="modal-item" onclick="selFuneraria(${f.id},'${esc(f.nombre)}','${f.zona}',${f.costo_envio})">
      <strong>${f.nombre}</strong> — ${f.zona} $${f.costo_envio/100}
    </div>`
  ).join('') || '<div style="padding:10px;color:var(--texto2);font-size:12px">Sin resultados</div>';
}

function selFuneraria(id, nombre, zona, costo) {
  funerariaSel = {id, nombre, zona, costo_envio: costo};
  document.getElementById('modal-funeraria').classList.remove('active');
  buildW3Form();
}

// ─── Payments ───
function togglePay(el, name) {
  el.classList.toggle('active');
  if (el.classList.contains('active')) {
    selectedPays[name] = 0;
  } else {
    delete selectedPays[name];
  }
  renderPayInputs();
  updateSummary();
}

function renderPayInputs() {
  const c = document.getElementById('pay-inputs');
  const soloEfectivo = Object.keys(selectedPays).length === 1 && selectedPays['Efectivo'] !== undefined;
  c.innerHTML = Object.keys(selectedPays).map(name => {
    const comNote = name === 'Link de pago' ? `<div style="font-size:10px;color:var(--dorado);margin-top:2px">+4% comision</div>` : '';
    const displayVal = selectedPays[name] ? (selectedPays[name] / 100) : '';
    let extra = '';
    if (name === 'Efectivo' && soloEfectivo) {
      extra = `<div style="display:flex;gap:8px;align-items:center;margin-top:6px;font-size:12px" id="vuelto-row">
        <label style="min-width:60px;font-weight:500">Recibido:</label>
        <input type="number" id="vuelto-recibido" placeholder="$0" step="any" style="flex:1;padding:4px 6px;border:1px solid var(--borde);border-radius:4px;font-size:13px" oninput="calcVuelto()">
        <span id="vuelto-cambio" style="min-width:90px;font-weight:600">Cambio: —</span>
      </div>`;
    }
    return `<div class="pay-input">
      <label>${name}</label>
      <input type="number" placeholder="$0" step="any" value="${displayVal}" onchange="updatePayAmt('${name}',this.value)">
      ${comNote}
    </div>${extra}`;
  }).join('');
  updatePayStatus();
}

function updatePayAmt(name, val) {
  selectedPays[name] = Math.round(parseFloat(val || 0) * 100);
  updatePayStatus();
  updateSummary();
}

function calcVuelto() {
  const inp = document.getElementById('vuelto-recibido');
  const span = document.getElementById('vuelto-cambio');
  if (!inp || !span) return;
  const recibido = parseFloat(inp.value || 0);
  const t = calcTotals();
  const totalPesos = t.total / 100;
  if (!inp.value || recibido === 0) {
    span.textContent = 'Cambio: —';
    span.style.color = 'var(--texto2)';
  } else if (recibido < totalPesos) {
    span.textContent = 'Monto insuficiente';
    span.style.color = 'var(--rojo)';
  } else {
    const cambio = (recibido - totalPesos).toFixed(2);
    span.textContent = `Cambio: $${cambio}`;
    span.style.color = '#2e7d32';
  }
}

function updatePayStatus() {
  const t = calcTotals();
  const asignado = Object.values(selectedPays).reduce((s, v) => s + v, 0);
  const el = document.getElementById('pay-status');
  if (Object.keys(selectedPays).length === 0) { el.innerHTML = ''; return; }
  if (asignado >= t.total) {
    el.innerHTML = `<div class="pay-status ok">✓ Pago completo: $${(asignado/100).toLocaleString()}</div>`;
  } else {
    const falta = t.total - asignado;
    el.innerHTML = `<div class="pay-status pending">Falta asignar: $${(falta/100).toLocaleString()}</div>`;
  }
}

// ─── Summary (right column) ───
function updateSummary() {
  const t = calcTotals();
  // Items
  const si = document.getElementById('sum-items');
  if (si) {
    si.innerHTML = carrito.map(it => {
      const fp = getItemFinalPrice(it);
      return `<div class="sum-item"><span>${it.cantidad}x ${it.nombre}</span><span>$${(fp/100).toLocaleString()}</span></div>`;
    }).join('');
  }
  // Totals
  const st = document.getElementById('sum-totals');
  if (st) {
    let html = `<div class="ct-line"><span>Subtotal</span><span>$${(t.subtotal/100).toLocaleString()}</span></div>`;
    if (t.iva) html += `<div class="ct-line"><span>IVA 16%</span><span>$${(t.iva/100).toLocaleString()}</span></div>`;
    if (t.ieps && iepsActivo) html += `<div class="ct-line"><span>IEPS 8% (incluido)</span><span>$${(t.ieps/100).toLocaleString()}</span></div>`;
    if (t.envio) html += `<div class="ct-line"><span>Envio</span><span>$${(t.envio/100).toLocaleString()}</span></div>`;
    if (t.cargoHora) html += `<div class="ct-line"><span>Hora especifica</span><span>+$${(t.cargoHora/100).toLocaleString()}</span></div>`;
    if (t.descGlobalAmt) html += `<div class="ct-line disc"><span>Descuento</span><span>-$${(t.descGlobalAmt/100).toLocaleString()}</span></div>`;
    if (t.comision) html += `<div class="ct-line"><span>Comision link (4%)</span><span>+$${(t.comision/100).toLocaleString()}</span></div>`;
    html += `<div class="ct-line total"><span>TOTAL</span><span>$${(t.total/100).toLocaleString()}</span></div>`;
    st.innerHTML = html;
  }
  updatePayStatus();
}

// ═══════════════════════════════════════════
// VALIDATION + SUBMIT
// ═══════════════════════════════════════════
function clearErrors() {
  document.querySelectorAll('.frow.error').forEach(el => el.classList.remove('error'));
}

function setError(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.add('error'); return el; }
}

function validate() {
  clearErrors();
  const errors = [];
  if (carrito.length === 0) { alert('Agrega al menos un producto'); return false; }

  if (ordenTipo === 'funeral') {
    const nonFun = carrito.filter(it => !it.es_custom && it.categoria && it.categoria.toLowerCase() !== 'funeral');
    if (nonFun.length) { alert('Solo productos de categoria funeral permitidos'); return false; }
  }

  if (['domicilio','recoger','funeral'].includes(ordenTipo) && !clienteSel) {
    alert('Selecciona un cliente'); return false;
  }

  if (ordenTipo === 'domicilio') {
    if (!val('f-rec-nombre', 'fr-rec-nombre')) errors.push('fr-rec-nombre');
    if (!val('f-rec-tel', 'fr-rec-tel')) errors.push('fr-rec-tel');
    if (!val('f-dir', 'fr-dir')) errors.push('fr-dir');
    if (!selHorario) errors.push(setError('fr-horario') && 'fr-horario');
  }
  if (ordenTipo === 'funeral') {
    if (!funerariaSel) errors.push(setError('fr-funeraria') && 'fr-funeraria');
    if (!val('f-fallecido', 'fr-fallecido')) errors.push('fr-fallecido');
  }
  if (ordenTipo === 'recoger') {
    if (!val('f-fecha-rec', 'fr-fecha-rec')) errors.push('fr-fecha-rec');
    if (!val('f-hora-rec', 'fr-hora-rec')) errors.push('fr-hora-rec');
  }

  if (errors.length) {
    const first = document.getElementById(errors[0]);
    if (first) first.scrollIntoView({behavior:'smooth', block:'center'});
    return false;
  }
  return true;
}

function val(inputId, rowId) {
  const el = document.getElementById(inputId);
  if (!el || !el.value.trim()) { setError(rowId); return false; }
  return true;
}

function buildPayload(estado) {
  const t = calcTotals();
  const items = carrito.map(it => ({
    producto_id: it.producto_id,
    cantidad: it.cantidad,
    precio_unitario: it.precio,
    es_personalizado: it.es_custom,
    nombre_personalizado: it.es_custom ? it.nombre : null,
    observaciones: it.observaciones || null,
  }));

  const pagos = Object.entries(selectedPays).map(([nombre, monto]) => ({
    metodo_pago_id: null, nombre, monto
  }));

  const body = {
    tipo: ordenTipo,
    cliente_id: clienteSel?.id || null,
    items,
    tipo_impuesto: ivaActivo ? 'IVA' : (iepsActivo ? 'IEPS' : 'NA'),
    descuento_total: t.descGlobalAmt,
    cargo_hora_especifica: t.cargoHora || 0,
    pagos,
    estado,
  };

  if (ordenTipo === 'domicilio') {
    body.nombre_destinatario = document.getElementById('f-rec-nombre')?.value || '';
    body.telefono_destinatario = document.getElementById('f-rec-tel')?.value || '';
    body.direccion_entrega = document.getElementById('f-dir')?.value || '';
    body.notas_entrega = document.getElementById('f-notas')?.value || '';
    body.dedicatoria = document.getElementById('f-dedicatoria')?.value || '';
    body.fecha_entrega = document.getElementById('f-fecha')?.value || todayStr();
    body.horario_entrega = selHorario;
    body.hora_especifica = selHorario === 'hora_especifica' ? horaEspecifica : null;
    body.zona_envio = document.getElementById('f-zona')?.value || null;
    body.ruta = geoData?.ruta || null;
    body.lat = geoData?.lat || null;
    body.lng = geoData?.lng || null;
  }

  if (ordenTipo === 'funeral') {
    body.funeraria_id = funerariaSel?.id || null;
    body.nombre_fallecido = document.getElementById('f-fallecido')?.value || '';
    body.sala = document.getElementById('f-sala')?.value || '';
    body.banda = document.getElementById('f-banda')?.value || '';
    body.dedicatoria = document.getElementById('f-dedicatoria-fun')?.value || '';
    body.fecha_entrega = document.getElementById('f-fecha-fun')?.value || todayStr();
    body.horario_velacion = velHorario === 'hora' ? (document.getElementById('f-vel-hora')?.value || '') : (velHorario || '');
  }

  if (ordenTipo === 'recoger') {
    body.fecha_entrega = document.getElementById('f-fecha-rec')?.value || todayStr();
    body.hora_especifica = document.getElementById('f-hora-rec')?.value || '';
  }

  return body;
}

async function guardarPedido() {
  await submitPedido('pendiente_pago');
}

async function finalizarVenta() {
  if (!validate()) return;
  const t = calcTotals();
  const asignado = Object.values(selectedPays).reduce((s, v) => s + v, 0);
  if (asignado < t.total) {
    alert(`Falta asignar $${((t.total - asignado)/100).toFixed(0)} en metodos de pago`);
    return;
  }
  await submitPedido('pagado');
}

async function submitPedido(estado) {
  const body = buildPayload(estado);
  console.log('POS submitPedido body:', JSON.stringify(body, null, 2));
  const url = editingPedidoId ? `/pos/pedido/${editingPedidoId}/completar` : '/pos/pedido';
  const method = editingPedidoId ? 'PATCH' : 'POST';
  try {
    const r = await fetch(url, {
      method, headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    const text = await r.text();
    console.log('POS response:', r.status, text);
    let result;
    try { result = JSON.parse(text); } catch(pe) { alert('Respuesta invalida del servidor'); return; }
    if (!r.ok) {
      alert(result.detail || 'Error al crear pedido');
      return;
    }
    lastResult = result;
    lastCarritoSnap = [...carrito];
    if (estado === 'pendiente_pago' && !editingPedidoId) {
      contadorPendientes++;
      renderBadge();
    }
    mostrarModalCreado(result);
  } catch(e) {
    console.error('POS submitPedido error:', e);
    alert('Error de red al crear pedido: ' + e.message);
  }
}

// ═══════════════════════════════════════════
// POST-SALE MODAL
// ═══════════════════════════════════════════
function mostrarModalCreado(result) {
  const info = buildInfoFromPOS();
  info.estado = result.estado;
  document.getElementById('creado-ticket-digital').innerHTML = buildTicketDigital(info);

  // WhatsApp button
  const btnWa = document.getElementById('btn-wa');
  const waNote = document.getElementById('wa-note');
  waNote.style.display = 'none';
  if (clienteSel && clienteSel.telefono && ordenTipo !== 'mostrador') {
    btnWa.style.display = '';
    btnWa.disabled = false;
    btnWa.textContent = '💬 WhatsApp';
    btnWa.style.background = '#25D366';
  } else {
    btnWa.style.display = 'none';
  }
  document.getElementById('modal-creado').classList.add('active');
}

function cerrarModalCreado() {
  document.getElementById('modal-creado').classList.remove('active');
  resetVenta();
  goWin(1);
}

function resetVenta() {
  carrito = [];
  clienteSel = null;
  funerariaSel = null;
  geoData = null;
  dirVerificada = false;
  selHorario = null;
  horaEspecifica = '';
  velHorario = null;
  ordenTipo = null;
  ivaActivo = false;
  iepsActivo = false;
  descGlobal = null;
  selectedPays = {};
  lastResult = null;
  lastCarritoSnap = [];
  editingPedidoId = null;
  editingPedidoData = null;
  renderCart();
}

// ─── Print — Ticket Completo ───
function buildTicketCompleto(info) {
  // info: {folio, fecha, cliente_nombre, cliente_telefono, items[], subtotal, envio, total,
  //        impuesto, descuento, comision, cargo_hora, zona_envio, forma_pago, pagos[],
  //        tipo, receptor_nombre, receptor_telefono, direccion_entrega, dedicatoria,
  //        notas_internas, horario_entrega, hora_exacta, ruta, fecha_entrega,
  //        funeraria, nombre_fallecido, sala, banda, horario_velacion}
  const S = sanitizarTexto;
  const L = [];
  // Header
  L.push('<div class="dsep"></div>');
  L.push('<div class="tline tk-header"><strong>FLORERIA LUCY</strong></div>');
  L.push('<div class="tline tk-subheader"><strong>- LA FLORE CHOCOLATIER -</strong></div>');
  L.push('<div class="tline sm">C. SABINO 610, LAS GRANJAS</div>');
  L.push('<div class="tline sm">CHIHUAHUA, CHIH., MEXICO</div>');
  L.push('<div class="tline sm">TEL. 614 334 9392</div>');
  L.push('<div class="tline sm">florerialucychihuahua@gmail.com</div>');
  L.push('<div class="dsep"></div>');
  L.push('<div class="tline tk-comprobante"><strong>COMPROBANTE DE COMPRA</strong></div>');
  L.push(`<div class="tline tk-folio">${info.folio||''}</div>`);
  L.push(`<div class="tline tk-fecha">${fechaTicket(info.fecha || new Date().toISOString())}</div>`);
  L.push('<div class="dsep"></div>');
  // Client
  if (info.cliente_nombre) {
    L.push('<div class="hdr">CLIENTE</div>');
    L.push(`<div>${S(info.cliente_nombre)}</div>`);
    if (info.cliente_telefono) L.push(`<div>${info.cliente_telefono}</div>`);
  }
  // Delivery / Funeral / Recoger
  const tipo = info.tipo || 'mostrador';
  if (tipo === 'funeral' || (info.notas_internas && info.notas_internas.includes('FUNERAL'))) {
    L.push('<div class="tline" style="margin:6px 0"><strong>*** PEDIDO FUNERAL ***</strong></div>');
    if (info.funeraria) L.push(`<div><strong>FUNERARIA:</strong> ${S(info.funeraria)}</div>`);
    if (info.nombre_fallecido) L.push(`<div><strong>FALLECIDO:</strong> ${S(info.nombre_fallecido)}</div>`);
    if (info.sala) L.push(`<div><strong>SALA:</strong> ${S(info.sala)}</div>`);
    if (info.banda) L.push(`<div><strong>BANDA:</strong> ${S(info.banda)}</div>`);
    if (info.horario_velacion) L.push(`<div><strong>VELACION:</strong> ${S(info.horario_velacion)}</div>`);
    if (info.fecha_entrega) L.push(`<div><strong>FECHA:</strong> ${fechaTicket(info.fecha_entrega)}</div>`);
  } else if (info.direccion_entrega) {
    L.push('<div class="hdr">DATOS DE ENTREGA</div>');
    if (info.receptor_nombre) L.push(`<div><strong>RECIBE:</strong> ${S(info.receptor_nombre)}</div>`);
    if (info.receptor_telefono) L.push(`<div><strong>TEL:</strong> ${info.receptor_telefono}</div>`);
    L.push(`<div><strong>DIR:</strong> ${S(info.direccion_entrega)}</div>`);
    if (info.fecha_entrega) L.push(`<div><strong>FECHA:</strong> ${fechaTicket(info.fecha_entrega)}</div>`);
    if (info.horario_entrega) L.push(`<div><strong>HORARIO:</strong> ${S(info.horario_entrega)}</div>`);
    if (info.hora_exacta) L.push(`<div><strong>HORA:</strong> ${info.hora_exacta}</div>`);
    if (info.zona_envio) L.push(`<div><strong>ZONA:</strong> ${S(info.zona_envio)}</div>`);
    if (info.ruta) L.push(`<div><strong>RUTA:</strong> ${S(info.ruta)}</div>`);
  } else if (info.hora_exacta && tipo === 'recoger') {
    L.push('<div class="hdr">RECOGER EN TIENDA</div>');
    if (info.fecha_entrega) L.push(`<div><strong>FECHA:</strong> ${fechaTicket(info.fecha_entrega)}</div>`);
    L.push(`<div><strong>HORA:</strong> ${info.hora_exacta}</div>`);
  }
  // Dedicatoria
  if (info.dedicatoria) {
    L.push('<div class="psep"></div>');
    L.push('<div><strong>DEDICATORIA:</strong></div>');
    L.push(`<div>${S(info.dedicatoria)}</div>`);
    L.push('<div class="psep"></div>');
  }
  // Products
  L.push('<div class="hdr">ARTICULOS</div>');
  const items = info.items || [];
  for (const it of items) {
    const name = S(it.nombre || it.nombre_personalizado || '');
    const qty = it.cantidad || 1;
    const price = fmtPrecioTk((it.precio_unitario || it.precio || 0) * qty);
    L.push(`<div class="irow"><span>${qty}X ${name}</span><span class="r">${price}</span></div>`);
  }
  L.push('<div class="sep"></div>');
  // Totals
  const subtotal = info.subtotal || 0;
  L.push(`<div class="irow"><span>SUBTOTAL</span><span class="r">${fmtPrecioTk(subtotal)}</span></div>`);
  if (info.envio) L.push(`<div class="irow"><span>ENVIO ZONA ${S(info.zona_envio||'')}</span><span class="r">${fmtPrecioTk(info.envio)}</span></div>`);
  if (info.impuesto) L.push(`<div class="irow"><span>IVA (16%)</span><span class="r">${fmtPrecioTk(info.impuesto)}</span></div>`);
  if (info.cargo_hora) L.push(`<div class="irow"><span>HORA ESPECIFICA</span><span class="r">+${fmtPrecioTk(info.cargo_hora)}</span></div>`);
  if (info.comision) L.push(`<div class="irow"><span>COMISION LINK (4%)</span><span class="r">+${fmtPrecioTk(info.comision)}</span></div>`);
  if (info.descuento) L.push(`<div class="irow"><span>DESCUENTO</span><span class="r">-${fmtPrecioTk(info.descuento)}</span></div>`);
  L.push('<div class="dsep"></div>');
  L.push(`<div class="irow"><span class="med">TOTAL</span><span class="r med">${fmtPrecioTk(info.total||0)}</span></div>`);
  L.push('<div class="sep"></div>');
  // Payment
  L.push('<div class="tk-pago-hdr"><strong>FORMA DE PAGO:</strong></div>');
  if (info.pagos && info.pagos.length) {
    for (const p of info.pagos) L.push(`<div class="irow"><span>${S(p.nombre||'')}</span><span class="r">${fmtPrecioTk(p.monto||0)}</span></div>`);
  } else if (info.forma_pago) {
    L.push(`<div>${S(info.forma_pago)}</div>`);
  }
  L.push('<div class="dsep"></div>');
  L.push('<div class="tline tk-gracias"><strong>GRACIAS POR SU PREFERENCIA</strong></div>');
  L.push(`<div class="tline sm">${fechaLargaHoy()}</div>`);
  L.push('<div class="dsep"></div>');
  return L.join('\n');
}

function buildMiniTickets(info) {
  const S = sanitizarTexto;
  const items = info.items || [];
  const total = Math.max(items.length, 1);
  let html = '';
  for (let i = 0; i < total; i++) {
    const it = items[i];
    const label = total > 1 ? ` (${i+1} DE ${total})` : '';
    const itemName = it ? S(it.nombre || it.nombre_personalizado || '') : '';
    let L = [];
    L.push('<div class="dsep"></div>');
    L.push(`<div class="tline med">${info.folio||''}${label}</div>`);
    if (itemName) L.push(`<div class="tline"><strong>${itemName}</strong></div>`);
    L.push('<div class="sep"></div>');
    if (info.fecha_entrega) L.push(`<div>ENTREGA: ${fechaTicket(info.fecha_entrega)}</div>`);
    if (info.horario_entrega) L.push(`<div>HORARIO: ${S(info.horario_entrega)}</div>`);
    if (info.hora_exacta) L.push(`<div>HORA: ${info.hora_exacta}</div>`);
    if (info.zona_envio) L.push(`<div>ZONA: ${S(info.zona_envio)}</div>`);
    if (info.receptor_nombre) L.push(`<div>RECIBE: ${S(info.receptor_nombre)}</div>`);
    if (info.funeraria) L.push(`<div>FUNERARIA: ${S(info.funeraria)}</div>`);
    L.push('<div class="dsep"></div>');
    html += `<div class="mini-ticket">${L.join('\n')}</div>`;
  }
  return html;
}

// Build info object from POS post-sale result + carrito state
function buildInfoFromPOS() {
  const r = lastResult;
  const items = lastCarritoSnap.map(it => ({
    nombre: it.nombre, cantidad: it.cantidad, precio_unitario: it.precio
  }));
  const tipo = ordenTipo || 'mostrador';
  return {
    folio: r.folio, fecha: new Date().toISOString(), items, tipo,
    subtotal: r.subtotal, envio: r.envio, total: r.total,
    impuesto: r.impuesto, descuento: r.descuento, comision: r.comision,
    cargo_hora: r.cargo_hora || 0,
    zona_envio: document.getElementById('f-zona')?.value || '',
    forma_pago: Object.keys(selectedPays).join(', '),
    pagos: Object.entries(selectedPays).map(([nombre,monto])=>({nombre,monto})),
    cliente_nombre: clienteSel?.nombre || null,
    cliente_telefono: clienteSel?.telefono || null,
    receptor_nombre: document.getElementById('f-rec-nombre')?.value || '',
    receptor_telefono: document.getElementById('f-rec-tel')?.value || '',
    direccion_entrega: document.getElementById('f-dir')?.value || '',
    dedicatoria: document.getElementById('f-dedicatoria')?.value || document.getElementById('f-dedicatoria-fun')?.value || '',
    notas_internas: document.getElementById('f-notas')?.value || '',
    horario_entrega: selHorario || '',
    hora_exacta: horaEspecifica || document.getElementById('f-hora-rec')?.value || '',
    fecha_entrega: document.getElementById('f-fecha')?.value || document.getElementById('f-fecha-rec')?.value || document.getElementById('f-fecha-fun')?.value || '',
    ruta: geoData?.ruta || '',
    funeraria: funerariaSel?.nombre || '',
    nombre_fallecido: document.getElementById('f-fallecido')?.value || '',
    sala: document.getElementById('f-sala')?.value || '',
    banda: document.getElementById('f-banda')?.value || '',
    horario_velacion: velHorario === 'hora' ? (document.getElementById('f-vel-hora')?.value || '') : (velHorario || ''),
  };
}

// Build info object from a pedido object (from API)
function buildInfoFromPedido(p) {
  // Parse funeral data from notas_internas
  let funeraria='', fallecido='', sala='', banda='', velacion='';
  if (p.tipo_especial === 'Funeral' && p.notas_internas) {
    const n = p.notas_internas;
    const mf = n.match(/FUNERAL\s*(?:—|-)\s*([^.]+)/i); if (mf) funeraria = mf[1].trim();
    const mfa = n.match(/Fallecido:\s*([^.]+)/i); if (mfa) fallecido = mfa[1].trim();
    const ms = n.match(/Sala:\s*([^.]+)/i); if (ms) sala = ms[1].trim();
    const mb = n.match(/Banda:\s*([^.]+)/i); if (mb) banda = mb[1].trim();
    const mv = n.match(/Velacion:\s*([^.]+)/i); if (mv) velacion = mv[1].trim();
  }
  let tipo = 'mostrador';
  if (p.tipo_especial === 'Funeral') tipo = 'funeral';
  else if (p.direccion_entrega) tipo = 'domicilio';
  else if (p.hora_exacta) tipo = 'recoger';
  return {
    folio: p.folio, fecha: p.fecha_pedido, items: p.items || [], tipo,
    subtotal: p.subtotal, envio: p.envio, total: p.total,
    impuesto: 0, descuento: 0, comision: 0, cargo_hora: 0,
    zona_envio: p.zona_entrega || '', forma_pago: p.forma_pago || '', pagos: [],
    cliente_nombre: p.cliente_nombre, cliente_telefono: p.cliente_telefono,
    receptor_nombre: p.receptor_nombre, receptor_telefono: p.receptor_telefono,
    direccion_entrega: p.direccion_entrega, dedicatoria: p.dedicatoria,
    notas_internas: p.notas_internas, horario_entrega: p.horario_entrega,
    hora_exacta: p.hora_exacta, fecha_entrega: p.fecha_entrega, ruta: p.ruta,
    funeraria, nombre_fallecido: fallecido, sala, banda, horario_velacion: velacion,
  };
}

function imprimirTicket() {
  document.getElementById('print-frame').innerHTML = buildTicketCompleto(buildInfoFromPOS());
  setTimeout(() => window.print(), 100);
}

// ─── WhatsApp ───
async function enviarWhatsApp() {
  const btn = document.getElementById('btn-wa');
  const note = document.getElementById('wa-note');
  if (!clienteSel || !clienteSel.telefono) return;
  btn.disabled = true;
  btn.textContent = '⏳ Enviando...';
  note.style.display = 'none';

  const container = document.createElement('div');
  container.style.cssText = 'position:fixed;left:-9999px;top:0;width:300px;padding:16px;background:#fff;font-family:Courier New,monospace;font-size:12px;line-height:1.5;color:#000';
  container.innerHTML = buildTicketCompleto(buildInfoFromPOS());
  document.body.appendChild(container);

  try {
    const canvas = await html2canvas(container, {scale: 2, backgroundColor: '#ffffff'});
    document.body.removeChild(container);
    const base64 = canvas.toDataURL('image/png').split(',')[1];
    const resp = await fetch('/pos/enviar-ticket-whatsapp', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({pedido_id: lastResult.id, telefono: clienteSel.telefono, nombre_cliente: clienteSel.nombre, imagen_base64: base64})
    });
    const data = await resp.json();
    if (data.ok) {
      btn.textContent = '✓ Enviado';
      btn.style.background = '#2d5a3d';
    } else {
      note.textContent = data.error || 'Error al enviar';
      note.style.color = 'var(--rojo)';
      note.style.display = '';
      btn.disabled = false;
      btn.textContent = '💬 Enviar por WhatsApp';
    }
  } catch(e) {
    if (container.parentNode) document.body.removeChild(container);
    note.textContent = 'Error al generar o enviar';
    note.style.color = 'var(--rojo)';
    note.style.display = '';
    btn.disabled = false;
    btn.textContent = '💬 Enviar por WhatsApp';
  }
}

// ─── Descartar ───
function descartarVenta() {
  document.getElementById('modal-descartar').classList.add('active');
}
function confirmarDescartar() {
  document.getElementById('modal-descartar').classList.remove('active');
  resetVenta();
  goWin(1);
}

// ═══════════════════════════════════════════
// PENDIENTES SECTION — Table style
// ═══════════════════════════════════════════
let pendAllData = []; // all pedidos from last fetch (pendientes+finalizados)
let pendFilterPeriodo = 'hoy';
let pendRefreshTimer = null;

function estadoClass(estado) {
  if (!estado) return '';
  const map = {'Pendiente pago':'pendiente_pago','pendiente_pago':'pendiente_pago','comprobante_recibido':'comprobante_recibido','esperando_validacion':'esperando_validacion','pagado':'pagado','Listo':'pagado','Pagado':'pagado','Listo taller':'listo_taller','En camino':'en_camino','Entregado':'entregado','Cancelado':'cancelado','rechazado':'cancelado'};
  return map[estado] || '';
}
function estadoLabel(estado) {
  const map = {'Pendiente pago':'Pendiente pago','pendiente_pago':'Pendiente pago','comprobante_recibido':'Comprobante recibido','esperando_validacion':'Esperando validacion','pagado':'Pagado','Listo':'Pagado','Pagado':'Pagado','Listo taller':'Listo taller','En camino':'En camino','Entregado':'Entregado','Cancelado':'Cancelado','rechazado':'Rechazado'};
  return map[estado] || estado;
}
function tipoIcon(p) {
  if (p.tipo_especial === 'Funeral') return '🌹';
  if (p.direccion_entrega) return '🚚';
  if (p.tipo_especial === 'Recoger') return '🛍';
  return '🏪';
}
function tipoLabel(p) {
  if (p.tipo_especial === 'Funeral') return 'Funeral';
  if (p.direccion_entrega) return 'Domicilio';
  if (p.tipo_especial === 'Recoger') return 'Recoger';
  return 'Mostrador';
}
function canalLabel(canal) {
  if (canal === 'WhatsApp') return 'Claudia';
  return 'POS';
}

async function loadPendientes(params) {
  const tbody = document.getElementById('pend-tbody');
  const empty = document.getElementById('pend-empty');
  tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--texto2);padding:20px">Cargando...</td></tr>';
  try {
    let url = '/pos/pedidos-hoy?periodo=' + pendFilterPeriodo + '&estado=pendiente_pago';
    if (params) url += '&' + params;
    if (pendFilterPeriodo === 'rango') {
      const fi = document.getElementById('fp-fecha-ini').value;
      const ff = document.getElementById('fp-fecha-fin').value;
      if (fi) url += '&fecha_inicio=' + fi;
      if (ff) url += '&fecha_fin=' + ff;
    }
    const r = await fetch(url);
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `Error ${r.status}`);
    }
    const data = await r.json();
    pendAllData = data.pendientes || [];
    contadorPendientes = pendAllData.length;
    renderBadge();
    renderPendTable(pendAllData);
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="9" style="color:var(--rojo);padding:16px">Error al cargar: ${e.message || 'sin conexion'}</td></tr>`;
  }
}

function renderPendTable(rows) {
  const tbody = document.getElementById('pend-tbody');
  const empty = document.getElementById('pend-empty');
  const countEl = document.getElementById('pend-count');
  countEl.textContent = rows.length + ' pedido' + (rows.length !== 1 ? 's' : '');
  if (rows.length === 0) {
    tbody.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';
  tbody.innerHTML = rows.map(p => {
    const itemsHtml = (p.items||[]).map(it => `<div>${it.cantidad}x ${esc(it.nombre)}</div>`).join('');
    const fecha = formatearFecha(p.fecha_pedido) || formatearFecha(p.fecha_entrega) || '';
    const ec = estadoClass(p.estado);
    return `<tr>
      <td style="font-weight:600;color:var(--verde);white-space:nowrap">${p.folio}${p.requiere_factura ? ' <span style="background:#d4a843;color:#193a2c;font-size:9px;padding:2px 5px;border-radius:4px;font-weight:700;vertical-align:middle">FACTURA</span>' : ''}</td>
      <td style="white-space:nowrap;font-size:11px">${fecha}</td>
      <td>${p.cliente_nombre || 'Mostrador'}</td>
      <td>${canalLabel(p.canal)}</td>
      <td><span class="items-link">${(p.items||[]).length} items<span class="items-tooltip">${itemsHtml}</span></span></td>
      <td style="font-weight:600">$${((p.total||0)/100).toLocaleString()}</td>
      <td><span class="badge-estado ${ec}">${estadoLabel(p.estado)}</span></td>
      <td title="${tipoLabel(p)}">${tipoIcon(p)}</td>
      <td class="pend-actions">
        <button class="btn-edit" onclick='editarPendiente(${JSON.stringify(p).replace(/'/g,"&#39;")})'>Editar</button>
        ${ec === 'comprobante_recibido' ? `<button class="btn-fin" style="background:#e67e22" onclick="confirmarPagoPos(${p.id})">Confirmar pago</button>` : ''}
        ${ec === 'comprobante_recibido' && p.comprobante_pago_url ? `<a href="${p.comprobante_pago_url}" target="_blank" class="btn-edit" style="text-decoration:none">Ver comprobante</a>` : ''}
        ${ec === 'pendiente_pago' ? `<button class="btn-fin" onclick="finalizarPendiente(${p.id},${p.total})">Finalizar</button>` : ''}
        ${ec !== 'cancelado' ? `<button class="btn-cancel" onclick="pedirCancelar(${p.id},'${esc(p.folio)}')">Cancelar</button>` : ''}
      </td>
    </tr>`;
  }).join('');
}

function filtrarTablaPend() {
  const q = document.getElementById('pend-search').value.toLowerCase().trim();
  if (!q) { renderPendTable(pendAllData); return; }
  const filtered = pendAllData.filter(p => {
    const itemsStr = (p.items||[]).map(it => it.nombre).join(' ').toLowerCase();
    const cli = (p.cliente_nombre || 'mostrador').toLowerCase();
    const folio = (p.folio || '').toLowerCase();
    return cli.includes(q) || itemsStr.includes(q) || folio.includes(q);
  });
  renderPendTable(filtered);
}

// Filter panel — shared between pendientes and transacciones
let filterPanelTarget = 'pend'; // 'pend' or 'trans'

function toggleFilterPanel(target) {
  if (target) filterPanelTarget = target;
  document.getElementById('filter-panel').classList.toggle('open');
  document.getElementById('filter-overlay').classList.toggle('open');
}

function fpSelectPeriodo(el, val) {
  document.querySelectorAll('#fp-periodo .fp-chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  if (filterPanelTarget === 'trans') transFilterPeriodo = val;
  else pendFilterPeriodo = val;
  document.getElementById('fp-rango-dates').style.display = val === 'rango' ? 'flex' : 'none';
}

function onToggleCancelados() {
  const on = document.getElementById('fp-cancelados').checked;
  // Disable estado checkboxes when toggle is active
  document.querySelectorAll('#filter-panel .fp-section:nth-child(3) input').forEach(cb => {
    cb.disabled = on;
    if (on) cb.checked = false;
    cb.closest('.fp-check').style.opacity = on ? '.4' : '1';
  });
}

function getFilterParams() {
  const params = [];
  const metodos = [];
  document.querySelectorAll('#filter-panel .fp-section:nth-child(2) input:checked').forEach(cb => metodos.push(cb.value));
  if (metodos.length) params.push('metodo_pago=' + encodeURIComponent(metodos.join(',')));
  // Cancelados toggle overrides estado
  const canceladosOn = document.getElementById('fp-cancelados').checked;
  if (canceladosOn) {
    params.push('estado=cancelado');
  } else {
    const estados = [];
    document.querySelectorAll('#filter-panel .fp-section:nth-child(3) input:checked').forEach(cb => estados.push(cb.value));
    if (estados.length) params.push('estado=' + encodeURIComponent(estados.join(',')));
  }
  const canales = [];
  document.querySelectorAll('#filter-panel .fp-section:nth-child(4) input:checked').forEach(cb => canales.push(cb.value));
  if (canales.length) params.push('canal=' + encodeURIComponent(canales.join(',')));
  const tipos = [];
  document.querySelectorAll('#filter-panel .fp-section:nth-child(5) input:checked').forEach(cb => tipos.push(cb.value));
  if (tipos.length) params.push('tipo=' + encodeURIComponent(tipos.join(',')));
  return params.join('&');
}

function aplicarFiltrosPanel() {
  const params = getFilterParams();
  toggleFilterPanel();
  if (filterPanelTarget === 'trans') loadTransacciones(params);
  else loadPendientes(params);
}

// Cancelar pedido
let cancelPedidoId = null;
function pedirCancelar(id, folio) {
  cancelPedidoId = id;
  document.getElementById('cancel-folio').textContent = folio;
  document.getElementById('modal-cancelar').classList.add('active');
}
async function confirmarCancelar() {
  document.getElementById('modal-cancelar').classList.remove('active');
  try {
    const r = await fetch(`/pos/pedido/${cancelPedidoId}/cancelar`, { method: 'PATCH' });
    if (!r.ok) { const err = await r.json(); alert(err.detail || 'Error'); return; }
    pendAllData = pendAllData.filter(p => p.id !== cancelPedidoId);
    renderPendTable(pendAllData);
    contadorPendientes--;
    renderBadge();
  } catch(e) { alert('Error de red'); }
}

// Editar pendiente — load into cart with ALL data preserved
// Store pending order data for pre-filling form fields
let editingPedidoData = null;

function editarPendiente(p) {
  resetVenta();
  editingPedidoId = p.id;
  editingPedidoData = p;

  // Load items into cart
  carrito = (p.items || []).map(it => ({
    producto_id: null, nombre: it.nombre, codigo: null, categoria: null,
    precio: it.precio_unitario, cantidad: it.cantidad, imagen_url: null,
    descuento: null, es_custom: true, observaciones: null
  }));

  // Determine type
  if (p.tipo_especial === 'Funeral') ordenTipo = 'funeral';
  else if (p.direccion_entrega) ordenTipo = 'domicilio';
  else if (p.hora_exacta && !p.direccion_entrega && !p.tipo_especial) ordenTipo = 'recoger';
  else ordenTipo = 'mostrador';

  // Load client
  if (p.customer_id && p.cliente_nombre) {
    clienteSel = { id: p.customer_id, nombre: p.cliente_nombre, telefono: '', primera_compra: false };
  }

  // Restore delivery data
  if (ordenTipo === 'domicilio') {
    if (p.horario_entrega) selHorario = p.horario_entrega;
    else if (p.hora_exacta) { selHorario = 'hora_especifica'; horaEspecifica = p.hora_exacta; }
    if (p.zona_entrega) {
      geoData = { zona_envio: p.zona_entrega, tarifa_envio: null, ruta: p.ruta };
    }
    if (p.direccion_entrega) dirVerificada = true;
  }

  // Navigate to ventas > win1
  navTo('ventas');
  renderCart();
  goWin(1);
}

// Pre-fill form fields after buildW3Form renders the DOM
function prefillFromEditing() {
  const p = editingPedidoData;
  if (!p) return;

  if (ordenTipo === 'domicilio') {
    const el = (id) => document.getElementById(id);
    if (el('f-rec-nombre') && p.receptor_nombre) el('f-rec-nombre').value = p.receptor_nombre;
    if (el('f-rec-tel') && p.receptor_telefono) el('f-rec-tel').value = p.receptor_telefono;
    if (el('f-dir') && p.direccion_entrega) el('f-dir').value = p.direccion_entrega;
    if (el('f-notas') && p.notas_internas) el('f-notas').value = p.notas_internas;
    if (el('f-dedicatoria') && p.dedicatoria) el('f-dedicatoria').value = p.dedicatoria;
    if (el('f-fecha') && p.fecha_entrega) el('f-fecha').value = p.fecha_entrega;
    if (el('f-zona') && p.zona_entrega) el('f-zona').value = p.zona_entrega;
    // Restore horario button
    if (selHorario) {
      const btns = document.querySelectorAll('#w3-form .hor-btn');
      btns.forEach(b => {
        const map = {'manana':'manana','tarde':'tarde','noche':'noche','hora_especifica':'hora_especifica'};
        if (b.textContent.toLowerCase().includes('manana') && selHorario === 'manana') b.classList.add('active');
        else if (b.textContent.toLowerCase().includes('tarde') && selHorario === 'tarde') b.classList.add('active');
        else if (b.textContent.toLowerCase().includes('noche') && selHorario === 'noche') b.classList.add('active');
        else if (b.textContent.toLowerCase().includes('especifica') && selHorario === 'hora_especifica') {
          b.classList.add('active');
          const wrap = document.getElementById('hora-esp-wrap');
          if (wrap) { wrap.style.display = ''; }
          if (el('f-hora-esp') && horaEspecifica) el('f-hora-esp').value = horaEspecifica;
        }
      });
    }
    // Restore geo badge
    if (p.zona_entrega && p.ruta) {
      const gb = document.getElementById('geo-badge');
      if (gb) gb.innerHTML = `<span class="zona-badge ${(p.zona_entrega||'').toLowerCase()}">${p.zona_entrega}</span> <span class="zona-badge" style="background:#e8eaed;color:var(--texto)">${p.ruta}</span>`;
      const chk = document.getElementById('f-dir-check');
      if (chk) chk.checked = true;
    }
  }

  if (ordenTipo === 'recoger') {
    if (document.getElementById('f-fecha-rec') && p.fecha_entrega) document.getElementById('f-fecha-rec').value = p.fecha_entrega;
    if (document.getElementById('f-hora-rec') && p.hora_exacta) document.getElementById('f-hora-rec').value = p.hora_exacta;
  }

  if (ordenTipo === 'funeral') {
    if (document.getElementById('f-fallecido') && p.notas_internas) {
      // Parse funeral data from notas_internas
      const notas = p.notas_internas || '';
      const match_fallecido = notas.match(/Fallecido:\s*([^.]+)/);
      const match_sala = notas.match(/Sala:\s*([^.]+)/);
      const match_banda = notas.match(/Banda:\s*([^.]+)/);
      if (match_fallecido) document.getElementById('f-fallecido').value = match_fallecido[1].trim();
      if (match_sala && document.getElementById('f-sala')) document.getElementById('f-sala').value = match_sala[1].trim();
      if (match_banda && document.getElementById('f-banda')) document.getElementById('f-banda').value = match_banda[1].trim();
    }
    if (document.getElementById('f-dedicatoria-fun') && p.dedicatoria) document.getElementById('f-dedicatoria-fun').value = p.dedicatoria;
    if (document.getElementById('f-fecha-fun') && p.fecha_entrega) document.getElementById('f-fecha-fun').value = p.fecha_entrega;
  }

  updateSummary();
}

// Finalizar pendiente inline
let finPendId = null, finPendTotal = 0, finPendPays = {};
function finalizarPendiente(id, total) {
  finPendId = id;
  finPendTotal = total;
  finPendPays = {};
  const html = `<div class="modal-bg active" id="modal-fin-pend" onclick="if(event.target===this)this.classList.remove('active')">
    <div class="modal">
      <button class="close" onclick="document.getElementById('modal-fin-pend').remove()">&times;</button>
      <h3>Finalizar pedido</h3>
      <div style="font-weight:700;font-size:15px;color:var(--verde);margin-bottom:12px">Total: $${(total/100).toLocaleString()}</div>
      <div class="pay-chips" id="fp-chips">
        <div class="pay-chip" onclick="fpToggle(this,'Efectivo')">Efectivo</div>
        <div class="pay-chip" onclick="fpToggle(this,'Tarjeta debito')">Tarjeta debito</div>
        <div class="pay-chip" onclick="fpToggle(this,'Tarjeta credito')">Tarjeta credito</div>
        <div class="pay-chip" onclick="fpToggle(this,'Transferencia')">Transferencia</div>
        <div class="pay-chip" onclick="fpToggle(this,'Link de pago')">Link de pago</div>
        <div class="pay-chip" onclick="fpToggle(this,'OXXO')">OXXO</div>
      </div>
      <div id="fp-inputs"></div>
      <div id="fp-err" style="color:var(--rojo);font-size:12px;display:none;margin-top:6px"></div>
      <button onclick="fpConfirm()" style="width:100%;padding:10px;background:var(--verde);color:#fff;border:none;border-radius:8px;font-weight:700;font-size:13px;margin-top:12px">Finalizar</button>
    </div>
  </div>`;
  document.body.insertAdjacentHTML('beforeend', html);
}

function fpToggle(el, name) {
  el.classList.toggle('active');
  if (el.classList.contains('active')) finPendPays[name] = 0;
  else delete finPendPays[name];
  fpRenderInputs();
}

function fpRenderInputs() {
  document.getElementById('fp-inputs').innerHTML = Object.keys(finPendPays).map(name => {
    const displayVal = finPendPays[name] ? (finPendPays[name] / 100) : '';
    return `<div class="pay-input"><label>${name}</label><input type="number" placeholder="$0" step="any" value="${displayVal}" onchange="finPendPays['${name}']=Math.round(parseFloat(this.value||0)*100)"></div>`;
  }).join('');
}

async function fpConfirm() {
  const sum = Object.values(finPendPays).reduce((s, v) => s + v, 0);
  if (sum < finPendTotal) {
    document.getElementById('fp-err').textContent = `Falta asignar $${((finPendTotal-sum)/100).toFixed(0)}`;
    document.getElementById('fp-err').style.display = '';
    return;
  }
  const pagos = Object.entries(finPendPays).map(([nombre, monto]) => ({nombre, monto}));
  try {
    const r = await fetch(`/pos/pedido/${finPendId}/finalizar`, {
      method: 'PATCH', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({pagos})
    });
    if (!r.ok) { const err = await r.json(); alert(err.detail || 'Error'); return; }
    document.getElementById('modal-fin-pend').remove();
    pendAllData = pendAllData.filter(p => p.id !== finPendId);
    renderPendTable(pendAllData);
    contadorPendientes--;
    renderBadge();
  } catch(e) { alert('Error de red'); }
}

// ═══════════════════════════════════════════
// TRANSACCIONES SECTION — Table style
// ═══════════════════════════════════════════
let transAllData = [];
let transFilterPeriodo = 'hoy';

function pagoIcon(forma) {
  if (!forma) return '';
  const f = forma.toLowerCase();
  if (f.includes('efectivo')) return '💵';
  if (f.includes('tarjeta')) return '💳';
  if (f.includes('transferencia')) return '🏦';
  if (f.includes('link')) return '📱';
  if (f.includes('oxxo')) return '🏪';
  return '';
}

function obsIcon(p) {
  if (p.dedicatoria || p.notas_internas) return '<span title="' + esc(p.dedicatoria || p.notas_internas) + '" style="cursor:help">💬</span>';
  return '<span style="color:var(--texto2)">-</span>';
}

async function loadResumenVentas() {
  try {
    const r = await fetch('/pos/resumen-ventas');
    const d = await r.json();
    document.getElementById('tm-hoy').innerHTML = `${d.hoy.ventas} ventas`;
    document.getElementById('tm-ayer').innerHTML = `${d.ayer.ventas} ventas`;
    document.getElementById('tm-semana').innerHTML = `${d.semana.ventas} ventas`;
    document.getElementById('tm-mes').innerHTML = `${d.mes.ventas} ventas`;
  } catch(e) { /* silent */ }
}

async function loadTransacciones(params) {
  const tbody = document.getElementById('trans-tbody');
  const empty = document.getElementById('trans-empty');
  tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--texto2);padding:20px">Cargando...</td></tr>';
  loadResumenVentas();
  try {
    let url = '/pos/pedidos-hoy?periodo=' + transFilterPeriodo;
    // Default: only finalized states
    if (!params || !params.includes('estado=')) {
      url += '&estado=pagado,listo_taller,en_camino,entregado';
    }
    if (params) url += '&' + params;
    if (transFilterPeriodo === 'rango') {
      const fi = document.getElementById('fp-fecha-ini').value;
      const ff = document.getElementById('fp-fecha-fin').value;
      if (fi) url += '&fecha_inicio=' + fi;
      if (ff) url += '&fecha_fin=' + ff;
    }
    const r = await fetch(url);
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `Error ${r.status}`);
    }
    const data = await r.json();
    transAllData = [...(data.pendientes || []), ...(data.finalizados || [])];
    renderTransTable(transAllData);
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="10" style="color:var(--rojo);padding:16px">Error al cargar: ${e.message || 'sin conexion'}</td></tr>`;
  }
}

function renderTransTable(rows) {
  const tbody = document.getElementById('trans-tbody');
  const empty = document.getElementById('trans-empty');
  const countEl = document.getElementById('trans-count');
  countEl.textContent = rows.length + ' transaccion' + (rows.length !== 1 ? 'es' : '');
  if (rows.length === 0) {
    tbody.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';
  tbody.innerHTML = rows.map(p => {
    const itemsHtml = (p.items||[]).map(it => `<div>${it.cantidad}x ${esc(it.nombre)}</div>`).join('');
    const fecha = formatearFecha(p.fecha_pedido) || formatearFecha(p.fecha_entrega) || '';
    const ec = estadoClass(p.estado);
    return `<tr>
      <td style="font-weight:600;color:var(--verde);white-space:nowrap">📄 ${p.folio}</td>
      <td style="white-space:nowrap;font-size:11px">${fecha}</td>
      <td>${p.cliente_nombre || '-'}</td>
      <td>${canalLabel(p.canal)}</td>
      <td><span class="items-link">${(p.items||[]).length} items<span class="items-tooltip">${itemsHtml}</span></span></td>
      <td title="${tipoLabel(p)}">${tipoIcon(p)}</td>
      <td>${obsIcon(p)}</td>
      <td><button onclick='verTicket(${JSON.stringify(p).replace(/'/g,"&#39;")})' style="background:none;border:none;font-size:16px;cursor:pointer" title="Ver ticket">🎫</button></td>
      <td class="pend-actions">
        ${ec !== 'cancelado' ? `<button class="btn-cancel" onclick="pedirCancelarTrans(${p.id},'${esc(p.folio)}')" title="Cancelar">✂️</button>` : '<span class="badge-estado cancelado">Cancelado</span>'}
      </td>
    </tr>`;
  }).join('');
}

function filtrarTablaTrans() {
  const q = document.getElementById('trans-search').value.toLowerCase().trim();
  if (!q) { renderTransTable(transAllData); return; }
  const filtered = transAllData.filter(p => {
    const itemsStr = (p.items||[]).map(it => it.nombre).join(' ').toLowerCase();
    const cli = (p.cliente_nombre || '').toLowerCase();
    const folio = (p.folio || '').toLowerCase();
    return cli.includes(q) || itemsStr.includes(q) || folio.includes(q);
  });
  renderTransTable(filtered);
}

// Cancelar desde transacciones — modal con advertencia de finanzas
let cancelTransId = null;
function pedirCancelarTrans(id, folio) {
  cancelTransId = id;
  document.getElementById('cancel-trans-folio').textContent = folio;
  document.getElementById('modal-cancelar-trans').classList.add('active');
}
async function confirmarCancelarTrans() {
  document.getElementById('modal-cancelar-trans').classList.remove('active');
  try {
    const r = await fetch(`/pos/pedido/${cancelTransId}/cancelar`, { method: 'PATCH' });
    if (!r.ok) { const err = await r.json(); alert(err.detail || 'Error'); return; }
    loadTransacciones();
    loadResumenVentas();
  } catch(e) { alert('Error de red'); }
}

// ═══════════════════════════════════════════
// CORTE DE CAJA
// ═══════════════════════════════════════════
let lastCorteData = null;

async function abrirCorteCaja() {
  document.getElementById('corte-content').innerHTML = '<div style="padding:20px;color:var(--texto2)">Cargando...</div>';
  document.getElementById('modal-corte').classList.add('active');
  try {
    let url = '/pos/corte-caja?periodo=' + transFilterPeriodo;
    const params = getFilterParams();
    if (params) url += '&' + params;
    if (transFilterPeriodo === 'rango') {
      const fi = document.getElementById('fp-fecha-ini').value;
      const ff = document.getElementById('fp-fecha-fin').value;
      if (fi) url += '&fecha_inicio=' + fi;
      if (ff) url += '&fecha_fin=' + ff;
    }
    const r = await fetch(url);
    if (!r.ok) throw new Error('Error ' + r.status);
    const d = await r.json();
    lastCorteData = d;
    const fP = (v) => '$' + v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
    let h = '';
    h += `<div style="font-size:16px;font-weight:700;color:var(--verde);margin-bottom:4px">CORTE DE CAJA</div>`;
    h += `<div style="font-size:13px;color:var(--texto2);margin-bottom:12px">${d.periodo}</div>`;
    h += `<div style="font-size:12px;color:var(--texto2);margin-bottom:12px">${d.total_transacciones} transaccion${d.total_transacciones !== 1 ? 'es' : ''}</div>`;
    h += '<div style="text-align:left;background:var(--crema);border-radius:8px;padding:12px;font-size:13px">';
    h += '<div style="border-bottom:1px solid var(--borde);padding-bottom:6px;margin-bottom:6px">';
    for (const [metodo, monto] of Object.entries(d.por_metodo || {})) {
      if (monto > 0) h += `<div style="display:flex;justify-content:space-between;padding:3px 0"><span>${metodo}</span><span style="font-weight:600">${fP(monto)}</span></div>`;
    }
    h += '</div>';
    h += `<div style="display:flex;justify-content:space-between;padding:6px 0;font-size:15px;font-weight:700;color:var(--verde)"><span>TOTAL</span><span>${fP(d.total)}</span></div>`;
    h += '</div>';
    document.getElementById('corte-content').innerHTML = h;
  } catch(e) {
    document.getElementById('corte-content').innerHTML = `<div style="color:var(--rojo);padding:20px">Error: ${e.message}</div>`;
  }
}

function imprimirCorte() {
  if (!lastCorteData) return;
  const d = lastCorteData;
  const S = sanitizarTexto;
  const fP = (v) => '$' + v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  const L = [];
  L.push('<div class="dsep"></div>');
  L.push('<div class="tline tk-header"><strong>FLORERIA LUCY</strong></div>');
  L.push('<div class="dsep"></div>');
  L.push('<div class="tline tk-comprobante"><strong>CORTE DE CAJA</strong></div>');
  L.push(`<div class="tline tk-fecha">${S(d.periodo)}</div>`);
  L.push('<div class="dsep"></div>');
  L.push(`<div>${d.total_transacciones} TRANSACCIONES</div>`);
  L.push('<div class="sep"></div>');
  for (const [metodo, monto] of Object.entries(d.por_metodo || {})) {
    if (monto > 0) L.push(`<div class="irow"><span>${S(metodo)}</span><span class="r">${fP(monto)}</span></div>`);
  }
  L.push('<div class="dsep"></div>');
  L.push(`<div class="irow"><span class="med">TOTAL</span><span class="r med">${fP(d.total)}</span></div>`);
  L.push('<div class="dsep"></div>');
  L.push(`<div class="tline tk-fecha">${fechaLargaHoy()}</div>`);
  L.push('<div class="dsep"></div>');
  document.getElementById('print-frame').innerHTML = L.join('\n');
  setTimeout(() => window.print(), 100);
}

// ═══════════════════════════════════════════
// CLIENTES SECTION
// ═══════════════════════════════════════════
function debounceBuscarClientes() {
  clearTimeout(debounceCliSearchTimer);
  debounceCliSearchTimer = setTimeout(buscarClientesSec, 300);
}

async function buscarClientesSec() {
  const q = document.getElementById('cli-search').value;
  if (q.length < 2) { document.getElementById('cli-list').innerHTML = ''; return; }
  try {
    const r = await fetch('/pos/clientes/buscar?q=' + encodeURIComponent(q));
    const clientes = await r.json();
    document.getElementById('cli-list').innerHTML = clientes.map(c =>
      `<div class="cli-card">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <div class="cli-name">${c.nombre}</div>
            <div class="cli-phone">${c.telefono} ${c.email ? '— ' + c.email : ''}</div>
            <div class="cli-orders">${c.total_pedidos > 0 ? 'Cliente recurrente' : 'Cliente nuevo'}</div>
          </div>
        </div>
        <div style="display:flex;gap:6px;margin-top:8px">
          ${c.telefono ? `<button onclick="abrirWaCli('${esc(c.nombre)}','${c.telefono}')" style="padding:5px 10px;border:1px solid #25D366;background:#fff;color:#25D366;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer">💬 WhatsApp</button>` : ''}
          <button onclick="verPedidosCliente(${c.id},'${esc(c.nombre)}')" style="padding:5px 10px;border:1px solid var(--borde);background:#fff;color:var(--texto);border-radius:6px;font-size:11px;font-weight:600;cursor:pointer">📋 Ver pedidos</button>
          <button onclick="nuevoPedidoCliente(${c.id},'${esc(c.nombre)}','${c.telefono}',false)" style="padding:5px 10px;border:1px solid var(--verde);background:var(--verde);color:#fff;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer">➕ Nuevo pedido</button>
        </div>
      </div>`
    ).join('') || '<div style="padding:10px;color:var(--texto2);font-size:12px">Sin resultados</div>';
  } catch(e) { console.error(e); }
}

// ═══════════════════════════════════════════
// CLIENT ACTIONS
// ═══════════════════════════════════════════
let waCliTel = '';
function abrirWaCli(nombre, tel) {
  waCliTel = tel;
  document.getElementById('wa-cli-nombre').textContent = nombre;
  document.getElementById('wa-cli-msg').value = '';
  document.getElementById('wa-cli-status').style.display = 'none';
  document.getElementById('wa-cli-btn').disabled = false;
  document.getElementById('wa-cli-btn').textContent = 'Enviar';
  document.getElementById('modal-wa-cli').classList.add('active');
}

async function enviarWaCli() {
  const msg = document.getElementById('wa-cli-msg').value.trim();
  if (!msg) { document.getElementById('wa-cli-status').textContent = 'Escribe un mensaje'; document.getElementById('wa-cli-status').style.display = ''; document.getElementById('wa-cli-status').style.color = 'var(--rojo)'; return; }
  const btn = document.getElementById('wa-cli-btn');
  const status = document.getElementById('wa-cli-status');
  btn.disabled = true;
  btn.textContent = 'Enviando...';
  status.style.display = 'none';
  try {
    const r = await fetch('/pos/enviar-whatsapp-cliente', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({telefono: waCliTel, mensaje: msg})
    });
    const data = await r.json();
    if (data.ok) {
      status.textContent = '✓ Mensaje enviado';
      status.style.color = '#2e7d32';
      btn.textContent = 'Enviado ✓';
    } else {
      status.textContent = data.error || 'Error al enviar';
      status.style.color = 'var(--rojo)';
      btn.disabled = false;
      btn.textContent = 'Reintentar';
    }
  } catch(e) {
    status.textContent = 'Error de red';
    status.style.color = 'var(--rojo)';
    btn.disabled = false;
    btn.textContent = 'Reintentar';
  }
  status.style.display = '';
}

async function verPedidosCliente(id, nombre) {
  document.getElementById('cli-ped-titulo').textContent = 'Pedidos de ' + nombre;
  const tbody = document.getElementById('cli-ped-tbody');
  tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--texto2);padding:20px">Cargando...</td></tr>';
  document.getElementById('modal-cli-pedidos').classList.add('active');
  try {
    const r = await fetch('/pos/pedidos-hoy?periodo=todos&cliente_id=' + id);
    if (!r.ok) throw new Error('Error ' + r.status);
    const data = await r.json();
    const all = [...(data.pendientes||[]), ...(data.finalizados||[])];
    if (all.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--texto2);padding:20px">Sin pedidos</td></tr>';
      return;
    }
    tbody.innerHTML = all.map(p => {
      const itemsHtml = (p.items||[]).map(it => `<div>${it.cantidad}x ${esc(it.nombre)}</div>`).join('');
      const fecha = formatearFecha(p.fecha_pedido) || formatearFecha(p.fecha_entrega) || '';
      const ec = estadoClass(p.estado);
      return `<tr>
        <td style="font-weight:600;color:var(--verde);white-space:nowrap">${p.folio}</td>
        <td style="white-space:nowrap;font-size:11px">${fecha}</td>
        <td><span class="items-link">${(p.items||[]).length} items<span class="items-tooltip">${itemsHtml}</span></span></td>
        <td style="font-weight:600">$${((p.total||0)/100).toLocaleString()}</td>
        <td><span class="badge-estado ${ec}">${estadoLabel(p.estado)}</span></td>
        <td title="${tipoLabel(p)}">${tipoIcon(p)}</td>
        <td><button onclick='verTicket(${JSON.stringify(p).replace(/'/g,"&#39;")})' style="background:none;border:none;font-size:14px;cursor:pointer" title="Ver ticket">🎫</button></td>
      </tr>`;
    }).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="7" style="color:var(--rojo);padding:16px">Error: ${e.message}</td></tr>`;
  }
}

function nuevoPedidoCliente(id, nombre, telefono, primera) {
  resetVenta();
  clienteSel = {id, nombre, telefono, primera_compra: primera};
  navTo('ventas');
  renderCart();
  goWin(1);
}

// ═══════════════════════════════════════════
// TICKET DIGITAL (pantalla) — diseño elegante
// ═══════════════════════════════════════════
let ticketPedido = null;

function buildTicketDigital(info) {
  // info same shape as buildTicketCompleto. NO sanitizarTexto — acentos normales.
  const fP = (c) => '$' + (c/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  const secLabel = (txt) => `<div style="font-size:10px;font-weight:700;color:#d4a843;text-transform:uppercase;letter-spacing:.8px;border-bottom:1px solid #e0ddd8;padding-bottom:4px;margin:14px 0 8px">${txt}</div>`;
  const row2 = (a,b) => `<div style="display:flex;justify-content:space-between;font-size:12px;padding:2px 0"><span>${a}</span><span style="font-weight:600">${b}</span></div>`;
  const gridItem = (label, val) => val ? `<div style="min-width:45%"><div style="font-size:10px;color:#888;margin-bottom:1px">${label}</div><div style="font-size:12px;font-weight:600">${val}</div></div>` : '';

  let h = '';
  // Header
  h += '<div style="background:#193a2c;padding:18px 20px 14px;text-align:center">';
  h += '<div style="font-size:20px;font-weight:700;color:#d4a843;font-family:Inter,sans-serif">FLORERIA LUCY</div>';
  h += '<div style="font-size:11px;color:rgba(255,255,255,.7);margin-top:2px;font-style:italic">La expresion del amor</div>';
  h += '</div>';

  // Folio + fecha
  h += '<div style="text-align:center;padding:16px 20px 10px">';
  h += '<div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px">Comprobante de compra</div>';
  h += `<div style="font-size:24px;font-weight:700;color:#193a2c;margin:4px 0">${info.folio||''}</div>`;
  h += `<div style="font-size:12px;color:#888">${formatearFecha(info.fecha || new Date().toISOString())}</div>`;
  if (info.estado) h += `<span class="badge-estado ${estadoClass(info.estado)}" style="font-size:11px;margin-top:6px;display:inline-block">${estadoLabel(info.estado)}</span>`;
  if (info.canal) h += `<div style="font-size:11px;color:#888;margin-top:4px">Canal: ${canalLabel(info.canal)}</div>`;
  h += '</div>';

  h += '<div style="padding:0 20px 16px">';

  // Cliente
  if (info.cliente_nombre) {
    h += secLabel('Cliente');
    h += `<div style="font-size:13px;font-weight:600">${info.cliente_nombre}</div>`;
    if (info.cliente_telefono) h += `<div style="font-size:12px;color:#888">${info.cliente_telefono}</div>`;
  }

  // Entrega
  const tipo = info.tipo || 'mostrador';
  if (tipo === 'funeral' || (info.funeraria)) {
    h += secLabel('Funeral');
    h += '<div style="display:flex;flex-wrap:wrap;gap:8px">';
    h += gridItem('Funeraria', info.funeraria);
    h += gridItem('Fallecido', info.nombre_fallecido);
    h += gridItem('Sala', info.sala);
    h += gridItem('Banda', info.banda);
    h += gridItem('Fecha', formatearFecha(info.fecha_entrega));
    h += gridItem('Velacion', info.horario_velacion);
    h += '</div>';
    if (info.dedicatoria) {
      h += secLabel('Dedicatoria');
      h += `<div style="background:#fffdf7;border-left:3px solid #d4a843;padding:10px 12px;font-style:italic;font-size:12px;border-radius:0 6px 6px 0">"${info.dedicatoria}"</div>`;
    }
  } else if (info.direccion_entrega) {
    h += secLabel('Entrega');
    h += '<div style="display:flex;flex-wrap:wrap;gap:8px">';
    h += gridItem('Recibe', info.receptor_nombre);
    h += gridItem('Tel', info.receptor_telefono);
    h += '</div>';
    if (info.direccion_entrega) h += `<div style="margin-top:6px"><div style="font-size:10px;color:#888">Direccion</div><div style="font-size:12px;font-weight:600">${info.direccion_entrega}</div></div>`;
    h += '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px">';
    h += gridItem('Fecha', formatearFecha(info.fecha_entrega));
    h += gridItem('Horario', info.horario_entrega);
    if (info.hora_exacta) h += gridItem('Hora', info.hora_exacta);
    h += gridItem('Zona', info.zona_envio);
    h += gridItem('Ruta', info.ruta);
    h += '</div>';
    if (info.dedicatoria) {
      h += secLabel('Dedicatoria');
      h += `<div style="background:#fffdf7;border-left:3px solid #d4a843;padding:10px 12px;font-style:italic;font-size:12px;border-radius:0 6px 6px 0">"${info.dedicatoria}"</div>`;
    }
    if (info.notas_internas) h += `<div style="font-size:11px;color:#888;margin-top:6px"><strong>Notas:</strong> ${info.notas_internas}</div>`;
  } else if (tipo === 'recoger') {
    h += secLabel('Recoger en tienda');
    h += '<div style="display:flex;flex-wrap:wrap;gap:8px">';
    h += gridItem('Fecha', formatearFecha(info.fecha_entrega));
    h += gridItem('Hora', info.hora_exacta);
    h += '</div>';
  }

  // Articulos
  h += secLabel('Articulos');
  (info.items||[]).forEach(it => {
    const price = (it.precio_unitario || it.precio || 0) * (it.cantidad || 1);
    h += `<div style="display:flex;justify-content:space-between;font-size:12px;padding:5px 0;border-bottom:1px solid #f0ede8">
      <span>${it.cantidad||1}x ${it.nombre||''}</span>
      <span style="font-weight:600">${fP(price)}</span>
    </div>`;
  });

  // Totales
  h += secLabel('Totales');
  h += row2('Subtotal', fP(info.subtotal||0));
  if (info.envio) h += row2('Envio ' + (info.zona_envio||''), fP(info.envio));
  if (info.impuesto) h += row2('IVA (16%)', fP(info.impuesto));
  if (info.cargo_hora) h += row2('Hora especifica', '+' + fP(info.cargo_hora));
  if (info.comision) h += row2('Comision link (4%)', '+' + fP(info.comision));
  if (info.descuento) h += `<div style="display:flex;justify-content:space-between;font-size:12px;padding:2px 0;color:#d4a843"><span>Descuento</span><span style="font-weight:600">-${fP(info.descuento)}</span></div>`;
  // If we don't have individual breakdowns, show diff
  if (!info.impuesto && !info.cargo_hora && !info.comision && !info.descuento) {
    const diff = (info.total||0) - (info.subtotal||0) - (info.envio||0);
    if (diff > 0) h += row2('Impuestos / Cargos', '+' + fP(diff));
    if (diff < 0) h += `<div style="display:flex;justify-content:space-between;font-size:12px;padding:2px 0;color:#d4a843"><span>Descuento</span><span style="font-weight:600">-${fP(Math.abs(diff))}</span></div>`;
  }
  h += `<div style="display:flex;justify-content:space-between;font-size:16px;font-weight:700;color:#193a2c;padding:10px 0 4px;border-top:2px solid #193a2c;margin-top:6px"><span>TOTAL</span><span>${fP(info.total||0)}</span></div>`;

  // Forma de pago
  h += secLabel('Forma de pago');
  if (info.pagos && info.pagos.length) {
    info.pagos.forEach(p => { if(p.monto) h += row2(p.nombre||'', fP(p.monto)); });
  } else if (info.forma_pago) {
    h += `<div style="font-size:12px">${info.forma_pago}</div>`;
  }

  h += '</div>'; // /padding container

  // Footer
  h += '<div style="background:#193a2c;padding:14px 20px;text-align:center;margin-top:8px">';
  h += '<div style="font-size:13px;font-weight:600;color:#d4a843">¡Gracias por tu preferencia!</div>';
  h += '<div style="font-size:10px;color:rgba(255,255,255,.6);margin-top:4px">C. Sabino 610, Las Granjas · 614 334 9392</div>';
  h += '<div style="font-size:10px;color:rgba(255,255,255,.6)">florerialucychihuahua@gmail.com</div>';
  h += '</div>';

  return h;
}

function verTicket(p) {
  ticketPedido = p;
  const info = buildInfoFromPedido(p);
  info.estado = p.estado;
  info.canal = p.canal;
  document.getElementById('ticket-content').innerHTML = buildTicketDigital(info);
  // Buttons
  let btns = '<button onclick="reimprimirDesdeTicket()" style="flex:1;padding:10px;background:var(--verde);color:#fff;border:none;border-radius:8px;font-weight:600;font-size:12px;cursor:pointer">🖨 Imprimir</button>';
  if (p.cliente_telefono) btns += '<button onclick="enviarWaDesdeTicket()" style="flex:1;padding:10px;background:#25D366;color:#fff;border:none;border-radius:8px;font-weight:600;font-size:12px;cursor:pointer">💬 WhatsApp</button>';
  btns += `<button onclick="document.getElementById('modal-ticket').classList.remove('active')" style="flex:1;padding:10px;background:var(--gris);color:var(--texto2);border:none;border-radius:8px;font-weight:600;font-size:12px;cursor:pointer">✕ Cerrar</button>`;
  document.getElementById('ticket-buttons').innerHTML = btns;
  document.getElementById('modal-ticket').classList.add('active');
}

function reimprimirDesdeTicket() {
  const p = ticketPedido;
  if (!p) return;
  document.getElementById('print-frame').innerHTML = buildTicketCompleto(buildInfoFromPedido(p));
  setTimeout(() => window.print(), 100);
}

async function enviarWaDesdeTicket() {
  const p = ticketPedido;
  if (!p || !p.cliente_telefono) return;
  // Capture ticket as image and send
  try {
    const tc = document.getElementById('ticket-content');
    const canvas = await html2canvas(tc, {scale:2, backgroundColor:'#ffffff'});
    const b64 = canvas.toDataURL('image/png').split(',')[1];
    const r = await fetch('/pos/enviar-ticket-whatsapp', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({pedido_id: p.id, telefono: p.cliente_telefono, nombre_cliente: p.cliente_nombre || '', imagen_base64: b64})
    });
    const data = await r.json();
    if (data.ok) alert('Ticket enviado por WhatsApp');
    else alert(data.error || 'Error al enviar');
  } catch(e) { alert('Error: ' + e.message); }
}

// ═══════════════════════════════════════════
// UTIL
// ═══════════════════════════════════════════
function esc(s) { return (s||'').replace(/'/g, "\\'").replace(/"/g, '&quot;'); }

function sanitizarTexto(s) {
  return (s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/ñ/g,'N').replace(/Ñ/g,'N').replace(/ü/g,'U').replace(/Ü/g,'U').toUpperCase();
}

function fmtPrecioTk(centavos) {
  return '$' + (centavos/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
}

function fechaTicket(str) {
  if (!str) return '';
  const d = new Date((str||'').replace(' ','T'));
  if (isNaN(d)) return sanitizarTexto(str);
  const dias = ['DOM','LUN','MAR','MIE','JUE','VIE','SAB'];
  const meses = ['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'];
  const dia = dias[d.getDay()];
  const dd = d.getDate();
  const mes = meses[d.getMonth()];
  const yyyy = d.getFullYear();
  const hasTime = (str||'').includes(':');
  if (!hasTime) return `${dia} ${dd} ${mes} ${yyyy}`;
  let h = d.getHours(), m = d.getMinutes();
  const ap = h >= 12 ? 'PM' : 'AM';
  if (h === 0) h = 12; else if (h > 12) h -= 12;
  return `${dia} ${dd} ${mes} ${yyyy}  ${h}:${String(m).padStart(2,'0')} ${ap}`;
}

function fechaLargaHoy() {
  const d = new Date();
  const meses = ['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO','JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE'];
  return `CHIHUAHUA, CHIH., A ${d.getDate()} DE ${meses[d.getMonth()]} DE ${d.getFullYear()}`;
}

const _dias = ['DOM','LUN','MAR','MIÉ','JUE','VIE','SÁB'];
const _meses = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
function formatearFecha(str) {
  if (!str) return '';
  // Accept "2026-03-27 22:30" or "2026-03-27" or ISO
  const d = new Date(str.replace(' ', 'T'));
  if (isNaN(d)) return str;
  const dia = _dias[d.getDay()];
  const dd = d.getDate();
  const mes = _meses[d.getMonth()];
  const yyyy = d.getFullYear();
  // If time portion exists
  const hasTime = str.includes(':');
  if (!hasTime) return `${dia} ${dd} ${mes} ${yyyy}`;
  let h = d.getHours(), m = d.getMinutes();
  const ampm = h >= 12 ? 'pm' : 'am';
  if (h === 0) h = 12; else if (h > 12) h -= 12;
  return `${dia} ${dd} ${mes} ${yyyy}, ${h}:${String(m).padStart(2,'0')} ${ampm}`;
}

function buildHoraOptions() {
  let html = '<option value="">Seleccionar hora</option>';
  for (let h = 9; h <= 21; h++) {
    for (let m = 0; m < 60; m += 30) {
      if (h === 21 && m > 0) break;
      const val24 = String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0');
      let dh = h > 12 ? h - 12 : (h === 0 ? 12 : h);
      const ap = h >= 12 ? 'pm' : 'am';
      html += `<option value="${val24}">${dh}:${String(m).padStart(2,'0')} ${ap}</option>`;
    }
  }
  return html;
}

// ═══════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════
fetchProds();
fetchCategorias();
setView(vistaActual);
renderCart();

// Badge pendientes — local render + polling every 60s to sync with DB
function renderBadge() {
  const badge = document.getElementById('badge-pend');
  if (contadorPendientes <= 0) {
    contadorPendientes = 0;
    badge.style.display = 'none';
  } else {
    badge.style.display = 'flex';
    badge.textContent = contadorPendientes > 9 ? '9+' : contadorPendientes;
  }
}

async function updateBadgePend() {
  try {
    const r = await fetch('/pos/pedidos-hoy?estado=pendiente_pago');
    const data = await r.json();
    contadorPendientes = (data.pendientes || []).length;
    renderBadge();
    // Auto-refresh if pendientes section is active
    if (document.getElementById('sec-pendientes').classList.contains('active') && pendFilterPeriodo === 'hoy') {
      pendAllData = data.pendientes || [];
      const q = document.getElementById('pend-search').value.trim();
      if (q) filtrarTablaPend(); else renderPendTable(pendAllData);
    }
    // Auto-refresh transacciones if active
    if (document.getElementById('sec-transacciones').classList.contains('active') && transFilterPeriodo === 'hoy') {
      loadTransacciones();
    }
  } catch(e) { /* silent */ }
}
updateBadgePend();
setInterval(updateBadgePend, 60000);

async function confirmarPagoPos(id) {
  if (!confirm('Confirmar que el pago fue verificado?')) return;
  try {
    const r = await fetch(`/pedidos/${id}/confirmar-pago`, {method:'POST', credentials:'include'});
    if (r.ok) {
      loadPendientes();
      updateBadgePend();
    } else {
      const err = await r.json().catch(() => ({}));
      alert(err.detail || 'Error al confirmar pago');
    }
  } catch(e) { alert('Error de conexion'); }
}
