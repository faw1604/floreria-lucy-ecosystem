/* ═══════════════════════════════════════════
   ADMIN PANEL — Florería Lucy
   ═══════════════════════════════════════════ */

const API = '';
const WHATSAPP = '5216143349392';

// ══════ NAVIGATION ══════
function navTo(sec) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.sb-item').forEach(s => s.classList.remove('active'));
  const secEl = document.getElementById('sec-' + sec);
  const sbEl = document.getElementById('sb-' + sec);
  if (secEl) secEl.classList.add('active');
  if (sbEl) sbEl.classList.add('active');
  location.hash = sec;
  // Load data for section
  const loaders = {
    productos: loadProductos,
    claudia: loadClaudia,
    web: loadWeb,
    finanzas: loadFinanzas,
    estadisticas: loadEstadisticas,
    usuarios: loadUsuarios,
    config: loadConfig,
  };
  if (loaders[sec]) loaders[sec]();
}

// Init from hash
(function() {
  const hash = location.hash.replace('#', '') || 'ventas';
  navTo(hash);
})();

function logout() {
  fetch(API + '/auth/logout', {credentials:'include'});
  location.href = '/panel/';
}

function cerrarModal(id) {
  document.getElementById(id).classList.remove('active');
}

function showToast(msg) {
  let t = document.querySelector('.toast');
  if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

function esc(s) { return (s||'').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function fmt$(cents) { return '$' + ((cents||0)/100).toLocaleString(); }
function fmtDate(d) { if (!d) return ''; return new Date(d).toLocaleDateString('es-MX', {timeZone:'America/Chihuahua', day:'2-digit', month:'short', year:'numeric'}); }

// Sub-tab helpers
function webSubTab(id) { switchSubTab('web', id); }
function finSubTab(id) { switchSubTab('fin', id); }
function cfgSubTab(id) { switchSubTab('cfg', id); }

function switchSubTab(prefix, id) {
  const parent = document.getElementById('sec-' + (prefix === 'cfg' ? 'config' : prefix === 'fin' ? 'finanzas' : 'web'));
  parent.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
  parent.querySelectorAll('.sub-content').forEach(c => c.style.display = 'none');
  event.target.classList.add('active');
  document.getElementById(id + '-content').style.display = '';
}

// ══════ PENDIENTES ══════
async function loadPendientes() {
  try {
    const canal = document.getElementById('pend-canal-filter').value;
    const estado = document.getElementById('pend-estado-filter').value;
    let url = API + '/pos/pedidos-hoy?periodo=mes&estado=pendiente_pago';
    if (canal) url += '&canal=' + canal;
    const r = await fetch(url, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    let rows = [...(data.pendientes || [])];
    if (estado) rows = rows.filter(p => p.estado === estado);
    const tbody = document.getElementById('pend-tbody');
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--texto2);padding:40px">Sin pedidos pendientes</td></tr>'; return; }
    tbody.innerHTML = rows.map(p => {
      const items = (p.items||[]).map(i => i.cantidad + 'x ' + esc(i.nombre)).join(', ');
      return `<tr>
        <td style="font-weight:600;color:var(--verde)">${esc(p.folio)}</td>
        <td>${esc(p.cliente_nombre||'Mostrador')}</td>
        <td>${p.canal === 'WhatsApp' ? '🤖' : p.canal === 'Web' ? '🌐' : '🛒'} ${esc(p.canal)}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(items)}">${items||'—'}</td>
        <td style="font-weight:600">${fmt$(p.total)}</td>
        <td>${badgeEstado(p.estado)}</td>
        <td>${fmtDate(p.fecha_entrega)}</td>
        <td><button class="btn-sm" onclick="confirmarPagoPend(${p.id})">✓ Confirmar</button></td>
      </tr>`;
    }).join('');
    // Badge
    const badge = document.getElementById('badge-pend');
    if (rows.length > 0) { badge.style.display = 'flex'; badge.textContent = rows.length > 9 ? '9+' : rows.length; }
    else badge.style.display = 'none';
  } catch(e) { console.error(e); }
}

function badgeEstado(estado) {
  const map = {
    'esperando_validacion': ['Esperando validación', 'badge-validacion'],
    'pendiente_pago': ['Pendiente pago', 'badge-pendiente'],
    'Pendiente pago': ['Pendiente pago', 'badge-pendiente'],
    'comprobante_recibido': ['Comprobante recibido', 'badge-comprobante'],
    'pagado': ['Pagado', 'badge-pagado'],
    'Listo': ['Pagado', 'badge-pagado'],
    'Cancelado': ['Cancelado', 'badge-cancelado'],
  };
  const [label, cls] = map[estado] || [estado, 'badge-pendiente'];
  return `<span class="badge-estado ${cls}">${label}</span>`;
}

async function confirmarPagoPend(id) {
  if (!confirm('¿Confirmar pago de este pedido?')) return;
  await fetch(API + '/pedidos/' + id + '/confirmar-pago', {method:'POST', credentials:'include'});
  loadPendientes();
}

// ══════ TRANSACCIONES ══════
async function loadTransacciones() {
  try {
    const periodo = document.getElementById('trans-periodo').value;
    const r = await fetch(API + '/pos/pedidos-hoy?periodo=' + periodo, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    const rows = data.finalizados || [];
    const resumen = data.resumen || {};
    // KPIs
    document.getElementById('trans-kpis').innerHTML = `
      <div class="kpi-card"><div class="kpi-label">Total vendido</div><div class="kpi-value">${fmt$(resumen.total_vendido)}</div></div>
      <div class="kpi-card"><div class="kpi-label">Transacciones</div><div class="kpi-value">${resumen.num_finalizados||0}</div></div>
      ${Object.entries(resumen.desglose_pago||{}).map(([k,v]) => `<div class="kpi-card"><div class="kpi-label">${esc(k)}</div><div class="kpi-value">${fmt$(v)}</div></div>`).join('')}
    `;
    const tbody = document.getElementById('trans-tbody');
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--texto2);padding:40px">Sin transacciones</td></tr>'; return; }
    tbody.innerHTML = rows.map(p => `<tr>
      <td style="font-weight:600;color:var(--verde)">${esc(p.folio)}</td>
      <td>${esc(p.cliente_nombre||'Mostrador')}</td>
      <td>${esc(p.canal)}</td>
      <td style="font-weight:600">${fmt$(p.total)}</td>
      <td>${esc(p.forma_pago||'—')}</td>
      <td>${badgeEstado(p.estado)}</td>
      <td>${fmtDate(p.fecha_entrega)}</td>
      <td><button class="btn-sm" onclick="window.open('/pedidos/${p.id}/ticket-digital','_blank')">🧾 Ticket</button></td>
    </tr>`).join('');
  } catch(e) { console.error(e); }
}

// ══════ CLIENTES ══════
let cliSearchTimeout = null;
function debounceCliSearch() { clearTimeout(cliSearchTimeout); cliSearchTimeout = setTimeout(loadClientes, 300); }

async function loadClientes() {
  try {
    const q = (document.getElementById('cli-search')?.value || '').trim();
    let url = API + '/clientes/';
    if (q) url += '?busqueda=' + encodeURIComponent(q);
    const r = await fetch(url, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    const tbody = document.getElementById('cli-tbody');
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--texto2);padding:40px">Sin clientes</td></tr>'; return; }
    tbody.innerHTML = data.slice(0, 100).map(c => `<tr>
      <td style="font-weight:500">${esc(c.nombre)}</td>
      <td>${esc(c.telefono)}</td>
      <td>${esc(c.email||'—')}</td>
      <td>${c.total_pedidos||0}</td>
      <td>${fmt$(c.total_gastado||0)}</td>
      <td>${fmtDate(c.ultima_compra)}</td>
      <td>
        <button class="btn-sm" onclick="verCliente(${c.id})">Ver</button>
        <a class="btn-sm" href="https://wa.me/52${c.telefono}" target="_blank" style="text-decoration:none">💬</a>
      </td>
    </tr>`).join('');
  } catch(e) { console.error(e); }
}

async function verCliente(id) {
  try {
    const r = await fetch(API + '/clientes/' + id, {credentials:'include'});
    if (!r.ok) return;
    const c = await r.json();
    document.getElementById('modal-cli-title').textContent = c.nombre;
    document.getElementById('modal-cli-body').innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
        <div class="field"><label>Nombre</label><input value="${esc(c.nombre)}" id="cli-edit-nombre"></div>
        <div class="field"><label>Teléfono</label><input value="${esc(c.telefono)}" id="cli-edit-tel"></div>
        <div class="field"><label>Email</label><input value="${esc(c.email||'')}" id="cli-edit-email"></div>
        <div class="field"><label>Dirección</label><input value="${esc(c.direccion_default||'')}" id="cli-edit-dir"></div>
      </div>
      <button class="btn-primary" onclick="guardarCliente(${c.id})">Guardar cambios</button>
    `;
    document.getElementById('modal-cliente').classList.add('active');
  } catch(e) {}
}

async function guardarCliente(id) {
  await fetch(API + '/clientes/' + id, {
    method: 'PUT', headers: {'Content-Type':'application/json'}, credentials: 'include',
    body: JSON.stringify({
      nombre: document.getElementById('cli-edit-nombre').value,
      telefono: document.getElementById('cli-edit-tel').value,
      email: document.getElementById('cli-edit-email').value || null,
      direccion_default: document.getElementById('cli-edit-dir').value || null,
    })
  });
  cerrarModal('modal-cliente');
  showToast('Cliente actualizado ✓');
  loadClientes();
}

async function exportarClientes() {
  try {
    const r = await fetch(API + '/clientes/', {credentials:'include'});
    const data = await r.json();
    let csv = 'Nombre,Telefono,Email,Pedidos,Total\n';
    data.forEach(c => { csv += `"${c.nombre}","${c.telefono}","${c.email||''}",${c.total_pedidos||0},${(c.total_gastado||0)/100}\n`; });
    const blob = new Blob([csv], {type:'text/csv'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'clientes_floreria_lucy.csv'; a.click();
  } catch(e) {}
}

// ══════ PRODUCTOS ══════
let prodSearchTimeout = null;
let prodVariantesCache = {};
let prodAllData = [];
let prodOffset = 0;
const PROD_PAGE = 50;
let prodLoading = false;
let prodHasMore = true;
let prodCatsLoaded = false;
function debounceProdSearch() { clearTimeout(prodSearchTimeout); prodSearchTimeout = setTimeout(() => { prodOffset = 0; prodAllData = []; prodHasMore = true; loadProductos(); }, 300); }

function prodFilterUrl() {
  const status = document.getElementById('prod-status-filter')?.value || '';
  const cat = document.getElementById('prod-cat-filter')?.value || '';
  const activoVal = status === '1' ? 'true' : status === '0' ? 'false' : 'todos';
  let url = API + '/productos/?activo=' + activoVal + '&offset=' + prodOffset + '&limit=' + PROD_PAGE;
  if (cat) url += '&categoria=' + encodeURIComponent(cat);
  return url;
}

async function loadProductos(append) {
  if (prodLoading) return;
  if (!append) { prodOffset = 0; prodAllData = []; prodHasMore = true; }
  if (!prodHasMore) return;
  prodLoading = true;
  try {
    const r = await fetch(prodFilterUrl(), {credentials:'include'});
    if (!r.ok) return;
    let data = await r.json();
    if (data.length < PROD_PAGE) prodHasMore = false;
    prodOffset += data.length;
    // Client-side search filter
    const q = (document.getElementById('prod-search')?.value || '').trim();
    if (q) { const ql = q.toLowerCase(); data = data.filter(p => p.nombre.toLowerCase().includes(ql) || (p.codigo||'').toLowerCase().includes(ql)); }
    prodAllData = append ? prodAllData.concat(data) : data;
    // Populate category filter once
    if (!prodCatsLoaded) {
      prodCatsLoaded = true;
      const catR = await fetch(API + '/productos/?activo=todos&limit=0', {credentials:'include'});
      if (catR.ok) {
        const allProds = await catR.json();
        const allCats = [...new Set(allProds.map(p => p.categoria))].filter(Boolean).sort();
        const catSel = document.getElementById('prod-cat-filter');
        if (catSel.options.length <= 1) allCats.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; catSel.appendChild(o); });
      }
    }
    renderProdTable();
  } catch(e) { console.error(e); }
  prodLoading = false;
}

function renderProdTable() {
  const tbody = document.getElementById('prod-tbody');
  if (!prodAllData.length) { tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--texto2);padding:40px">Sin productos</td></tr>'; return; }
  tbody.innerHTML = prodAllData.map(p => `<tr>
    <td><input type="checkbox" class="prod-check" data-id="${p.id}"></td>
    <td>${p.imagen_url ? '<img src="'+esc(p.imagen_url)+'" class="thumb">' : '—'}</td>
    <td style="font-weight:500">${esc(p.nombre)}${p.precio_descuento ? ' <span style="color:var(--dorado);font-size:10px">OFERTA</span>' : ''}</td>
    <td style="color:var(--texto2)">${esc(p.codigo||'—')}</td>
    <td>${esc(p.categoria)}</td>
    <td style="font-weight:600">${p.precio_descuento ? '<span style="text-decoration:line-through;color:#999;font-weight:400">'+fmt$(p.precio)+'</span> '+fmt$(p.precio_descuento) : fmt$(p.precio)}</td>
    <td>${p.activo ? '<span style="color:var(--verde)">Si</span>' : '<span style="color:var(--rojo)">No</span>'}</td>
    <td><input type="checkbox" ${p.visible_catalogo !== false ? 'checked' : ''} onchange="toggleWebProdQuick(${p.id}, this.checked)" title="Visible en catálogo web"></td>
    <td id="var-badge-${p.id}"></td>
    <td><button class="btn-sm" onclick="editarProducto(${p.id})">Editar</button></td>
  </tr>`).join('');
  if (prodHasMore) {
    tbody.innerHTML += '<tr id="prod-sentinel"><td colspan="10" style="text-align:center;padding:12px;color:var(--texto2);font-size:12px">Cargando más...</td></tr>';
    observeProdSentinel();
  }
}

let prodObserver = null;
function observeProdSentinel() {
  if (prodObserver) prodObserver.disconnect();
  const sentinel = document.getElementById('prod-sentinel');
  if (!sentinel) return;
  prodObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && prodHasMore && !prodLoading) loadProductos(true);
  }, {rootMargin: '200px'});
  prodObserver.observe(sentinel);
}

async function loadVariantesBadge(prodId) {
  try {
    const r = await fetch(API + '/api/admin/variantes/' + prodId, {credentials:'include'});
    if (!r.ok) return;
    const vars = await r.json();
    prodVariantesCache[prodId] = vars;
    const el = document.getElementById('var-badge-' + prodId);
    if (el && vars.filter(v => v.activo).length > 0) {
      el.innerHTML = '<span style="background:var(--dorado);color:var(--verde);padding:2px 8px;border-radius:6px;font-size:10px;font-weight:600">Variantes</span>';
    }
  } catch(e) {}
}

async function toggleWebProdQuick(id, visible) {
  await fetch(API + '/productos/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({visible_catalogo: visible})});
}

function toggleAllProds() {
  const checked = document.getElementById('prod-check-all').checked;
  document.querySelectorAll('.prod-check').forEach(c => c.checked = checked);
}

async function masivoProd(accion) {
  const ids = [...document.querySelectorAll('.prod-check:checked')].map(c => parseInt(c.dataset.id));
  if (!ids.length) return alert('Selecciona al menos un producto');
  for (const id of ids) {
    await fetch(API + '/productos/' + id, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({activo: accion === 'activar'})});
  }
  showToast(`${ids.length} productos ${accion === 'activar' ? 'activados' : 'desactivados'}`);
  loadProductos();
}

// --- MODAL PRODUCTO ---
let editingProdId = null;
let editingVariantes = [];

async function abrirModalProducto(prod) {
  editingProdId = prod?.id || null;
  editingVariantes = [];
  document.getElementById('modal-prod-title').textContent = prod ? 'Editar producto' : 'Nuevo producto';

  // Load categories for select
  let catOptions = '';
  try {
    const r = await fetch(API + '/api/admin/categorias', {credentials:'include'});
    const cats = await r.json();
    catOptions = cats.map(c => `<option value="${esc(c.nombre)}" ${prod?.categoria === c.nombre ? 'selected' : ''} data-tipo="${c.tipo}">${esc(c.nombre)}</option>`).join('');
  } catch(e) {}

  // Load variantes if editing
  if (prod?.id) {
    try {
      const r = await fetch(API + '/api/admin/variantes/' + prod.id, {credentials:'include'});
      editingVariantes = await r.json();
    } catch(e) {}
  }

  const hasActiveVariants = editingVariantes.filter(v => v.activo).length > 0;

  document.getElementById('modal-prod-body').innerHTML = `
    <!-- FOTO -->
    <div class="field">
      <label>Foto del producto</label>
      <div style="display:flex;align-items:flex-start;gap:12px">
        <div id="pf-img-preview" style="width:100px;height:100px;border-radius:10px;background:var(--borde);display:flex;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0">
          ${prod?.imagen_url ? '<img src="'+esc(prod.imagen_url)+'" style="width:100%;height:100%;object-fit:cover">' : '<span style="color:var(--texto2);font-size:24px">📷</span>'}
        </div>
        <div style="flex:1">
          <input type="file" id="pf-img-file" accept="image/*" onchange="subirImagenProd()">
          <input type="hidden" id="pf-img" value="${esc(prod?.imagen_url||'')}">
          <div id="pf-img-status" style="font-size:11px;color:var(--texto2);margin-top:4px"></div>
        </div>
      </div>
    </div>
    <!-- BÁSICO -->
    <div class="field"><label>Nombre *</label><input id="pf-nombre" value="${esc(prod?.nombre||'')}"></div>
    <div class="field"><label>Categoría *</label><select id="pf-cat" onchange="onCatChange()"><option value="">Selecciona...</option>${catOptions}</select></div>
    <div class="field"><label>Código *</label><input id="pf-sku" value="${esc(prod?.codigo||'')}"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div class="field"><label>Precio *</label><input type="number" id="pf-precio" value="${prod ? (prod.precio/100).toFixed(2) : ''}" step="0.01"></div>
      <div class="field"><label>Precio de oferta</label><input type="number" id="pf-precio-desc" value="${prod?.precio_descuento ? (prod.precio_descuento/100).toFixed(2) : ''}" step="0.01">
        <div style="font-size:10px;color:var(--texto2)">Si tiene valor, el precio normal aparece tachado</div>
      </div>
    </div>
    <!-- DESCRIPCIÓN + IA -->
    <div class="field">
      <label>Descripción</label>
      <textarea id="pf-desc" rows="3">${esc(prod?.descripcion||'')}</textarea>
      <div style="display:flex;gap:6px;margin-top:6px">
        <button class="btn-sm" onclick="generarDescIA(false)" id="pf-ia-gen">Generar con IA</button>
        <button class="btn-sm" onclick="generarDescIA(true)" id="pf-ia-mej">Mejorar con IA</button>
        <span id="pf-ia-spinner" style="display:none;font-size:12px;color:var(--texto2)">Generando...</span>
      </div>
    </div>
    <div style="display:flex;gap:12px;margin:12px 0">
      <label style="display:flex;align-items:center;gap:6px;font-size:13px"><input type="checkbox" id="pf-activo" ${prod?.activo !== false ? 'checked' : ''}> Activo</label>
      <label style="display:flex;align-items:center;gap:6px;font-size:13px"><input type="checkbox" id="pf-web" ${prod?.visible_catalogo !== false ? 'checked' : ''}> Visible en web</label>
      <label style="display:flex;align-items:center;gap:6px;font-size:13px;display:none" id="pf-funeral-wrap"><input type="checkbox" id="pf-funeral"> Es funeral</label>
    </div>
    <!-- STOCK -->
    <div style="border:1px solid var(--borde);border-radius:10px;padding:14px;margin:14px 0">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <label style="font-size:13px;font-weight:600">Control de stock</label>
        <input type="checkbox" id="pf-stock-activo" ${prod?.stock_activo ? 'checked' : ''} onchange="onStockToggle()" ${hasActiveVariants ? 'disabled' : ''}>
      </div>
      ${hasActiveVariants ? '<div style="font-size:11px;color:var(--naranja);margin-bottom:6px">El stock lo controla cada variante</div>' : '<div style="font-size:11px;color:var(--texto2);margin-bottom:6px">Stock desactivado = siempre disponible. Actívalo para controlar piezas limitadas.</div>'}
      <div id="pf-stock-field" style="${prod?.stock_activo && !hasActiveVariants ? '' : 'display:none'}">
        <div class="field"><label>Unidades en stock</label><input type="number" id="pf-stock" value="${prod?.stock||0}" min="0"></div>
      </div>
    </div>
    <!-- VARIANTES -->
    <div style="border:1px solid var(--borde);border-radius:10px;padding:14px;margin:14px 0">
      <div style="font-size:13px;font-weight:600;margin-bottom:10px">Variantes</div>
      ${['color','tamaño','estilo'].map(tipo => {
        const vars = editingVariantes.filter(v => v.tipo === tipo);
        const hasVars = vars.length > 0;
        return `<div style="border-bottom:1px solid var(--borde);padding:8px 0">
          <div style="display:flex;align-items:center;justify-content:space-between">
            <label style="font-size:13px;font-weight:500;text-transform:capitalize">${tipo}</label>
            <input type="checkbox" class="var-toggle" data-tipo="${tipo}" ${hasVars ? 'checked' : ''} onchange="toggleVarianteTipo('${tipo}', this.checked)">
          </div>
          <div id="var-${tipo}-list" style="${hasVars ? '' : 'display:none'};margin-top:8px">
            ${vars.map(v => renderVarianteRow(v)).join('')}
            <button class="btn-sm" onclick="addVarianteRow('${tipo}')" style="margin-top:6px">+ Agregar ${tipo}</button>
          </div>
        </div>`;
      }).join('')}
    </div>
    <button class="btn-primary" onclick="guardarProducto(${prod?.id||'null'})" style="width:100%;margin-top:12px">Guardar producto</button>
  `;
  onCatChange();
  document.getElementById('modal-producto').classList.add('active');
}

function renderVarianteRow(v) {
  const uid = 'vr-' + Math.random().toString(36).substr(2,6);
  return `<div class="var-row" data-var-id="${v.id||''}" data-tipo="${v.tipo}" style="background:var(--crema);border-radius:8px;padding:10px;margin-bottom:6px;position:relative">
    <button onclick="this.parentElement.remove()" style="position:absolute;top:4px;right:6px;background:none;border:none;color:var(--rojo);font-size:16px;cursor:pointer">&times;</button>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
      <div class="field" style="margin-bottom:6px"><label style="font-size:11px">Nombre</label><input class="vr-nombre" value="${esc(v.nombre||'')}" style="font-size:12px;padding:6px 8px"></div>
      <div class="field" style="margin-bottom:6px"><label style="font-size:11px">Código</label><input class="vr-codigo" value="${esc(v.codigo||'')}" style="font-size:12px;padding:6px 8px"></div>
      <div class="field" style="margin-bottom:6px"><label style="font-size:11px">Precio</label><input type="number" class="vr-precio" value="${v.precio ? (v.precio/100).toFixed(2) : ''}" step="0.01" style="font-size:12px;padding:6px 8px"></div>
      <div class="field" style="margin-bottom:6px"><label style="font-size:11px">Precio oferta</label><input type="number" class="vr-precio-desc" value="${v.precio_descuento ? (v.precio_descuento/100).toFixed(2) : ''}" step="0.01" style="font-size:12px;padding:6px 8px"></div>
      <div class="field" style="margin-bottom:6px"><label style="font-size:11px;display:flex;align-items:center;gap:4px">Controlar stock <input type="checkbox" class="vr-stock-activo" ${v.stock_activo ? 'checked' : ''} onchange="this.closest('.var-row').querySelector('.vr-stock-wrap').style.display=this.checked?'':'none'"></label></div>
      <div class="field vr-stock-wrap" style="margin-bottom:6px;${v.stock_activo ? '' : 'display:none'}"><label style="font-size:11px">Stock</label><input type="number" class="vr-stock" value="${v.stock||0}" min="0" style="font-size:12px;padding:6px 8px"></div>
      <div class="field" style="margin-bottom:0;grid-column:1/-1"><label style="font-size:11px">Foto</label><input type="file" class="vr-img-file" accept="image/*" style="font-size:11px"><input type="hidden" class="vr-img" value="${esc(v.imagen_url||'')}"></div>
    </div>
  </div>`;
}

function addVarianteRow(tipo) {
  const list = document.getElementById('var-' + tipo + '-list');
  const codigo = document.getElementById('pf-sku')?.value || '';
  const btn = list.querySelector('button');
  const row = document.createElement('div');
  row.innerHTML = renderVarianteRow({tipo, nombre:'', codigo: codigo ? codigo + '-' : '', precio:0, stock:0});
  btn.before(row.firstElementChild);
}

function toggleVarianteTipo(tipo, checked) {
  const list = document.getElementById('var-' + tipo + '-list');
  list.style.display = checked ? '' : 'none';
  if (checked && !list.querySelector('.var-row')) addVarianteRow(tipo);
  updateStockByVariantes();
}

function updateStockByVariantes() {
  const hasActiveVars = document.querySelectorAll('.var-row').length > 0;
  const stockToggle = document.getElementById('pf-stock-activo');
  if (hasActiveVars) {
    stockToggle.checked = false;
    stockToggle.disabled = true;
    document.getElementById('pf-stock-field').style.display = 'none';
  } else {
    stockToggle.disabled = false;
  }
}

function onStockToggle() {
  document.getElementById('pf-stock-field').style.display = document.getElementById('pf-stock-activo').checked ? '' : 'none';
}

function onCatChange() {
  const sel = document.getElementById('pf-cat');
  const opt = sel?.options[sel.selectedIndex];
  const wrap = document.getElementById('pf-funeral-wrap');
  if (wrap) wrap.style.display = opt?.dataset?.tipo === 'funeral' ? 'flex' : 'none';
}

async function editarProducto(id) {
  const r = await fetch(API + '/productos/' + id, {credentials:'include'});
  if (!r.ok) return;
  const p = await r.json();
  abrirModalProducto(p);
}

async function subirImagenProd() {
  const file = document.getElementById('pf-img-file').files[0];
  if (!file) return;
  document.getElementById('pf-img-status').textContent = 'Subiendo...';
  const fd = new FormData();
  fd.append('imagen', file);
  try {
    const r = await fetch(API + '/productos/subir-imagen', {method:'POST', body:fd, credentials:'include'});
    const data = await r.json();
    if (data.url) {
      document.getElementById('pf-img').value = data.url;
      document.getElementById('pf-img-preview').innerHTML = '<img src="'+data.url+'" style="width:100%;height:100%;object-fit:cover">';
      document.getElementById('pf-img-status').textContent = 'Imagen subida ✓';
    }
  } catch(e) { document.getElementById('pf-img-status').textContent = 'Error al subir'; }
}

async function generarDescIA(mejorar) {
  const nombre = document.getElementById('pf-nombre').value.trim();
  const cat = document.getElementById('pf-cat').value;
  const descBase = document.getElementById('pf-desc').value.trim();
  if (!nombre) return alert('Escribe el nombre del producto primero');
  document.getElementById('pf-ia-spinner').style.display = '';
  document.getElementById('pf-ia-gen').disabled = true;
  document.getElementById('pf-ia-mej').disabled = true;
  try {
    const r = await fetch(API + '/api/admin/productos/generar-descripcion', {
      method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
      body: JSON.stringify({nombre, categoria: cat, descripcion_base: mejorar ? descBase : ''})
    });
    const data = await r.json();
    if (data.descripcion) document.getElementById('pf-desc').value = data.descripcion;
  } catch(e) { alert('Error al generar descripción'); }
  document.getElementById('pf-ia-spinner').style.display = 'none';
  document.getElementById('pf-ia-gen').disabled = false;
  document.getElementById('pf-ia-mej').disabled = false;
}

async function guardarProducto(id) {
  const body = {
    nombre: document.getElementById('pf-nombre').value.trim(),
    descripcion: document.getElementById('pf-desc').value.trim() || null,
    codigo: document.getElementById('pf-sku').value.trim() || null,
    categoria: document.getElementById('pf-cat').value.trim(),
    precio: Math.round(parseFloat(document.getElementById('pf-precio').value || 0) * 100),
    precio_descuento: document.getElementById('pf-precio-desc').value ? Math.round(parseFloat(document.getElementById('pf-precio-desc').value) * 100) : null,
    imagen_url: document.getElementById('pf-img').value.trim() || null,
    activo: document.getElementById('pf-activo').checked,
    visible_catalogo: document.getElementById('pf-web').checked,
    stock_activo: document.getElementById('pf-stock-activo').checked,
    stock: parseInt(document.getElementById('pf-stock')?.value || 0),
  };
  if (!body.nombre || !body.categoria || !body.precio) return alert('Nombre, categoría y precio son obligatorios');
  const url = id ? API + '/productos/' + id : API + '/productos/';
  const method = id ? 'PUT' : 'POST';
  const r = await fetch(url, {method, headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(body)});
  const result = await r.json();
  const prodId = id || result.id;
  // Save variantes
  await saveAllVariantes(prodId);
  cerrarModal('modal-producto');
  showToast('Producto guardado ✓');
  loadProductos();
}

async function saveAllVariantes(prodId) {
  // Collect all variante rows from DOM
  const rows = document.querySelectorAll('.var-row');
  const existingIds = new Set();
  for (const row of rows) {
    const varId = row.dataset.varId;
    const tipo = row.dataset.tipo;
    const nombre = row.querySelector('.vr-nombre')?.value?.trim();
    if (!nombre) continue;
    const data = {
      tipo,
      nombre,
      codigo: row.querySelector('.vr-codigo')?.value?.trim() || null,
      precio: Math.round(parseFloat(row.querySelector('.vr-precio')?.value || 0) * 100),
      precio_descuento: row.querySelector('.vr-precio-desc')?.value ? Math.round(parseFloat(row.querySelector('.vr-precio-desc').value) * 100) : null,
      stock_activo: row.querySelector('.vr-stock-activo')?.checked || false,
      stock: parseInt(row.querySelector('.vr-stock')?.value || 0),
      imagen_url: row.querySelector('.vr-img')?.value || null,
      activo: true,
    };
    // Upload image if file selected
    const fileInput = row.querySelector('.vr-img-file');
    if (fileInput?.files?.length) {
      const fd = new FormData(); fd.append('imagen', fileInput.files[0]);
      try {
        const ur = await fetch(API + '/productos/subir-imagen', {method:'POST', body:fd, credentials:'include'});
        const ud = await ur.json();
        if (ud.url) data.imagen_url = ud.url;
      } catch(e) {}
    }
    if (varId && varId !== '') {
      await fetch(API + '/api/admin/variantes/' + varId, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(data)});
      existingIds.add(parseInt(varId));
    } else {
      await fetch(API + '/api/admin/variantes/' + prodId, {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(data)});
    }
  }
  // Delete removed variantes
  for (const v of editingVariantes) {
    if (!existingIds.has(v.id) && !document.querySelector(`.var-row[data-var-id="${v.id}"]`)) {
      await fetch(API + '/api/admin/variantes/' + v.id, {method:'DELETE', credentials:'include'});
    }
  }
}

// --- CATEGORÍAS ---
async function abrirModalCategorias() {
  document.getElementById('modal-cat-body').innerHTML = '<div style="text-align:center;color:var(--texto2)">Cargando...</div>';
  document.getElementById('modal-categorias').classList.add('active');
  try {
    const r = await fetch(API + '/api/admin/categorias', {credentials:'include'});
    const cats = await r.json();
    let html = '<table class="data-table" style="margin-bottom:16px"><thead><tr><th>Nombre</th><th>Tipo</th><th>Orden</th><th>Productos</th><th></th></tr></thead><tbody>';
    cats.forEach(c => {
      html += `<tr id="cat-row-${c.id}">
        <td><input value="${esc(c.nombre)}" id="cat-nombre-${c.id}" style="width:100%;padding:4px 8px;border:1px solid var(--borde);border-radius:4px;font-size:12px"></td>
        <td><select id="cat-tipo-${c.id}" style="padding:4px;font-size:12px"><option value="normal" ${c.tipo==='normal'?'selected':''}>Normal</option><option value="funeral" ${c.tipo==='funeral'?'selected':''}>Funeral</option></select></td>
        <td><input type="number" value="${c.orden}" id="cat-orden-${c.id}" style="width:50px;padding:4px;font-size:12px;border:1px solid var(--borde);border-radius:4px"></td>
        <td style="color:var(--texto2)">${c.productos_activos}</td>
        <td>
          <button class="btn-sm" onclick="guardarCat(${c.id})">Guardar</button>
          ${c.productos_activos === 0 ? `<button class="btn-danger" style="font-size:11px;padding:4px 8px" onclick="eliminarCat(${c.id})">Eliminar</button>` : `<span style="font-size:10px;color:var(--texto2)" title="Tiene ${c.productos_activos} productos activos">No eliminable</span>`}
        </td>
      </tr>`;
    });
    html += '</tbody></table>';
    html += `<div style="border-top:1px solid var(--borde);padding-top:12px"><strong style="font-size:13px">Nueva categoría</strong>
      <div style="display:flex;gap:6px;margin-top:8px">
        <input id="cat-new-nombre" placeholder="Nombre" style="flex:1;padding:6px 10px;border:1px solid var(--borde);border-radius:6px;font-size:13px">
        <select id="cat-new-tipo" style="padding:6px;font-size:12px"><option value="normal">Normal</option><option value="funeral">Funeral</option></select>
        <input type="number" id="cat-new-orden" placeholder="Orden" value="0" style="width:60px;padding:6px;border:1px solid var(--borde);border-radius:6px;font-size:12px">
        <button class="btn-primary" onclick="crearCat()">Agregar</button>
      </div>
    </div>`;
    document.getElementById('modal-cat-body').innerHTML = html;
  } catch(e) { document.getElementById('modal-cat-body').innerHTML = '<div style="color:var(--rojo)">Error al cargar categorías</div>'; }
}

async function guardarCat(id) {
  await fetch(API + '/api/admin/categorias/' + id, {
    method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({
      nombre: document.getElementById('cat-nombre-' + id).value.trim(),
      tipo: document.getElementById('cat-tipo-' + id).value,
      orden: parseInt(document.getElementById('cat-orden-' + id).value || 0),
    })
  });
  showToast('Categoría actualizada ✓');
}

async function eliminarCat(id) {
  if (!confirm('¿Eliminar esta categoría?')) return;
  const r = await fetch(API + '/api/admin/categorias/' + id, {method:'DELETE', credentials:'include'});
  if (!r.ok) { const e = await r.json(); return alert(e.detail || 'Error'); }
  abrirModalCategorias();
}

async function crearCat() {
  const nombre = document.getElementById('cat-new-nombre').value.trim();
  if (!nombre) return alert('Nombre requerido');
  await fetch(API + '/api/admin/categorias', {
    method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({nombre, tipo: document.getElementById('cat-new-tipo').value, orden: parseInt(document.getElementById('cat-new-orden').value || 0)})
  });
  showToast('Categoría creada ✓');
  abrirModalCategorias();
}

// --- EXPORTAR / IMPORTAR ---
async function exportarProductos() {
  try {
    const r = await fetch(API + '/api/admin/productos/exportar', {credentials:'include'});
    if (!r.ok) { alert('Error al exportar'); return; }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const hoy = new Date().toISOString().split('T')[0];
    a.download = 'productos_floreria_lucy_' + hoy + '.xlsx';
    a.click();
    URL.revokeObjectURL(url);
  } catch(e) { alert('Error al exportar'); }
}

async function importarProductos(input) {
  const file = input.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('archivo', file);
  showToast('Importando...');
  try {
    const r = await fetch(API + '/api/admin/productos/importar', {method:'POST', body:fd, credentials:'include'});
    const data = await r.json();
    if (data.ok) {
      alert(`Importación completada:\n${data.actualizados} productos actualizados\n${data.creados} productos creados\n${data.errores} errores`);
      loadProductos();
    } else {
      alert('Error en la importación');
    }
  } catch(e) { alert('Error al importar'); }
  input.value = '';
}

// ══════ CLAUDIA ══════
async function loadClaudia() {
  try {
    const r = await fetch(API + '/configuracion/', {credentials:'include'});
    const data = await r.json();
    const cfg = {};
    data.forEach(c => cfg[c.clave] = c.valor);
    document.getElementById('claudia-toggle').checked = cfg.claudia_activa === 'true';
    document.getElementById('claudia-temp').checked = cfg.claudia_temporada_alta === 'true';
    document.getElementById('claudia-msg').value = cfg.claudia_mensaje_bienvenida || '';
  } catch(e) {}
}

async function toggleConfig(clave, valor) {
  await fetch(API + '/configuracion/' + clave, {
    method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({valor: String(valor)})
  });
  showToast('Guardado ✓');
}

async function saveConfigField(clave, valor) {
  await toggleConfig(clave, valor);
}

// ══════ PÁGINA WEB ══════
async function loadWeb() {
  loadWebProductos();
}

async function loadWebProductos() {
  try {
    const r = await fetch(API + '/productos/', {credentials:'include'});
    const data = await r.json();
    const el = document.getElementById('web-productos-content');
    el.innerHTML = `<div class="table-wrap"><table class="data-table">
      <thead><tr><th><input type="checkbox" onchange="toggleAllWebProds(this.checked)"></th><th>Imagen</th><th>Nombre</th><th>Categoría</th><th>Visible en web</th></tr></thead>
      <tbody>${data.map(p => `<tr>
        <td><input type="checkbox" class="web-prod-check" data-id="${p.id}"></td>
        <td>${p.imagen_url ? '<img src="'+esc(p.imagen_url)+'" class="thumb">' : '—'}</td>
        <td>${esc(p.nombre)}</td>
        <td>${esc(p.categoria)}</td>
        <td><input type="checkbox" ${p.visible_catalogo !== false ? 'checked' : ''} onchange="toggleWebProd(${p.id}, this.checked)"></td>
      </tr>`).join('')}</tbody>
    </table></div>`;
  } catch(e) {}
}

function toggleAllWebProds(checked) {
  document.querySelectorAll('.web-prod-check').forEach(c => c.checked = checked);
}

async function toggleWebProd(id, visible) {
  await fetch(API + '/productos/' + id, {
    method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({visible_catalogo: visible})
  });
}

// ══════ FINANZAS ══════
let finChart = null;
async function loadFinanzas() {
  try {
    const periodo = document.getElementById('fin-periodo').value;
    const r = await fetch(API + '/pos/pedidos-hoy?periodo=' + periodo, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    const resumen = data.resumen || {};
    document.getElementById('fin-kpis').innerHTML = `
      <div class="kpi-card"><div class="kpi-label">Ingresos</div><div class="kpi-value">${fmt$(resumen.total_vendido)}</div></div>
      <div class="kpi-card"><div class="kpi-label">Transacciones</div><div class="kpi-value">${resumen.num_finalizados||0}</div></div>
    `;
    loadEgresos();
  } catch(e) {}
}

async function loadEgresos() {
  try {
    const r = await fetch(API + '/api/admin/egresos', {credentials:'include'});
    if (!r.ok) { document.getElementById('egresos-tbody').innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--texto2)">Sin egresos registrados</td></tr>'; return; }
    const data = await r.json();
    document.getElementById('egresos-tbody').innerHTML = data.map(e => `<tr>
      <td>${fmtDate(e.fecha)}</td>
      <td>${esc(e.concepto)}</td>
      <td>${esc(e.categoria)}</td>
      <td style="font-weight:600">${fmt$(e.monto)}</td>
      <td><button class="btn-sm" onclick="eliminarEgreso(${e.id})">🗑</button></td>
    </tr>`).join('') || '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--texto2)">Sin egresos</td></tr>';
  } catch(e) {}
}

function abrirModalEgreso() {
  const hoy = new Date().toISOString().split('T')[0];
  document.getElementById('modal-egreso-body').innerHTML = `
    <div class="field"><label>Fecha *</label><input type="date" id="eg-fecha" value="${hoy}"></div>
    <div class="field"><label>Concepto *</label><input id="eg-concepto"></div>
    <div class="field"><label>Categoría</label><select id="eg-cat"><option value="insumos">Insumos</option><option value="nomina">Nómina</option><option value="servicios">Servicios</option><option value="mantenimiento">Mantenimiento</option><option value="otro">Otro</option></select></div>
    <div class="field"><label>Monto * (pesos)</label><input type="number" id="eg-monto" step="0.01"></div>
    <div class="field"><label>Notas</label><textarea id="eg-notas"></textarea></div>
    <button class="btn-primary" onclick="guardarEgreso()" style="width:100%;margin-top:8px">Guardar</button>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function guardarEgreso() {
  const body = {
    fecha: document.getElementById('eg-fecha').value,
    concepto: document.getElementById('eg-concepto').value.trim(),
    categoria: document.getElementById('eg-cat').value,
    monto: Math.round(parseFloat(document.getElementById('eg-monto').value || 0) * 100),
    notas: document.getElementById('eg-notas').value.trim() || null,
  };
  if (!body.fecha || !body.concepto || !body.monto) return alert('Fecha, concepto y monto son obligatorios');
  await fetch(API + '/api/admin/egresos', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(body)});
  cerrarModal('modal-egreso');
  showToast('Gasto registrado ✓');
  loadEgresos();
}

async function eliminarEgreso(id) {
  if (!confirm('¿Eliminar este gasto?')) return;
  await fetch(API + '/api/admin/egresos/' + id, {method:'DELETE', credentials:'include'});
  loadEgresos();
}

async function exportarFinanzas(tipo) {
  showToast('Exportando ' + tipo + '...');
  // Simple CSV export from current data
  if (tipo === 'ingresos') {
    const periodo = document.getElementById('fin-periodo').value;
    const r = await fetch(API + '/pos/pedidos-hoy?periodo=' + periodo, {credentials:'include'});
    const data = await r.json();
    let csv = 'Folio,Cliente,Canal,Total,Pago,Estado,Fecha\n';
    (data.finalizados||[]).forEach(p => { csv += `"${p.folio}","${p.cliente_nombre||''}","${p.canal}",${(p.total||0)/100},"${p.forma_pago||''}","${p.estado}","${p.fecha_entrega||''}"\n`; });
    downloadCSV(csv, 'ingresos.csv');
  }
}

function downloadCSV(csv, filename) {
  const blob = new Blob([csv], {type:'text/csv'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
}

// ══════ ESTADÍSTICAS ══════
let charts = {};
async function loadEstadisticas() {
  const periodo = document.getElementById('est-periodo').value;
  const {desde, hasta} = getPeriodoDates(periodo);
  // KPIs
  try {
    const r = await fetch(API + '/pos/pedidos-hoy?periodo=' + (periodo === 'anio' ? 'mes' : periodo), {credentials:'include'});
    const data = await r.json();
    const resumen = data.resumen || {};
    document.getElementById('est-kpis').innerHTML = `
      <div class="kpi-card"><div class="kpi-label">Ventas totales</div><div class="kpi-value">${fmt$(resumen.total_vendido)}</div></div>
      <div class="kpi-card"><div class="kpi-label">Pedidos</div><div class="kpi-value">${resumen.num_finalizados||0}</div></div>
      <div class="kpi-card"><div class="kpi-label">Ticket promedio</div><div class="kpi-value">${resumen.num_finalizados ? fmt$(Math.round(resumen.total_vendido / resumen.num_finalizados)) : '$0'}</div></div>
    `;
  } catch(e) {}
  // Charts
  loadChartVentasDia(desde, hasta);
  loadChartProductosTop(desde, hasta);
  loadChartCanales(desde, hasta);
  loadChartZonas(desde, hasta);
}

function getPeriodoDates(periodo) {
  const now = new Date();
  const hoy = now.toISOString().split('T')[0];
  let desde = hoy, hasta = hoy;
  if (periodo === 'semana') {
    const d = new Date(now); d.setDate(d.getDate() - d.getDay());
    desde = d.toISOString().split('T')[0];
  } else if (periodo === 'mes') {
    desde = hoy.substring(0, 8) + '01';
  } else if (periodo === 'anio') {
    desde = hoy.substring(0, 5) + '01-01';
  }
  return {desde, hasta};
}

async function loadChartVentasDia(desde, hasta) {
  try {
    const r = await fetch(API + `/api/admin/estadisticas/ventas-por-dia?desde=${desde}&hasta=${hasta}`, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    if (charts.ventasDia) charts.ventasDia.destroy();
    charts.ventasDia = new Chart(document.getElementById('chart-ventas-dia'), {
      type: 'bar', data: { labels: data.map(d => d.fecha), datasets: [{label:'Ventas', data: data.map(d => d.total/100), backgroundColor:'#193a2c'}] },
      options: {responsive:true, plugins:{legend:{display:false}}}
    });
  } catch(e) {}
}

async function loadChartProductosTop(desde, hasta) {
  try {
    const r = await fetch(API + `/api/admin/estadisticas/productos-top?desde=${desde}&hasta=${hasta}&limit=10`, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    if (charts.prodTop) charts.prodTop.destroy();
    charts.prodTop = new Chart(document.getElementById('chart-productos-top'), {
      type: 'bar', data: { labels: data.map(d => d.nombre), datasets: [{label:'Unidades', data: data.map(d => d.cantidad), backgroundColor:'#d4a843'}] },
      options: {responsive:true, indexAxis:'y', plugins:{legend:{display:false}}}
    });
  } catch(e) {}
}

async function loadChartCanales(desde, hasta) {
  try {
    const r = await fetch(API + `/api/admin/estadisticas/canales?desde=${desde}&hasta=${hasta}`, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    if (charts.canales) charts.canales.destroy();
    charts.canales = new Chart(document.getElementById('chart-canales'), {
      type: 'doughnut', data: { labels: data.map(d => d.canal), datasets: [{data: data.map(d => d.total), backgroundColor:['#193a2c','#d4a843','#6b9e78','#ef4444']}] },
      options: {responsive:true}
    });
  } catch(e) {}
}

async function loadChartZonas(desde, hasta) {
  try {
    const r = await fetch(API + `/api/admin/estadisticas/zonas?desde=${desde}&hasta=${hasta}`, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    if (charts.zonas) charts.zonas.destroy();
    charts.zonas = new Chart(document.getElementById('chart-zonas'), {
      type: 'bar', data: { labels: data.map(d => d.zona||'Sin zona'), datasets: [{label:'Pedidos', data: data.map(d => d.cantidad), backgroundColor:['#7c3aed','#3b82f6','#22c55e','#9ca3af']}] },
      options: {responsive:true, plugins:{legend:{display:false}}}
    });
  } catch(e) {}
}

// ══════ USUARIOS ══════
async function loadUsuarios() {
  try {
    const r = await fetch(API + '/api/admin/usuarios', {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    const rolColors = {admin:'#193a2c', operador:'#2d5a3d', florista:'#d4a843', repartidor:'#6b9e78'};
    document.getElementById('usuarios-tbody').innerHTML = data.map(u => `<tr>
      <td style="font-weight:500">${esc(u.nombre)}</td>
      <td>${esc(u.username)}</td>
      <td><span class="badge-rol" style="background:${rolColors[u.rol]||'#666'}">${u.rol}</span></td>
      <td>${u.activo ? '<span style="color:var(--verde)">Si</span>' : '<span style="color:var(--rojo)">No</span>'}</td>
      <td>${fmtDate(u.created_at)}</td>
      <td>
        <button class="btn-sm" onclick="editarUsuario(${u.id})">Editar</button>
        ${u.rol !== 'admin' ? `<button class="btn-sm" onclick="toggleUsuario(${u.id}, ${!u.activo})">${u.activo ? 'Desactivar' : 'Activar'}</button>` : ''}
      </td>
    </tr>`).join('');
  } catch(e) {}
}

function abrirModalUsuario(user) {
  document.getElementById('modal-user-title').textContent = user ? 'Editar usuario' : 'Nuevo usuario';
  document.getElementById('modal-user-body').innerHTML = `
    <div class="field"><label>Nombre *</label><input id="uf-nombre" value="${esc(user?.nombre||'')}"></div>
    <div class="field"><label>Usuario *</label><input id="uf-username" value="${esc(user?.username||'')}" ${user ? 'disabled' : ''}></div>
    ${!user ? '<div class="field"><label>Contraseña *</label><input type="password" id="uf-pass"></div>' : ''}
    <div class="field"><label>Rol *</label><select id="uf-rol">
      <option value="admin" ${user?.rol==='admin'?'selected':''}>Admin</option>
      <option value="operador" ${user?.rol==='operador'?'selected':''}>Operador</option>
      <option value="florista" ${user?.rol==='florista'?'selected':''}>Florista</option>
      <option value="repartidor" ${user?.rol==='repartidor'?'selected':''}>Repartidor</option>
    </select></div>
    <button class="btn-primary" onclick="guardarUsuario(${user?.id||'null'})" style="width:100%;margin-top:8px">Guardar</button>
    ${user ? '<button class="btn-sm" onclick="cambiarPassUsuario('+user.id+')" style="width:100%;margin-top:8px">Cambiar contraseña</button>' : ''}
  `;
  document.getElementById('modal-usuario').classList.add('active');
}

async function editarUsuario(id) {
  const r = await fetch(API + '/api/admin/usuarios', {credentials:'include'});
  const data = await r.json();
  const u = data.find(u => u.id === id);
  if (u) abrirModalUsuario(u);
}

async function guardarUsuario(id) {
  const body = {
    nombre: document.getElementById('uf-nombre').value.trim(),
    username: document.getElementById('uf-username').value.trim(),
    rol: document.getElementById('uf-rol').value,
  };
  if (!id) body.password = document.getElementById('uf-pass')?.value || '';
  if (!body.nombre || !body.username) return alert('Nombre y usuario son obligatorios');
  if (!id && !body.password) return alert('Contraseña es obligatoria');
  const url = id ? API + '/api/admin/usuarios/' + id : API + '/api/admin/usuarios';
  const method = id ? 'PUT' : 'POST';
  const r = await fetch(url, {method, headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(body)});
  if (!r.ok) { const e = await r.json(); return alert(e.detail || 'Error'); }
  cerrarModal('modal-usuario');
  showToast('Usuario guardado ✓');
  loadUsuarios();
}

async function toggleUsuario(id, activo) {
  await fetch(API + '/api/admin/usuarios/' + id, {
    method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({activo})
  });
  loadUsuarios();
}

async function cambiarPassUsuario(id) {
  const pass = prompt('Nueva contraseña:');
  if (!pass || pass.length < 4) return;
  await fetch(API + '/api/admin/usuarios/' + id + '/cambiar-password', {
    method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({password: pass})
  });
  showToast('Contraseña actualizada ✓');
}

// ══════ CONFIGURACIONES ══════
async function loadConfig() {
  try {
    const r = await fetch(API + '/configuracion/', {credentials:'include'});
    const data = await r.json();
    const cfg = {};
    data.forEach(c => cfg[c.clave] = c.valor);
    renderCfgSection('cfg-negocio', [
      {k:'negocio_nombre',l:'Nombre del negocio'},
      {k:'negocio_direccion',l:'Dirección'},
      {k:'negocio_telefono',l:'Teléfono'},
      {k:'negocio_email',l:'Email'},
      {k:'negocio_rfc',l:'RFC'},
    ], cfg);
    renderCfgSection('cfg-banco', [
      {k:'banco_nombre',l:'Banco'},
      {k:'banco_titular',l:'Titular'},
      {k:'banco_cuenta',l:'Número de cuenta',secret:true},
      {k:'banco_clabe',l:'CLABE',secret:true},
      {k:'banco_concepto',l:'Concepto sugerido'},
    ], cfg);
    renderCfgSection('cfg-ticket', [
      {k:'ticket_mostrar_rfc',l:'Mostrar RFC en tickets',type:'toggle'},
      {k:'ticket_mensaje_footer',l:'Footer ticket digital'},
      {k:'ticket_termico_mensaje',l:'Footer ticket térmico'},
      {k:'pos_iva_default',l:'IVA por default en POS',type:'toggle'},
      {k:'pos_ieps_default',l:'IEPS por default en POS',type:'toggle'},
    ], cfg);
    renderCfgSection('cfg-whatsapp', [
      {k:'whatsapp_numero',l:'Número WhatsApp'},
      {k:'claudia_activa',l:'Claudia activa',type:'toggle'},
      {k:'claudia_temporada_alta',l:'Temporada alta',type:'toggle'},
      {k:'claudia_mensaje_bienvenida',l:'Mensaje bienvenida',type:'textarea'},
    ], cfg);
    renderCfgSection('cfg-catalogo', [
      {k:'catalogo_activo',l:'Catálogo web activo',type:'toggle'},
      {k:'catalogo_titulo',l:'Título'},
      {k:'catalogo_subtitulo',l:'Subtítulo'},
      {k:'catalogo_whatsapp_msg',l:'Mensaje WhatsApp'},
      {k:'catalogo_footer',l:'Footer'},
      {k:'catalogo_fecha_minima_dias',l:'Días mínimos anticipación',type:'number'},
    ], cfg);
  } catch(e) {}
}

function renderCfgSection(id, fields, cfg) {
  const el = document.getElementById(id + '-content');
  let html = '<div style="max-width:600px">';
  fields.forEach(f => {
    const val = cfg[f.k] || '';
    if (f.type === 'toggle') {
      html += `<div class="toggle-row"><label>${f.l}</label><input type="checkbox" ${val === 'true' ? 'checked' : ''} onchange="saveConfigField('${f.k}', String(this.checked))"></div>`;
    } else if (f.type === 'textarea') {
      html += `<div class="config-field"><label>${f.l}</label><textarea onchange="saveConfigField('${f.k}', this.value)">${esc(val)}</textarea></div>`;
    } else if (f.type === 'number') {
      html += `<div class="config-field"><label>${f.l}</label><input type="number" value="${esc(val)}" onchange="saveConfigField('${f.k}', this.value)"></div>`;
    } else if (f.secret) {
      html += `<div class="config-field"><label>${f.l}</label><div style="display:flex;gap:6px"><input type="password" value="${esc(val)}" id="cfg-${f.k}" onchange="saveConfigField('${f.k}', this.value)"><button class="btn-sm" onclick="const i=document.getElementById('cfg-${f.k}');i.type=i.type==='password'?'text':'password'">👁</button></div></div>`;
    } else {
      html += `<div class="config-field"><label>${f.l}</label><input value="${esc(val)}" onchange="saveConfigField('${f.k}', this.value)"></div>`;
    }
  });
  html += '<div style="margin-top:16px;font-size:12px;color:var(--verde)" id="cfg-saved-' + id + '"></div></div>';
  el.innerHTML = html;
}

// Override saveConfigField to show toast
const _origSaveCfg = saveConfigField;
saveConfigField = async function(clave, valor) {
  await fetch(API + '/configuracion/' + clave, {
    method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({valor})
  });
  showToast('Guardado ✓');
};

// ══════ BADGE POLLING ══════
async function updateBadge() {
  try {
    const r = await fetch(API + '/pos/pedidos-hoy?estado=pendiente_pago', {credentials:'include'});
    const data = await r.json();
    const count = (data.pendientes || []).length;
    const badge = document.getElementById('badge-pend');
    if (count > 0) { badge.style.display = 'flex'; badge.textContent = count > 9 ? '9+' : count; }
    else badge.style.display = 'none';
  } catch(e) {}
}
updateBadge();
setInterval(updateBadge, 30000);
