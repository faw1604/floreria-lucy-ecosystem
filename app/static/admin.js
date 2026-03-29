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
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
      <div class="field"><label>Precio *</label><input type="number" id="pf-precio" value="${prod ? (prod.precio/100).toFixed(2) : ''}" step="0.01"></div>
      <div class="field"><label>Precio de oferta</label><input type="number" id="pf-precio-desc" value="${prod?.precio_descuento ? (prod.precio_descuento/100).toFixed(2) : ''}" step="0.01">
        <div style="font-size:10px;color:var(--texto2)">Precio normal aparece tachado</div>
      </div>
      <div class="field"><label>Costo unitario</label><input type="number" id="pf-costo" value="${prod?.costo_unitario || ''}" step="0.01">
        <div style="font-size:10px;color:var(--texto2)">Solo visible en admin</div>
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
    <!-- MEDIDAS -->
    <div style="margin:14px 0">
      <label style="font-size:12px;font-weight:500;color:var(--texto2);display:block;margin-bottom:6px">Medidas aproximadas</label>
      <div style="display:flex;gap:10px">
        <div class="field" style="flex:1;margin-bottom:0"><label style="font-size:11px">Alto (cm)</label><input type="number" id="pf-alto" value="${prod?.medida_alto||''}" step="0.1" min="0" placeholder="Ej: 45"></div>
        <div class="field" style="flex:1;margin-bottom:0"><label style="font-size:11px">Ancho (cm)</label><input type="number" id="pf-ancho" value="${prod?.medida_ancho||''}" step="0.1" min="0" placeholder="Ej: 30"></div>
      </div>
      <div style="font-size:10px;color:var(--texto2);margin-top:4px">Medidas aproximadas — se muestran al cliente en el catálogo web.</div>
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
    costo_unitario: document.getElementById('pf-costo')?.value ? parseFloat(document.getElementById('pf-costo').value) : null,
    medida_alto: document.getElementById('pf-alto')?.value ? parseFloat(document.getElementById('pf-alto').value) : null,
    medida_ancho: document.getElementById('pf-ancho')?.value ? parseFloat(document.getElementById('pf-ancho').value) : null,
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
let webCfg = {};

async function loadWeb() {
  // Load all config
  try {
    const r = await fetch(API + '/configuracion/', {credentials:'include'});
    const data = await r.json();
    webCfg = {};
    data.forEach(c => webCfg[c.clave] = c.valor);
  } catch(e) {}
  loadWebBanners();
}

// --- BANNERS / HERO ---
function loadWebBanners() {
  const el = document.getElementById('web-banners-content');
  el.innerHTML = `<div style="max-width:600px">
    <div class="field"><label>Imagen de fondo del hero</label>
      <div style="display:flex;align-items:flex-start;gap:12px">
        <div id="web-hero-preview" style="width:200px;height:120px;border-radius:10px;background:var(--borde);overflow:hidden;flex-shrink:0">
          ${webCfg.catalogo_hero_imagen ? '<img src="'+esc(webCfg.catalogo_hero_imagen)+'" style="width:100%;height:100%;object-fit:cover">' : ''}
        </div>
        <div style="flex:1"><input type="file" id="web-hero-file" accept="image/*" onchange="subirHeroImg()"><input type="hidden" id="web-hero-img" value="${esc(webCfg.catalogo_hero_imagen||'')}"><div id="web-hero-status" style="font-size:11px;color:var(--texto2);margin-top:4px"></div></div>
      </div>
    </div>
    <div class="config-field"><label>Título del hero</label><input id="web-hero-titulo" value="${esc(webCfg.catalogo_hero_titulo||'')}"></div>
    <div class="config-field"><label>Subtítulo del hero</label><input id="web-hero-subtitulo" value="${esc(webCfg.catalogo_hero_subtitulo||'')}"></div>
    <button class="btn-primary" onclick="guardarHero()" style="margin-top:12px">Guardar cambios</button>
  </div>`;
}

async function subirHeroImg() {
  const file = document.getElementById('web-hero-file').files[0];
  if (!file) return;
  document.getElementById('web-hero-status').textContent = 'Subiendo...';
  const fd = new FormData(); fd.append('imagen', file);
  try {
    const r = await fetch(API + '/productos/subir-imagen', {method:'POST', body:fd, credentials:'include'});
    const d = await r.json();
    if (d.url) {
      document.getElementById('web-hero-img').value = d.url;
      document.getElementById('web-hero-preview').innerHTML = '<img src="'+d.url+'" style="width:100%;height:100%;object-fit:cover">';
      document.getElementById('web-hero-status').textContent = 'Subida ✓';
    }
  } catch(e) { document.getElementById('web-hero-status').textContent = 'Error'; }
}

async function guardarHero() {
  const keys = {
    catalogo_hero_imagen: document.getElementById('web-hero-img').value,
    catalogo_hero_titulo: document.getElementById('web-hero-titulo').value,
    catalogo_hero_subtitulo: document.getElementById('web-hero-subtitulo').value,
  };
  for (const [k,v] of Object.entries(keys)) {
    await fetch(API + '/configuracion/' + k, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({valor: v})});
  }
  showToast('Hero guardado ✓');
}

// --- TEXTOS ---
function webSubTab(id) {
  switchSubTab('web', id);
  if (id === 'web-textos') loadWebTextos();
  if (id === 'web-horarios') loadWebHorarios();
  if (id === 'web-descuentos') loadWebDescuentos();
}

function loadWebTextos() {
  const el = document.getElementById('web-textos-content');
  const fields = [
    {k:'catalogo_whatsapp_msg', l:'Mensaje WhatsApp (pre-llenado al contactar)', type:'textarea'},
    {k:'catalogo_footer', l:'Texto del footer'},
    {k:'catalogo_meta_titulo', l:'Título de la pestaña del navegador'},
    {k:'catalogo_meta_descripcion', l:'Descripción SEO', type:'textarea'},
  ];
  el.innerHTML = '<div style="max-width:600px">' + fields.map(f =>
    `<div class="config-field"><label>${f.l}</label>${f.type === 'textarea' ? `<textarea id="wt-${f.k}" rows="2">${esc(webCfg[f.k]||'')}</textarea>` : `<input id="wt-${f.k}" value="${esc(webCfg[f.k]||'')}">`}</div>`
  ).join('') + '<button class="btn-primary" onclick="guardarWebTextos()" style="margin-top:12px">Guardar textos</button></div>';
}

async function guardarWebTextos() {
  const keys = ['catalogo_whatsapp_msg','catalogo_footer','catalogo_meta_titulo','catalogo_meta_descripcion'];
  for (const k of keys) {
    const val = document.getElementById('wt-' + k)?.value || '';
    await fetch(API + '/configuracion/' + k, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({valor: val})});
  }
  showToast('Textos guardados ✓');
}

// --- HORARIOS ---
const DIAS_WEB = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'];

async function loadWebHorarios() {
  const el = document.getElementById('web-horarios-content');
  // Load horarios especificos
  let horariosHtml = '<div style="color:var(--texto2);font-size:13px">Cargando...</div>';
  try {
    const r = await fetch(API + '/panel/horarios-especificos', {credentials:'include'});
    const data = await r.json();
    horariosHtml = DIAS_WEB.map((dia, i) => {
      const horas = data.filter(h => h.dia_semana === i);
      const chips = horas.length ? horas.map(h => `<span style="display:inline-flex;align-items:center;gap:4px;background:#e8f5ec;color:var(--verde);font-size:12px;padding:4px 8px;border-radius:6px">${h.hora} <button onclick="eliminarHorarioWeb(${h.id})" style="background:none;border:none;color:var(--rojo);cursor:pointer;font-size:14px">&times;</button></span>`).join(' ') : '<span style="font-size:12px;color:var(--texto2);font-style:italic">Sin horas</span>';
      return `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--borde)"><span style="width:90px;font-size:13px;font-weight:500">${dia}</span><div style="flex:1;display:flex;flex-wrap:wrap;gap:4px">${chips}</div><button class="btn-sm" onclick="agregarHorarioWeb(${i})" style="font-size:11px">+</button></div>`;
    }).join('');
  } catch(e) {}

  // Load categories for fecha especial
  let catOpts = '';
  try {
    const r = await fetch(API + '/api/admin/categorias', {credentials:'include'});
    const cats = await r.json();
    const selCats = JSON.parse(webCfg.catalogo_fecha_especial_categorias || '[]');
    catOpts = cats.map(c => `<label style="display:flex;align-items:center;gap:6px;font-size:13px;padding:4px 0"><input type="checkbox" class="fe-cat" value="${c.id}" ${selCats.includes(c.id) ? 'checked' : ''}> ${esc(c.nombre)}</label>`).join('');
  } catch(e) {}

  el.innerHTML = `<div style="max-width:700px">
    <div class="toggle-row"><label>Catálogo web activo</label><input type="checkbox" ${webCfg.catalogo_activo==='true'?'checked':''} onchange="saveConfigField('catalogo_activo',String(this.checked))"></div>
    <div class="config-field" style="margin:12px 0"><label>Días mínimos de anticipación</label><input type="number" value="${esc(webCfg.catalogo_fecha_minima_dias||'1')}" min="0" style="width:80px" onchange="saveConfigField('catalogo_fecha_minima_dias',this.value)"></div>
    <h4 style="font-size:14px;color:var(--verde);margin:20px 0 12px;padding-top:16px;border-top:2px solid var(--borde)">Horarios de hora específica</h4>
    ${horariosHtml}

    <div style="margin-top:24px;padding-top:16px;border-top:2px solid var(--borde)">
      <div class="toggle-row"><label>Temporada alta (envíos $99)</label><input type="checkbox" id="wh-temporada" ${webCfg.claudia_temporada_alta==='true'?'checked':''} onchange="saveConfigField('claudia_temporada_alta', String(this.checked))"></div>
      <div class="toggle-row"><label>Cerrar catálogo temporalmente</label><input type="checkbox" id="wh-cerrado" ${webCfg.catalogo_cerrado==='true'?'checked':''} onchange="saveConfigField('catalogo_cerrado', String(this.checked))"></div>
    </div>

    <div style="margin-top:24px;padding-top:16px;border-top:2px solid var(--borde)">
      <h4 style="font-size:14px;color:var(--verde);margin-bottom:12px">Modo fecha especial</h4>
      <div class="toggle-row"><label>Activar modo fecha especial</label><input type="checkbox" id="wh-fe-activa" ${webCfg.catalogo_fecha_especial_activa==='true'?'checked':''} onchange="toggleFechaEspecial(this.checked)"></div>
      <div id="wh-fe-fields" style="${webCfg.catalogo_fecha_especial_activa==='true'?'':'display:none'};margin-top:12px">
        <div class="config-field"><label>Nombre del evento</label><input id="wh-fe-nombre" value="${esc(webCfg.catalogo_fecha_especial_nombre||'')}" placeholder="Ej: Día de las Madres"></div>
        <div class="config-field"><label>Texto del botón en hero</label><input id="wh-fe-boton" value="${esc(webCfg.catalogo_fecha_especial_boton_texto||'')}" placeholder="Ej: Ver arreglos para mamá"></div>
        <div class="config-field"><label>Categorías a mostrar</label><div style="max-height:150px;overflow-y:auto;border:1px solid var(--borde);border-radius:8px;padding:8px">${catOpts || '<span style="color:var(--texto2);font-size:12px">Sin categorías</span>'}</div></div>
        <button class="btn-primary" onclick="guardarFechaEspecial()" style="margin-top:12px">Guardar fecha especial</button>
      </div>
    </div>
  </div>`;
}

function toggleFechaEspecial(checked) {
  document.getElementById('wh-fe-fields').style.display = checked ? '' : 'none';
  saveConfigField('catalogo_fecha_especial_activa', String(checked));
}

async function guardarFechaEspecial() {
  const catIds = [...document.querySelectorAll('.fe-cat:checked')].map(c => parseInt(c.value));
  const keys = {
    catalogo_fecha_especial_nombre: document.getElementById('wh-fe-nombre').value,
    catalogo_fecha_especial_boton_texto: document.getElementById('wh-fe-boton').value,
    catalogo_fecha_especial_categorias: JSON.stringify(catIds),
  };
  for (const [k,v] of Object.entries(keys)) {
    await fetch(API + '/configuracion/' + k, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({valor: v})});
  }
  showToast('Fecha especial guardada ✓');
}

async function agregarHorarioWeb(dia) {
  const hora = prompt('Hora (HH:MM, ej: 13:00):');
  if (!hora || !/^\d{2}:\d{2}$/.test(hora)) return;
  await fetch(API + '/panel/horarios-especificos', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({dia_semana: dia, hora})});
  loadWebHorarios();
}

async function eliminarHorarioWeb(id) {
  await fetch(API + '/panel/horarios-especificos/' + id, {method:'DELETE', credentials:'include'});
  loadWebHorarios();
}

// --- DESCUENTOS ---
async function loadWebDescuentos() {
  const el = document.getElementById('web-descuentos-content');
  try {
    const r = await fetch(API + '/api/admin/descuentos', {credentials:'include'});
    const data = await r.json();
    el.innerHTML = `<button class="btn-primary" onclick="abrirModalDescuento()" style="margin-bottom:12px">+ Nuevo código</button>
    <div class="table-wrap"><table class="data-table">
      <thead><tr><th>Código</th><th>Tipo</th><th>Valor</th><th>Usos</th><th>Vigencia</th><th>Activo</th><th></th></tr></thead>
      <tbody>${data.map(d => `<tr>
        <td style="font-weight:600">${esc(d.codigo)}</td>
        <td>${d.tipo === 'porcentaje' ? '%' : '$'}</td>
        <td>${d.tipo === 'porcentaje' ? d.valor + '%' : fmt$(d.valor)}</td>
        <td>${d.usos_actuales}${d.usos_maximos ? '/' + d.usos_maximos : '/∞'}</td>
        <td style="font-size:11px">${d.fecha_inicio ? d.fecha_inicio + ' → ' : ''}${d.fecha_expiracion || 'Sin límite'}</td>
        <td>${d.activo ? '<span style="color:var(--verde)">Si</span>' : '<span style="color:var(--rojo)">No</span>'}</td>
        <td><button class="btn-sm" onclick="editarDescuento(${d.id})">Editar</button> <button class="btn-danger" style="font-size:11px;padding:4px 8px" onclick="eliminarDescuento(${d.id})">Eliminar</button></td>
      </tr>`).join('')}</tbody>
    </table></div>`;
  } catch(e) {}
}

let editDescId = null;
function abrirModalDescuento(d) {
  editDescId = d?.id || null;
  document.getElementById('modal-egreso-body').innerHTML = `
    <div class="field"><label>Código *</label><input id="dc-codigo" value="${esc(d?.codigo||'')}" style="text-transform:uppercase" ${d ? 'disabled' : ''}></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div class="field"><label>Tipo *</label><select id="dc-tipo"><option value="porcentaje" ${d?.tipo==='porcentaje'?'selected':''}>Porcentaje (%)</option><option value="monto" ${d?.tipo==='monto'?'selected':''}>Monto fijo ($)</option></select></div>
      <div class="field"><label>Valor *</label><input type="number" id="dc-valor" value="${d?.valor||''}" min="0"></div>
    </div>
    <div class="field"><label>Usos máximos (vacío = ilimitado)</label><input type="number" id="dc-usos" value="${d?.usos_maximos||''}" min="0"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div class="field"><label>Fecha inicio</label><input type="date" id="dc-inicio" value="${d?.fecha_inicio||''}"></div>
      <div class="field"><label>Fecha fin</label><input type="date" id="dc-fin" value="${d?.fecha_expiracion||''}"></div>
    </div>
    <div class="toggle-row" style="border:none"><label>Activo</label><input type="checkbox" id="dc-activo" ${d?.activo !== false ? 'checked' : ''}></div>
    <button class="btn-primary" onclick="guardarDescuento()" style="width:100%;margin-top:8px">Guardar</button>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function editarDescuento(id) {
  const r = await fetch(API + '/api/admin/descuentos', {credentials:'include'});
  const data = await r.json();
  const d = data.find(x => x.id === id);
  if (d) abrirModalDescuento(d);
}

async function guardarDescuento() {
  const body = {
    codigo: document.getElementById('dc-codigo').value.trim().toUpperCase(),
    tipo: document.getElementById('dc-tipo').value,
    valor: parseInt(document.getElementById('dc-valor').value || 0),
    usos_maximos: document.getElementById('dc-usos').value ? parseInt(document.getElementById('dc-usos').value) : null,
    fecha_inicio: document.getElementById('dc-inicio').value || null,
    fecha_expiracion: document.getElementById('dc-fin').value || null,
    activo: document.getElementById('dc-activo').checked,
  };
  if (!body.codigo || !body.valor) return alert('Código y valor son obligatorios');
  const url = editDescId ? API + '/api/admin/descuentos/' + editDescId : API + '/api/admin/descuentos';
  const method = editDescId ? 'PUT' : 'POST';
  await fetch(url, {method, headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(body)});
  cerrarModal('modal-egreso');
  showToast('Código guardado ✓');
  loadWebDescuentos();
}

async function eliminarDescuento(id) {
  if (!confirm('¿Eliminar este código?')) return;
  await fetch(API + '/api/admin/descuentos/' + id, {method:'DELETE', credentials:'include'});
  loadWebDescuentos();
}

// ══════ FINANZAS ══════
let finCharts = {};
let finData = {ingresos: null, egresos: null, flujo: null};

function chihuahuaHoy() {
  const now = new Date(new Date().toLocaleString('en-US',{timeZone:'America/Chihuahua'}));
  return {now, hoy: now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0')};
}

function getFinDates() {
  const p = document.getElementById('fin-periodo').value;
  const {now, hoy} = chihuahuaHoy();
  if (p === 'rango') return {desde: document.getElementById('fin-desde').value || hoy, hasta: document.getElementById('fin-hasta').value || hoy};
  if (p === 'hoy') return {desde: hoy, hasta: hoy};
  if (p === 'semana') { const d = new Date(now); d.setDate(d.getDate()-d.getDay()); const ds=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); return {desde:ds, hasta:hoy}; }
  if (p === 'mes') return {desde: hoy.substring(0,8)+'01', hasta: hoy};
  return {desde: hoy, hasta: hoy};
}

function onFinPeriodoChange() {
  const isRango = document.getElementById('fin-periodo').value === 'rango';
  document.getElementById('fin-desde').style.display = isRango ? '' : 'none';
  document.getElementById('fin-hasta').style.display = isRango ? '' : 'none';
  if (!isRango) reloadAllFinanzas();
}

function reloadAllFinanzas() {
  loadFinanzas();
  // Reload whichever sub-tab is visible
  const visible = document.querySelector('#sec-finanzas .sub-content:not([style*="display: none"]):not([style*="display:none"])');
  if (!visible) return;
  const id = visible.id.replace('-content', '');
  if (id === 'fin-egresos') loadEgresos();
  if (id === 'fin-utilidad') loadUtilidad();
  if (id === 'fin-flujo') loadFlujo();
  if (id === 'fin-cortes') loadCortes();
}

function finSubTab(id) {
  switchSubTab('fin', id);
  if (id === 'fin-egresos') loadEgresos();
  if (id === 'fin-utilidad') loadUtilidad();
  if (id === 'fin-flujo') loadFlujo();
  if (id === 'fin-cortes') loadCortes();
}

async function loadFinanzas() {
  const {desde, hasta} = getFinDates();
  try {
    const periodo = document.getElementById('fin-periodo').value;
    const r = await fetch(API + '/pos/pedidos-hoy?periodo=' + (periodo === 'rango' ? 'rango&fecha_inicio=' + desde + '&fecha_fin=' + hasta : periodo), {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    finData.ingresos = data;
    const res = data.resumen || {};
    const rows = data.finalizados || [];
    // Load otros ingresos
    let otrosRows = [];
    let otrosTotal = 0;
    try {
      const or2 = await fetch(API+'/api/admin/otros-ingresos?desde='+desde+'&hasta='+hasta, {credentials:'include'});
      if (or2.ok) { otrosRows = await or2.json(); otrosTotal = otrosRows.reduce((s,o) => s + (o.monto||0), 0); }
    } catch(e) {}
    const totalIngresos = (res.total_vendido||0) + otrosTotal;
    const totalTrans = (res.num_finalizados||0) + otrosRows.length;
    const ticket = totalTrans ? Math.round(totalIngresos / totalTrans) : 0;
    finData.otrosIngresos = otrosRows;
    finData.totalIngresos = totalIngresos;
    // KPIs
    let kpis = `<div class="kpi-card"><div class="kpi-label">Total ingresos</div><div class="kpi-value">${fmt$(totalIngresos)}</div>${otrosTotal ? '<div class="kpi-sub">Incluye '+fmt$(otrosTotal)+' de otros ingresos</div>' : ''}</div>
      <div class="kpi-card"><div class="kpi-label">Transacciones</div><div class="kpi-value">${totalTrans}</div></div>
      <div class="kpi-card"><div class="kpi-label">Ticket promedio</div><div class="kpi-value">${fmt$(ticket)}</div></div>`;
    for (const [m,v] of Object.entries(res.desglose_pago||{})) kpis += `<div class="kpi-card"><div class="kpi-label">${esc(m)}</div><div class="kpi-value">${fmt$(v)}</div></div>`;
    const canales = {};
    rows.forEach(p => { canales[p.canal] = (canales[p.canal]||0) + (p.total||0); });
    if (otrosTotal) canales['Otros'] = otrosTotal;
    for (const [c,v] of Object.entries(canales)) kpis += `<div class="kpi-card"><div class="kpi-label">${esc(c)}</div><div class="kpi-value">${fmt$(v)}</div></div>`;
    document.getElementById('fin-kpis').innerHTML = kpis;
    // Table — merge ventas + otros
    const tbody = document.getElementById('fin-ing-tbody');
    let allRows = rows.slice(0,200).map(p => `<tr><td>${fmtDate(p.fecha_entrega)}</td><td style="font-weight:600;color:var(--verde)">${esc(p.folio)}</td><td>${esc(p.cliente_nombre||'Mostrador')}</td><td>${esc(p.canal)}</td><td>${esc(p.forma_pago||'—')}</td><td style="font-weight:600">${fmt$(p.total)}</td></tr>`);
    otrosRows.forEach(o => {
      allRows.push(`<tr><td>${fmtDate(o.fecha)}</td><td><span style="background:var(--dorado);color:var(--verde);padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700">OTRO</span></td><td>${esc(o.concepto)}</td><td>—</td><td>${esc(o.metodo_pago||'—')}</td><td style="font-weight:600">${fmt$(o.monto)}</td></tr>`);
    });
    tbody.innerHTML = allRows.join('') || '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--texto2)">Sin ingresos</td></tr>';
  } catch(e) { console.error(e); }
}

async function abrirModalOtroIngreso() {
  await loadMetodosPago();
  const hoy = new Date().toISOString().split('T')[0];
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4 style="margin-bottom:12px">Registrar otro ingreso</h4>
    <div class="field"><label>Fecha *</label><input type="date" id="oi-fecha" value="${hoy}"></div>
    <div class="field"><label>Concepto *</label><input id="oi-concepto" placeholder="Ej: Clase de arreglos florales"></div>
    <div class="field"><label>Monto * (pesos)</label><input type="number" id="oi-monto" step="0.01"></div>
    <div class="field"><label>Método de pago</label><select id="oi-mp"><option value="">Selecciona...</option>${mpOptions()}</select></div>
    <div class="field"><label>Notas</label><textarea id="oi-notas"></textarea></div>
    <button class="btn-primary" onclick="guardarOtroIngreso()" style="width:100%;margin-top:8px">Guardar</button>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function guardarOtroIngreso() {
  const body = {
    fecha: document.getElementById('oi-fecha').value,
    concepto: document.getElementById('oi-concepto').value.trim(),
    monto: Math.round(parseFloat(document.getElementById('oi-monto').value||0)*100),
    metodo_pago: document.getElementById('oi-mp').value || null,
    notas: document.getElementById('oi-notas').value.trim() || null,
  };
  if (!body.fecha || !body.concepto || !body.monto) return alert('Fecha, concepto y monto son obligatorios');
  await fetch(API+'/api/admin/otros-ingresos', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body:JSON.stringify(body)});
  cerrarModal('modal-egreso');
  showToast('Ingreso registrado ✓');
  loadFinanzas();
}

// --- EGRESOS ---
let metodosPagoEgreso = [];
let categoriasGasto = [];

async function loadMetodosPago() {
  try { const r = await fetch(API+'/api/admin/metodos-pago-egreso',{credentials:'include'}); metodosPagoEgreso = await r.json(); } catch(e) {}
}

async function loadCategoriasGasto() {
  try { const r = await fetch(API+'/api/admin/categorias-gasto',{credentials:'include'}); categoriasGasto = await r.json(); } catch(e) {}
}

function catGastoOptions(selected) {
  return categoriasGasto.filter(c=>c.activo).map(c => `<option value="${esc(c.nombre)}" ${selected===c.nombre?'selected':''}>${esc(c.nombre)}</option>`).join('');
}

async function loadEgresos() {
  await loadMetodosPago();
  const {desde, hasta} = getFinDates();
  try {
    const r = await fetch(API + '/api/admin/egresos?desde='+desde+'&hasta='+hasta, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    finData.egresos = data;
    const tbody = document.getElementById('egresos-tbody');
    tbody.innerHTML = data.map(e => `<tr>
      <td>${fmtDate(e.fecha)}</td>
      <td>${esc(e.concepto)}${e.es_recurrente ? ' <span style="color:var(--dorado);font-size:10px">RECURRENTE</span>' : ''}</td>
      <td>${esc(e.categoria)}</td>
      <td>${esc(e.metodo_pago||'—')}</td>
      <td>${esc(e.proveedor||'—')}</td>
      <td style="font-weight:600">${fmt$(e.monto)}</td>
      <td><button class="btn-sm" onclick="eliminarEgreso(${e.id})">🗑</button></td>
    </tr>`).join('') || '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--texto2)">Sin egresos</td></tr>';
  } catch(e) {}
}

function mpOptions(selected) {
  return metodosPagoEgreso.filter(m=>m.activo).map(m => `<option value="${esc(m.nombre)}" ${selected===m.nombre?'selected':''}>${esc(m.nombre)}</option>`).join('');
}

async function abrirModalEgreso(eg) {
  await loadMetodosPago();
  await loadCategoriasGasto();
  const hoy = new Date().toISOString().split('T')[0];
  document.getElementById('modal-egreso-body').innerHTML = `
    <div class="field"><label>Fecha *</label><input type="date" id="eg-fecha" value="${eg?.fecha||hoy}"></div>
    <div class="field"><label>Concepto *</label><input id="eg-concepto" value="${esc(eg?.concepto||'')}"></div>
    <div class="field"><label>Categoría</label><select id="eg-cat"><option value="">Selecciona...</option>${catGastoOptions(eg?.categoria)}</select></div>
    <div class="field"><label>Método de pago *</label><select id="eg-mp"><option value="">Selecciona...</option>${mpOptions(eg?.metodo_pago)}</select></div>
    <div class="field"><label>Proveedor</label><input id="eg-prov" value="${esc(eg?.proveedor||'')}" placeholder="Nombre del proveedor (opcional)"></div>
    <div class="field"><label>Monto * (pesos)</label><input type="number" id="eg-monto" step="0.01" value="${eg ? (eg.monto/100).toFixed(2) : ''}"></div>
    <div class="field"><label>Notas</label><textarea id="eg-notas">${esc(eg?.notas||'')}</textarea></div>
    <div class="field"><label># Factura / Nota de referencia</label><input id="eg-ref" value="${esc(eg?.referencia||'')}" placeholder="Opcional"></div>
    <button class="btn-primary" onclick="guardarEgreso(${eg?.id||'null'})" style="width:100%;margin-top:8px">Guardar</button>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function guardarEgreso(id) {
  const body = {
    fecha: document.getElementById('eg-fecha').value,
    concepto: document.getElementById('eg-concepto').value.trim(),
    categoria: document.getElementById('eg-cat').value,
    metodo_pago: document.getElementById('eg-mp').value || null,
    proveedor: document.getElementById('eg-prov')?.value?.trim() || null,
    monto: Math.round(parseFloat(document.getElementById('eg-monto').value || 0) * 100),
    notas: document.getElementById('eg-notas').value.trim() || null,
    referencia: document.getElementById('eg-ref')?.value?.trim() || null,
  };
  if (!body.fecha || !body.concepto || !body.monto) return alert('Fecha, concepto y monto son obligatorios');
  const url = id ? API+'/api/admin/egresos/'+id : API+'/api/admin/egresos';
  const method = id ? 'PUT' : 'POST';
  try {
    const r = await fetch(url, {method, headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(body)});
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      alert('Error al guardar: ' + (err.detail || r.status));
      return;
    }
    cerrarModal('modal-egreso');
    showToast('Gasto guardado ✓');
    await loadEgresos();
  } catch(e) {
    alert('Error de conexión al guardar egreso');
  }
}

async function eliminarEgreso(id) {
  if (!confirm('¿Eliminar este gasto?')) return;
  await fetch(API+'/api/admin/egresos/'+id, {method:'DELETE', credentials:'include'});
  loadEgresos();
}

// --- Gastos recurrentes ---
async function abrirGastosRecurrentes() {
  await loadMetodosPago();
  try {
    const r = await fetch(API+'/api/admin/gastos-recurrentes', {credentials:'include'});
    const data = await r.json();
    const {desde, hasta} = getFinDates();
    // Check which are paid in period
    const er = await fetch(API+'/api/admin/egresos?desde='+desde+'&hasta='+hasta, {credentials:'include'});
    const egs = await er.json();
    const paidNames = new Set(egs.filter(e=>e.es_recurrente).map(e=>e.concepto));

    document.getElementById('modal-egreso-body').innerHTML = `
      <h4 style="margin-bottom:12px">Gastos recurrentes</h4>
      ${data.filter(g=>g.activo).map(g => {
        const paid = paidNames.has(g.nombre);
        return `<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--borde)">
          <div style="flex:1"><strong>${esc(g.nombre)}</strong><br><span style="font-size:11px;color:var(--texto2)">${g.categoria} · ${g.frecuencia} · ${fmt$(g.monto_sugerido)}</span></div>
          ${paid ? '<span style="color:var(--verde);font-size:12px;font-weight:600">Pagado ✓</span>' : `<button class="btn-dorado" onclick="pagarRecurrente(${g.id},'${esc(g.nombre)}',${g.monto_sugerido},'${esc(g.categoria)}')">Marcar pagado</button>`}
          <button class="btn-sm" onclick="eliminarGastoRec(${g.id})" style="font-size:11px">🗑</button>
        </div>`;
      }).join('') || '<div style="color:var(--texto2);padding:12px">Sin gastos recurrentes</div>'}
      <div style="border-top:1px solid var(--borde);margin-top:12px;padding-top:12px">
        <strong style="font-size:13px">Agregar gasto recurrente</strong>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px">
          <input id="gr-nombre" placeholder="Nombre" style="padding:6px 8px;border:1px solid var(--borde);border-radius:6px;font-size:12px">
          <select id="gr-cat" style="padding:6px;font-size:12px"><option value="servicios">Servicios</option><option value="nomina">Nómina</option><option value="insumos">Insumos</option><option value="mantenimiento">Mantenimiento</option><option value="otro">Otro</option></select>
          <select id="gr-freq" style="padding:6px;font-size:12px"><option value="mensual">Mensual</option><option value="quincenal">Quincenal</option><option value="semanal">Semanal</option></select>
          <input type="number" id="gr-monto" placeholder="Monto sugerido" step="0.01" style="padding:6px 8px;border:1px solid var(--borde);border-radius:6px;font-size:12px">
        </div>
        <button class="btn-primary" onclick="crearGastoRec()" style="margin-top:8px;width:100%">Agregar</button>
      </div>
    `;
    document.getElementById('modal-egreso').classList.add('active');
  } catch(e) {}
}

async function pagarRecurrente(id, nombre, monto, categoria) {
  await loadMetodosPago();
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4>Pagar: ${esc(nombre)}</h4>
    <div class="field"><label>Monto real (pesos)</label><input type="number" id="pr-monto" value="${(monto/100).toFixed(2)}" step="0.01"></div>
    <div class="field"><label>Método de pago *</label><select id="pr-mp"><option value="">Selecciona...</option>${mpOptions()}</select></div>
    <div class="field"><label>Fecha de pago</label><input type="date" id="pr-fecha" value="${new Date().toISOString().split('T')[0]}"></div>
    <div class="field"><label>Notas</label><input id="pr-notas"></div>
    <button class="btn-primary" onclick="confirmarPagoRec('${esc(nombre)}','${esc(categoria)}')" style="width:100%;margin-top:8px">Confirmar pago</button>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function confirmarPagoRec(nombre, categoria) {
  const body = {
    fecha: document.getElementById('pr-fecha').value,
    concepto: nombre,
    categoria: categoria,
    metodo_pago: document.getElementById('pr-mp').value || null,
    monto: Math.round(parseFloat(document.getElementById('pr-monto').value||0)*100),
    notas: document.getElementById('pr-notas').value.trim() || null,
    es_recurrente: true,
  };
  if (!body.monto) return alert('Monto es obligatorio');
  await fetch(API+'/api/admin/egresos', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(body)});
  cerrarModal('modal-egreso');
  showToast('Pago registrado ✓');
  loadEgresos();
}

async function crearGastoRec() {
  const nombre = document.getElementById('gr-nombre').value.trim();
  if (!nombre) return alert('Nombre requerido');
  await fetch(API+'/api/admin/gastos-recurrentes', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({nombre, categoria: document.getElementById('gr-cat').value, frecuencia: document.getElementById('gr-freq').value, monto_sugerido: Math.round(parseFloat(document.getElementById('gr-monto').value||0)*100)})
  });
  abrirGastosRecurrentes();
}

async function eliminarGastoRec(id) {
  if (!confirm('¿Eliminar?')) return;
  await fetch(API+'/api/admin/gastos-recurrentes/'+id, {method:'DELETE', credentials:'include'});
  abrirGastosRecurrentes();
}

// --- Categorías de gasto ---
async function abrirCategoriasGasto() {
  await loadCategoriasGasto();
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4>Categorías de gasto</h4>
    ${categoriasGasto.map(c => `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--borde)">
      <input value="${esc(c.nombre)}" id="cg-name-${c.id}" style="flex:1;padding:4px 8px;border:1px solid var(--borde);border-radius:4px;font-size:12px">
      <label style="font-size:12px;display:flex;align-items:center;gap:4px"><input type="checkbox" ${c.activo?'checked':''} onchange="toggleCG(${c.id},this.checked)"> Activo</label>
      <button class="btn-sm" onclick="guardarCG(${c.id})" style="font-size:11px">Guardar</button>
      ${c.egresos === 0 ? `<button class="btn-danger" style="font-size:11px;padding:4px 6px" onclick="eliminarCG(${c.id})">Eliminar</button>` : `<span style="font-size:10px;color:var(--texto2)" title="${c.egresos} egresos">${c.egresos} usos</span>`}
    </div>`).join('')}
    <div style="display:flex;gap:6px;margin-top:12px">
      <input id="cg-nuevo" placeholder="Nueva categoría" style="flex:1;padding:6px 10px;border:1px solid var(--borde);border-radius:6px;font-size:13px">
      <button class="btn-primary" onclick="crearCG()">Agregar</button>
    </div>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function guardarCG(id) {
  const nombre = document.getElementById('cg-name-'+id)?.value?.trim();
  if (!nombre) return;
  await fetch(API+'/api/admin/categorias-gasto/'+id, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({nombre})});
  showToast('Guardado');
}

async function toggleCG(id, activo) {
  await fetch(API+'/api/admin/categorias-gasto/'+id, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({activo})});
}

async function eliminarCG(id) {
  if (!confirm('Eliminar?')) return;
  const r = await fetch(API+'/api/admin/categorias-gasto/'+id, {method:'DELETE', credentials:'include'});
  if (!r.ok) { const e = await r.json(); alert(e.detail||'Error'); return; }
  abrirCategoriasGasto();
}

async function crearCG() {
  const nombre = document.getElementById('cg-nuevo').value.trim();
  if (!nombre) return;
  await fetch(API+'/api/admin/categorias-gasto', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({nombre})});
  abrirCategoriasGasto();
}

// --- Métodos de pago egresos ---
async function abrirMetodosPagoEgreso() {
  await loadMetodosPago();
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4>Métodos de pago para egresos</h4>
    ${metodosPagoEgreso.map(m => `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--borde)" id="mpe-row-${m.id}">
      <input value="${esc(m.nombre)}" id="mpe-name-${m.id}" style="flex:1;padding:4px 8px;border:1px solid var(--borde);border-radius:4px;font-size:12px">
      <label style="font-size:12px;display:flex;align-items:center;gap:4px"><input type="checkbox" ${m.activo?'checked':''} onchange="toggleMPE(${m.id},this.checked)"> Activo</label>
      <button class="btn-sm" onclick="guardarMPE(${m.id})" style="font-size:11px">Guardar</button>
      <button class="btn-danger" style="font-size:11px;padding:4px 6px" onclick="eliminarMPE(${m.id})" title="Eliminar">🗑</button>
    </div>`).join('')}
    <div style="display:flex;gap:6px;margin-top:12px">
      <input id="mpe-nuevo" placeholder="Nuevo método" style="flex:1;padding:6px 10px;border:1px solid var(--borde);border-radius:6px;font-size:13px">
      <button class="btn-primary" onclick="crearMPE()">Agregar</button>
    </div>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function toggleMPE(id, activo) {
  await fetch(API+'/api/admin/metodos-pago-egreso/'+id, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({activo})});
}

async function guardarMPE(id) {
  const nombre = document.getElementById('mpe-name-'+id)?.value?.trim();
  if (!nombre) return;
  await fetch(API+'/api/admin/metodos-pago-egreso/'+id, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({nombre})});
  showToast('Guardado ✓');
}

async function eliminarMPE(id) {
  if (!confirm('¿Eliminar este método de pago?')) return;
  const r = await fetch(API+'/api/admin/metodos-pago-egreso/'+id, {method:'DELETE', credentials:'include'});
  if (!r.ok) { const e = await r.json(); alert(e.detail||'No se puede eliminar'); return; }
  abrirMetodosPagoEgreso();
}

async function crearMPE() {
  const nombre = document.getElementById('mpe-nuevo').value.trim();
  if (!nombre) return;
  await fetch(API+'/api/admin/metodos-pago-egreso', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({nombre})});
  abrirMetodosPagoEgreso();
}

// --- UTILIDAD ---
async function loadUtilidad() {
  const {desde, hasta} = getFinDates();
  let totalIng = 0, totalEgr = 0;
  try {
    if (!finData.ingresos) await loadFinanzas();
    totalIng = finData.totalIngresos || finData.ingresos?.resumen?.total_vendido || 0;
    const r = await fetch(API+'/api/admin/egresos?desde='+desde+'&hasta='+hasta, {credentials:'include'});
    const egs = await r.json();
    totalEgr = egs.reduce((s,e) => s + (e.monto||0), 0);
  } catch(e) {}
  const util = totalIng - totalEgr;
  const color = util >= 0 ? 'var(--verde)' : 'var(--rojo)';
  document.getElementById('utilidad-card').innerHTML = `
    <div class="kpi-row">
      <div class="kpi-card"><div class="kpi-label">Ingresos</div><div class="kpi-value" style="color:var(--verde)">${fmt$(totalIng)}</div></div>
      <div class="kpi-card"><div class="kpi-label">Egresos</div><div class="kpi-value" style="color:var(--rojo)">${fmt$(totalEgr)}</div></div>
      <div class="kpi-card" style="border-color:${color}"><div class="kpi-label">Utilidad bruta</div><div class="kpi-value" style="color:${color}">${fmt$(util)}</div></div>
    </div>
    <div style="font-size:12px;color:var(--texto2);margin-top:8px">Cálculo estimado. No incluye impuestos ni depreciaciones.</div>
  `;
  // Chart
  try {
    const r = await fetch(API+'/api/admin/finanzas/flujo-caja?desde='+desde+'&hasta='+hasta, {credentials:'include'});
    const days = await r.json();
    if (finCharts.utilidad) finCharts.utilidad.destroy();
    finCharts.utilidad = new Chart(document.getElementById('utilidad-chart'), {
      type:'bar', data:{labels:days.map(d=>d.fecha), datasets:[
        {label:'Ingresos',data:days.map(d=>d.ingresos/100),backgroundColor:'#193a2c'},
        {label:'Egresos',data:days.map(d=>d.egresos/100),backgroundColor:'#ef4444'},
      ]}, options:{responsive:true,plugins:{legend:{position:'bottom'}}}
    });
  } catch(e) {}
}

// --- FLUJO DE CAJA ---
async function loadFlujo() {
  const {desde, hasta} = getFinDates();
  try {
    const r = await fetch(API+'/api/admin/finanzas/flujo-caja?desde='+desde+'&hasta='+hasta, {credentials:'include'});
    finData.flujo = await r.json();
    const days = finData.flujo;
    // Chart
    if (finCharts.flujo) finCharts.flujo.destroy();
    finCharts.flujo = new Chart(document.getElementById('flujo-chart'), {
      type:'line', data:{labels:days.map(d=>d.fecha), datasets:[
        {label:'Ingresos',data:days.map(d=>d.ingresos/100),borderColor:'#193a2c',backgroundColor:'rgba(25,58,44,.1)',fill:true,tension:.3},
        {label:'Egresos',data:days.map(d=>d.egresos/100),borderColor:'#ef4444',backgroundColor:'rgba(239,68,68,.1)',fill:true,tension:.3},
      ]}, options:{responsive:true,plugins:{legend:{position:'bottom'}}}
    });
    // Table
    document.getElementById('flujo-tbody').innerHTML = days.map(d => `<tr>
      <td>${d.fecha}</td>
      <td style="color:var(--verde)">${fmt$(d.ingresos)}</td>
      <td style="color:var(--rojo)">${fmt$(d.egresos)}</td>
      <td style="font-weight:600;color:${d.saldo>=0?'var(--verde)':'var(--rojo)'}">${fmt$(d.saldo)}</td>
      <td style="font-weight:600">${fmt$(d.acumulado)}</td>
    </tr>`).join('');
  } catch(e) {}
}

async function exportarFlujo() {
  if (!finData.flujo) return;
  let csv = 'Fecha,Ingresos,Egresos,Saldo,Acumulado\n';
  finData.flujo.forEach(d => { csv += `${d.fecha},${(d.ingresos/100).toFixed(2)},${(d.egresos/100).toFixed(2)},${(d.saldo/100).toFixed(2)},${(d.acumulado/100).toFixed(2)}\n`; });
  downloadCSV(csv, 'flujo_caja.csv');
}

// --- CORTES DE CAJA ---
async function loadCortes() {
  document.getElementById('cortes-list').innerHTML = '<div style="color:var(--texto2);font-size:13px;padding:20px;text-align:center">Cortes de caja disponibles en el POS → Transacciones → Corte de caja</div>';
}

// --- EXPORTAR ---
async function exportarFinanzas(tipo) {
  const {desde, hasta} = getFinDates();
  if (tipo === 'ingresos') {
    try {
      const r = await fetch(API+'/api/admin/productos/exportar'.replace('productos/exportar','') + 'pos/pedidos-hoy?periodo=rango&fecha_inicio='+desde+'&fecha_fin='+hasta, {credentials:'include'});
      const data = await r.json();
      let csv = 'Fecha,Folio,Cliente,Canal,Metodo Pago,Total\n';
      (data.finalizados||[]).forEach(p => { csv += `"${p.fecha_entrega||''}","${p.folio}","${p.cliente_nombre||''}","${p.canal}","${p.forma_pago||''}",${(p.total||0)/100}\n`; });
      downloadCSV(csv, 'ingresos_'+desde+'_'+hasta+'.csv');
    } catch(e) {}
  } else {
    try {
      const r = await fetch(API+'/api/admin/egresos/exportar?desde='+desde+'&hasta='+hasta, {credentials:'include'});
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = 'egresos_'+desde+'_'+hasta+'.xlsx'; a.click();
    } catch(e) {}
  }
}

function abrirCorteCajaPDF() {
  const {desde, hasta} = getFinDates();
  const periodo = document.getElementById('fin-periodo').value;
  const labels = {hoy:'Hoy',semana:'Esta semana',mes:'Este mes',rango:'Rango personalizado'};
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4 style="margin-bottom:12px">Generar resumen financiero</h4>
    <div style="background:var(--crema);border-radius:10px;padding:16px;margin-bottom:16px">
      <div style="font-size:13px;color:var(--texto2)">Período: <strong>${labels[periodo]||periodo}</strong></div>
      <div style="font-size:14px;font-weight:600;color:var(--verde);margin-top:4px">${desde} → ${hasta}</div>
    </div>
    <div style="font-size:12px;color:var(--texto2);margin-bottom:12px">Se generará un PDF con ingresos, egresos, flujo de caja y desglose por método de pago.</div>
    <button class="btn-primary" onclick="generarCortePDF('${desde}','${hasta}')" style="width:100%" id="btn-corte-pdf">Generar PDF</button>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function generarCortePDF(desde, hasta) {
  const btn = document.getElementById('btn-corte-pdf');
  btn.disabled = true; btn.textContent = 'Generando...';
  try {
    const r = await fetch(API+'/api/admin/finanzas/corte-pdf?desde='+desde+'&hasta='+hasta, {method:'POST', credentials:'include'});
    if (!r.ok) { alert('Error al generar PDF'); btn.disabled=false; btn.textContent='Generar PDF'; return; }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'corte_'+desde+'_'+hasta+'.pdf'; a.click();
    cerrarModal('modal-egreso');
    showToast('Corte generado ✓');
  } catch(e) { alert('Error de conexión'); btn.disabled=false; btn.textContent='Generar PDF'; }
}

function downloadCSV(csv, filename) {
  const blob = new Blob([csv], {type:'text/csv'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
}

// ══════ ESTADÍSTICAS ══════
let estChart = null;
let estPeriodo = 'semana';
let estActiveKpi = 'facturacion';
let estCache = {};

function getEstDates() {
  // Use Chihuahua timezone for date calculations
  const now = new Date(new Date().toLocaleString('en-US',{timeZone:'America/Chihuahua'}));
  const hoy = now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0');
  if (estPeriodo === 'rango') return {desde: document.getElementById('est-desde').value||hoy, hasta: document.getElementById('est-hasta').value||hoy};
  if (estPeriodo === 'hoy') return {desde:hoy, hasta:hoy};
  if (estPeriodo === 'semana') { const d = new Date(now); d.setDate(d.getDate()-d.getDay()); const ds=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); return {desde:ds, hasta:hoy}; }
  if (estPeriodo === 'mes') return {desde:hoy.substring(0,8)+'01', hasta:hoy};
  if (estPeriodo === 'anio') return {desde:hoy.substring(0,5)+'01-01', hasta:hoy};
  return {desde:hoy, hasta:hoy};
}

function setEstPeriodo(p) {
  estPeriodo = p;
  document.querySelectorAll('.est-per-btn').forEach(b => { b.style.background=''; b.style.color=''; });
  const btn = document.querySelector(`.est-per-btn[data-per="${p}"]`);
  if (btn) { btn.style.background='var(--verde)'; btn.style.color='#fff'; }
  document.getElementById('est-desde').style.display = p==='rango' ? '' : 'none';
  document.getElementById('est-hasta').style.display = p==='rango' ? '' : 'none';
  if (p !== 'rango') loadEstadisticas();
}

const EST_KPIS = [
  {id:'facturacion', label:'Facturación', icon:'💰'},
  {id:'ventas', label:'Ventas', icon:'🛒'},
  {id:'ticket', label:'Ticket medio', icon:'🧾'},
  {id:'ganancia', label:'Ganancia', icon:'📈'},
  {id:'medios', label:'Medio de pago', icon:'💳'},
  {id:'productos', label:'Productos top', icon:'📦'},
  {id:'clientes', label:'Mejores clientes', icon:'👤'},
  {id:'canales', label:'Canal de venta', icon:'🌐'},
];

async function loadEstadisticas() {
  estCache = {};
  const {desde, hasta} = getEstDates();
  // Load facturacion first for sidebar KPIs
  const sb = document.getElementById('est-sidebar');
  sb.innerHTML = EST_KPIS.map(k => `<div class="est-kpi-card" id="est-kpi-${k.id}" onclick="selectEstKpi('${k.id}')" style="padding:12px;border-left:3px solid transparent;margin-bottom:6px;cursor:pointer;border-radius:0 8px 8px 0;transition:all .15s">
    <div style="font-size:11px;color:var(--texto2);text-transform:uppercase">${k.icon} ${k.label}</div>
    <div style="font-size:20px;font-weight:700;color:var(--verde)" id="est-val-${k.id}">—</div>
    <div style="font-size:11px" id="est-vs-${k.id}"></div>
  </div>`).join('');
  // Load all KPI values async
  loadEstKpiValues(desde, hasta);
  selectEstKpi(estActiveKpi);
}

async function loadEstKpiValues(desde, hasta) {
  const q = `desde=${desde}&hasta=${hasta}`;
  // Facturación
  try { const r = await fetch(API+'/api/admin/estadisticas/facturacion?'+q,{credentials:'include'}); const d = await r.json(); estCache.facturacion = d; estCache.ventas = d;
    document.getElementById('est-val-facturacion').textContent = fmt$(d.total);
    document.getElementById('est-vs-facturacion').innerHTML = vsHtml(d.vs_anterior);
  } catch(e) {}
  // Ventas = num_ventas from facturacion
  if (estCache.facturacion) {
    document.getElementById('est-val-ventas').textContent = estCache.facturacion.num_ventas;
  }
  // Ticket medio
  try { const r = await fetch(API+'/api/admin/estadisticas/ticket-medio?'+q,{credentials:'include'}); const d = await r.json(); estCache.ticket = d;
    document.getElementById('est-val-ticket').textContent = fmt$(d.valor);
    document.getElementById('est-vs-ticket').innerHTML = vsHtml(d.vs_anterior);
  } catch(e) {}
  // Ganancia
  try { const r = await fetch(API+'/api/admin/estadisticas/ganancia?'+q,{credentials:'include'}); const d = await r.json(); estCache.ganancia = d;
    document.getElementById('est-val-ganancia').textContent = fmt$(d.total);
  } catch(e) {}
  // Medios
  try { const r = await fetch(API+'/api/admin/estadisticas/medios-pago?'+q,{credentials:'include'}); const d = await r.json(); estCache.medios = d;
    document.getElementById('est-val-medios').textContent = d.mas_usado;
  } catch(e) {}
  // Productos
  try { const r = await fetch(API+'/api/admin/estadisticas/productos-top?'+q,{credentials:'include'}); const d = await r.json(); estCache.productos = d;
    document.getElementById('est-val-productos').textContent = d.por_valor?.[0]?.nombre || '—';
  } catch(e) {}
  // Clientes
  try { const r = await fetch(API+'/api/admin/estadisticas/clientes-top?'+q,{credentials:'include'}); const d = await r.json(); estCache.clientes = d;
    document.getElementById('est-val-clientes').textContent = d.por_valor?.[0]?.nombre || '—';
  } catch(e) {}
  // Canales
  try { const r = await fetch(API+'/api/admin/estadisticas/canales?'+q,{credentials:'include'}); const d = await r.json(); estCache.canales = d;
    const top = d.distribucion?.sort((a,b)=>b.total-a.total)[0];
    document.getElementById('est-val-canales').textContent = top?.canal || '—';
  } catch(e) {}
}

function vsHtml(vs) {
  if (!vs) return '';
  const color = vs >= 0 ? 'var(--verde)' : 'var(--rojo)';
  return `<span style="color:${color};font-weight:600">${vs >= 0 ? '+' : ''}${vs}%</span> vs anterior`;
}

function selectEstKpi(id) {
  estActiveKpi = id;
  document.querySelectorAll('.est-kpi-card').forEach(c => { c.style.borderLeftColor='transparent'; c.style.background=''; });
  const card = document.getElementById('est-kpi-'+id);
  if (card) { card.style.borderLeftColor='var(--dorado)'; card.style.background='var(--crema)'; }
  renderEstChart(id);
}

function renderEstChart(id) {
  const data = estCache[id];
  const title = EST_KPIS.find(k=>k.id===id)?.label || '';
  document.getElementById('est-chart-title').textContent = title;
  document.getElementById('est-chart-tabs').innerHTML = '';
  if (estChart) { estChart.destroy(); estChart = null; }
  const ctx = document.getElementById('est-main-chart');
  const thead = document.getElementById('est-table-head');
  const tbody = document.getElementById('est-table-body');
  if (!data) { tbody.innerHTML = '<tr><td style="padding:20px;color:var(--texto2);text-align:center">Sin datos para este período</td></tr>'; thead.innerHTML = ''; return; }

  if (id === 'facturacion' || id === 'ventas') {
    const pd = data.por_dia || [];
    const isVentas = id === 'ventas';
    estChart = new Chart(ctx, {
      type: isVentas ? 'bar' : 'line',
      data: { labels: pd.map(d=>d.fecha), datasets: [{label: title, data: pd.map(d=> isVentas ? d.ventas : d.total/100), backgroundColor:'#193a2c', borderColor:'#193a2c', fill: !isVentas, tension:.3}] },
      options: {responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}}
    });
    thead.innerHTML = '<tr><th>Fecha</th><th>Facturación</th><th># Ventas</th><th>Ticket medio</th></tr>';
    tbody.innerHTML = pd.map(d => `<tr><td>${d.fecha}</td><td>${fmt$(d.total)}</td><td>${d.ventas}</td><td>${d.ventas ? fmt$(Math.round(d.total/d.ventas)) : '—'}</td></tr>`).join('');
  } else if (id === 'ticket') {
    const pd = data.por_dia || [];
    estChart = new Chart(ctx, {
      type:'line', data:{labels:pd.map(d=>d.fecha), datasets:[{label:'Ticket medio',data:pd.map(d=>d.promedio/100),borderColor:'#193a2c',fill:false,tension:.3}]},
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}
    });
    thead.innerHTML = '<tr><th>Fecha</th><th>Promedio</th><th>Mínimo</th><th>Máximo</th></tr>';
    tbody.innerHTML = pd.map(d => `<tr><td>${d.fecha}</td><td>${fmt$(d.promedio)}</td><td>${fmt$(d.min)}</td><td>${fmt$(d.max)}</td></tr>`).join('');
  } else if (id === 'ganancia') {
    const pd = data.por_dia || [];
    estChart = new Chart(ctx, {
      type:'bar', data:{labels:pd.map(d=>d.fecha), datasets:[{label:'Ganancia',data:pd.map(d=>d.ganancia/100),backgroundColor:'#193a2c'}]},
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}}}
    });
    thead.innerHTML = '<tr><th>Fecha</th><th>Facturación</th><th>Costo</th><th>Ganancia</th><th>Margen</th></tr>';
    tbody.innerHTML = pd.map(d => `<tr><td>${d.fecha}</td><td>${fmt$(d.facturacion)}</td><td>${fmt$(d.costo)}</td><td style="color:${d.ganancia>=0?'var(--verde)':'var(--rojo)'}">${fmt$(d.ganancia)}</td><td>${d.margen}%</td></tr>`).join('');
    if (data.productos_sin_costo) tbody.innerHTML += `<tr><td colspan="5" style="color:var(--dorado);font-size:12px;padding:8px">${data.productos_sin_costo} productos sin costo registrado — ganancia puede ser mayor</td></tr>`;
  } else if (id === 'medios') {
    const dist = data.distribucion || [];
    const colors = {'Efectivo':'#193a2c','Tarjeta débito':'#2d5a3d','Tarjeta crédito':'#2d5a3d','Transferencia':'#d4a843','Link de pago':'#6b9e78'};
    estChart = new Chart(ctx, {
      type:'doughnut', data:{labels:dist.map(d=>d.metodo), datasets:[{data:dist.map(d=>d.total/100), backgroundColor:dist.map(d=>colors[d.metodo]||'#9ca3af')}]},
      options:{responsive:true,maintainAspectRatio:false}
    });
    thead.innerHTML = '<tr><th>Método</th><th># Trans.</th><th>Total</th><th>%</th></tr>';
    tbody.innerHTML = dist.map(d => `<tr><td>${esc(d.metodo)}</td><td>${d.count}</td><td>${fmt$(d.total)}</td><td>${d.porcentaje}%</td></tr>`).join('');
  } else if (id === 'productos') {
    const pv = data.por_valor || [];
    estChart = new Chart(ctx, {
      type:'bar', data:{labels:pv.map(d=>d.nombre), datasets:[{label:'Total',data:pv.map(d=>d.total/100),backgroundColor:'#193a2c'}]},
      options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}}}
    });
    thead.innerHTML = '<tr><th>#</th><th>Producto</th><th>Categoría</th><th>Unidades</th><th>Total</th></tr>';
    tbody.innerHTML = pv.map((d,i) => `<tr><td>${i+1}</td><td>${esc(d.nombre)}</td><td>${esc(d.categoria)}</td><td>${d.cantidad}</td><td>${fmt$(d.total)}</td></tr>`).join('');
  } else if (id === 'clientes') {
    const cv = data.por_valor || [];
    estChart = new Chart(ctx, {
      type:'bar', data:{labels:cv.map(d=>d.nombre), datasets:[{label:'Total',data:cv.map(d=>d.total/100),backgroundColor:'#d4a843'}]},
      options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}}}
    });
    thead.innerHTML = '<tr><th>#</th><th>Cliente</th><th>Pedidos</th><th>Total</th><th>Ticket medio</th><th>Última</th></tr>';
    tbody.innerHTML = cv.map((d,i) => `<tr><td>${i+1}</td><td>${esc(d.nombre)}</td><td>${d.pedidos}</td><td>${fmt$(d.total)}</td><td>${fmt$(d.ticket_medio)}</td><td>${fmtDate(d.ultima)}</td></tr>`).join('');
  } else if (id === 'canales') {
    const dist = data.distribucion || [];
    const colors = {'Mostrador':'#193a2c','Web':'#d4a843','WhatsApp':'#6b9e78'};
    estChart = new Chart(ctx, {
      type:'doughnut', data:{labels:dist.map(d=>d.canal), datasets:[{data:dist.map(d=>d.total/100), backgroundColor:dist.map(d=>colors[d.canal]||'#9ca3af')}]},
      options:{responsive:true,maintainAspectRatio:false}
    });
    thead.innerHTML = '<tr><th>Canal</th><th># Ventas</th><th>Total</th><th>%</th></tr>';
    tbody.innerHTML = dist.map(d => `<tr><td>${esc(d.canal)}</td><td>${d.count}</td><td>${fmt$(d.total)}</td><td>${d.porcentaje}%</td></tr>`).join('');
  }
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
    renderCfgBancarios(cfg);
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
    // Catálogo config moved to Página Web sub-tabs
  } catch(e) {}
}

async function renderCfgBancarios(cfg) {
  const el = document.getElementById('cfg-banco-content');
  // Load cuentas
  let cuentas = [];
  try { const r = await fetch(API+'/api/admin/cuentas-transferencia',{credentials:'include'}); cuentas = await r.json(); } catch(e) {}

  let html = '<div style="max-width:700px">';
  // SECTION 1: Cuentas transferencia
  html += '<h4 style="font-size:14px;color:var(--verde);margin-bottom:12px">Cuentas de transferencia</h4>';
  cuentas.forEach(c => {
    html += `<div style="border:1px solid ${c.activa?'var(--dorado)':'var(--borde)'};border-radius:10px;padding:14px;margin-bottom:10px;${c.activa?'background:#faf8f5':''}">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <label style="font-size:13px;display:flex;align-items:center;gap:6px;cursor:pointer"><input type="radio" name="cuenta-activa" ${c.activa?'checked':''} onchange="activarCuenta(${c.id})"> ${c.activa?'<strong style="color:var(--dorado)">Cuenta activa</strong>':'Activar'}</label>
        <span style="flex:1"></span>
        ${!c.activa ? `<button class="btn-danger" style="font-size:11px;padding:4px 8px" onclick="eliminarCuenta(${c.id})">Eliminar</button>` : ''}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
        <div class="config-field"><label>Banco</label><input value="${esc(c.banco)}" id="ct-banco-${c.id}"></div>
        <div class="config-field"><label>Titular</label><input value="${esc(c.titular)}" id="ct-titular-${c.id}"></div>
        <div class="config-field"><label>No. tarjeta</label><input value="${esc(c.tarjeta)}" id="ct-tarjeta-${c.id}"></div>
        <div class="config-field"><label>CLABE</label><input value="${esc(c.clabe)}" id="ct-clabe-${c.id}"></div>
      </div>
      <button class="btn-sm" onclick="guardarCuenta(${c.id})" style="margin-top:8px">Guardar cambios</button>
    </div>`;
  });
  html += '<button class="btn-primary" onclick="nuevaCuenta()" style="margin-top:4px">+ Agregar cuenta</button>';

  // SECTION 2: OXXO
  html += '<h4 style="font-size:14px;color:var(--verde);margin:24px 0 12px;padding-top:16px;border-top:2px solid var(--borde)">OXXO</h4>';
  html += `<div class="toggle-row"><label>OXXO activo</label><input type="checkbox" id="oxxo-toggle" ${cfg.oxxo_activo==='true'?'checked':''} onchange="saveConfigField('oxxo_activo',String(this.checked))"></div>
    <div class="config-field"><label>Nombre (ej. Spin By Oxxo)</label><input id="oxxo-nom" value="${esc(cfg.oxxo_nombre||'')}"></div>
    <div class="config-field"><label>Número de tarjeta</label><input id="oxxo-tar" value="${esc(cfg.oxxo_tarjeta||'')}"></div>
    <button class="btn-sm" onclick="guardarOxxo()" style="margin-top:4px">Guardar OXXO</button>`;

  // SECTION 3: Mensajes de instrucciones de pago
  html += '<h4 style="font-size:14px;color:var(--verde);margin:24px 0 12px;padding-top:16px;border-top:2px solid var(--borde)">Instrucciones de pago</h4>';
  html += `<div class="config-field"><label>Instrucciones pedido normal</label><textarea id="msg-normal" rows="4">${esc(cfg.mensaje_pago_normal||'')}</textarea></div>
    <div class="config-field"><label>Instrucciones pedido funeral</label><textarea id="msg-funeral" rows="4">${esc(cfg.mensaje_pago_funeral||'')}</textarea></div>
    <button class="btn-sm" onclick="guardarMensajesPago()" style="margin-top:4px">Guardar instrucciones</button>`;

  html += '</div>';
  el.innerHTML = html;
}

async function activarCuenta(id) {
  await fetch(API+'/api/admin/cuentas-transferencia/'+id+'/activar',{method:'POST',credentials:'include'});
  showToast('Cuenta activada');
  loadConfig();
}

async function guardarCuenta(id) {
  const body = {
    banco: document.getElementById('ct-banco-'+id)?.value||'',
    titular: document.getElementById('ct-titular-'+id)?.value||'',
    tarjeta: document.getElementById('ct-tarjeta-'+id)?.value||'',
    clabe: document.getElementById('ct-clabe-'+id)?.value||'',
  };
  await fetch(API+'/api/admin/cuentas-transferencia/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(body)});
  showToast('Cuenta guardada');
}

async function nuevaCuenta() {
  await fetch(API+'/api/admin/cuentas-transferencia',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({banco:'',titular:'',tarjeta:'',clabe:''})});
  loadConfig();
}

async function eliminarCuenta(id) {
  if (!confirm('Eliminar esta cuenta?')) return;
  const r = await fetch(API+'/api/admin/cuentas-transferencia/'+id,{method:'DELETE',credentials:'include'});
  if (!r.ok) { const e = await r.json(); alert(e.detail||'Error'); return; }
  loadConfig();
}

async function guardarOxxo() {
  await saveConfigField('oxxo_nombre', document.getElementById('oxxo-nom').value);
  await saveConfigField('oxxo_tarjeta', document.getElementById('oxxo-tar').value);
  showToast('OXXO guardado');
}

async function guardarMensajesPago() {
  await saveConfigField('mensaje_pago_normal', document.getElementById('msg-normal').value);
  await saveConfigField('mensaje_pago_funeral', document.getElementById('msg-funeral').value);
  showToast('Instrucciones guardadas');
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
