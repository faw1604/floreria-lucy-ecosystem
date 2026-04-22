/* ═══════════════════════════════════════════
   ADMIN PANEL — Florería Lucy
   ═══════════════════════════════════════════ */

const API = '';
const WHATSAPP = '5216143349392';
let _clChatInterval = null;

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
    facturacion: loadFacturacion,
    usuarios: loadUsuarios,
    config: loadConfig,
  };
  if (loaders[sec]) loaders[sec]();
  // Claudia chat polling
  if (sec === 'claudia') {
    if (!_clChatInterval) _clChatInterval = setInterval(() => { if (!document.hidden) loadClaudiaChats(); }, 15000);
  } else if (_clChatInterval) {
    clearInterval(_clChatInterval);
    _clChatInterval = null;
  }
}

// Init from hash
(function() {
  const hash = location.hash.replace('#', '') || 'ventas';
  navTo(hash);
})();

async function logout() {
  await fetch(API + '/auth/logout', {credentials:'include'});
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
function fmtDate(d) { if (!d) return ''; const s = String(d); const dt = s.length === 10 ? new Date(s + 'T12:00:00') : new Date(s); return dt.toLocaleDateString('es-MX', {timeZone:'America/Chihuahua', day:'2-digit', month:'short', year:'numeric'}); }

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
let _lastAdminPendHash = '';
async function loadPendientes() {
  try {
    const canal = document.getElementById('pend-canal-filter').value;
    const estado = document.getElementById('pend-estado-filter').value;
    let url = API + '/pos/pedidos-hoy?periodo=todos&estado=pendiente_pago';
    if (canal) url += '&canal=' + canal;
    const r = await fetch(url, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    let rows = [...(data.pendientes || [])];
    if (estado) rows = rows.filter(p => p.estado === estado);
    const hash = JSON.stringify(rows.map(p => p.id + '|' + p.estado));
    if (hash === _lastAdminPendHash) return;
    _lastAdminPendHash = hash;
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
let _lastAdminTransHash = '';
async function loadTransacciones() {
  try {
    const periodo = document.getElementById('trans-periodo').value;
    const r = await fetch(API + '/pos/pedidos-hoy?periodo=' + periodo, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    const rows = data.finalizados || [];
    const hash = JSON.stringify(rows.map(p => p.id + '|' + p.estado + '|' + p.total));
    if (hash === _lastAdminTransHash) return;
    _lastAdminTransHash = hash;
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
  const q = (document.getElementById('prod-search')?.value || '').trim();
  const stock = document.getElementById('prod-stock-filter')?.value || '';
  const catVisible = status === '1' ? 'true' : status === '0' ? 'false' : '';
  // activo=true por defecto — no mostrar productos eliminados
  let url = API + '/productos/?activo=true&offset=' + prodOffset + '&limit=' + PROD_PAGE;
  if (catVisible) url += '&visible_catalogo=' + catVisible;
  if (cat) url += '&categoria=' + encodeURIComponent(cat);
  if (q) url += '&buscar=' + encodeURIComponent(q);
  if (stock) url += '&stock_filter=' + stock;
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

let _lastProdHash = '';
function renderProdTable() {
  const hash = JSON.stringify(prodAllData.map(p => p.id + '|' + p.activo + '|' + p.visible_catalogo + '|' + p.precio));
  if (hash === _lastProdHash) return;
  _lastProdHash = hash;
  const tbody = document.getElementById('prod-tbody');
  if (!prodAllData.length) { tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--texto2);padding:40px">Sin productos</td></tr>'; return; }
  tbody.innerHTML = prodAllData.map(p => `<tr>
    <td><input type="checkbox" class="prod-check" data-id="${p.id}"></td>
    <td>${p.imagen_url ? '<img src="'+esc(p.imagen_url)+'" class="thumb">' : '—'}</td>
    <td style="font-weight:500">${esc(p.nombre)}${p.destacado ? ' <span style="color:var(--dorado);font-size:10px">★</span>' : ''}${p.precio_descuento ? ' <span style="color:var(--dorado);font-size:10px">OFERTA</span>' : ''}</td>
    <td style="color:var(--texto2)">${esc(p.codigo||'—')}</td>
    <td>${esc(p.categoria)}</td>
    <td style="font-weight:600">${p.precio_descuento ? '<span style="text-decoration:line-through;color:#999;font-weight:400">'+fmt$(p.precio)+'</span> '+fmt$(p.precio_descuento) : fmt$(p.precio)}</td>
    <td>${p.activo ? '<span style="color:var(--verde)">Si</span>' : '<span style="color:var(--rojo)">No</span>'}</td>
    <td><input type="checkbox" ${p.visible_catalogo !== false ? 'checked' : ''} onchange="toggleWebProdQuick(${p.id}, this.checked)" title="Mostrar en catalogo"></td>
    <td id="var-badge-${p.id}"></td>
    <td style="white-space:nowrap"><button class="btn-sm" onclick="editarProducto(${p.id})">Editar</button> <button class="btn-sm" style="color:var(--rojo);border-color:var(--rojo)" onclick="eliminarProducto(${p.id},'${esc(p.nombre)}')">Eliminar</button></td>
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
    <!-- FOTOS EXTRA -->
    <div class="field">
      <label>Fotos adicionales <span style="font-weight:400;color:var(--texto2)">(menú de opciones, detalles, etc.)</span></label>
      <div id="pf-extras-preview" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
        ${(prod?._imagenes_extra||[]).map((url,i) => `
          <div style="position:relative;width:80px;height:80px;border-radius:8px;overflow:hidden;background:var(--borde)">
            <img src="${esc(url)}" style="width:100%;height:100%;object-fit:cover">
            <button onclick="quitarFotoExtra(${i})" style="position:absolute;top:2px;right:2px;background:rgba(0,0,0,.6);color:#fff;border:none;border-radius:50%;width:20px;height:20px;font-size:12px;cursor:pointer;line-height:20px;padding:0">&times;</button>
          </div>
        `).join('')}
      </div>
      <input type="file" id="pf-extras-file" accept="image/*" multiple onchange="subirFotosExtra()">
      <input type="hidden" id="pf-extras" value='${esc(JSON.stringify(prod?._imagenes_extra||[]))}'>
      <div id="pf-extras-status" style="font-size:11px;color:var(--texto2);margin-top:4px"></div>
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
      <input type="hidden" id="pf-activo" value="true">
      <label style="display:flex;align-items:center;gap:6px;font-size:13px"><input type="checkbox" id="pf-web" ${prod?.visible_catalogo !== false ? 'checked' : ''}> Mostrar en catalogo</label>
      <label style="display:flex;align-items:center;gap:6px;font-size:13px"><input type="checkbox" id="pf-destacado" ${prod?.destacado ? 'checked' : ''}> ⭐ Destacado <span style="font-size:10px;color:var(--texto2)">(aparece primero en catalogo)</span></label>
    </div>
    <!-- VENTA POR FRACCIÓN -->
    <div style="border:1px solid var(--borde);border-radius:10px;padding:14px;margin:14px 0">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <label style="font-size:13px;font-weight:600">Vender por fracción (gramos)</label>
        <input type="checkbox" id="pf-fraccion" ${prod?.vender_por_fraccion ? 'checked' : ''} onchange="onFraccionToggle()">
      </div>
      <div style="font-size:11px;color:var(--texto2)">El precio será por <strong>kilo</strong>. En el POS se vende en gramos (cualquier cantidad). El total se calcula automáticamente.</div>
      <div id="pf-fraccion-warn" style="${prod?.vender_por_fraccion ? '' : 'display:none'};font-size:11px;color:var(--naranja);margin-top:6px;padding:6px 8px;background:#fff7ed;border-radius:6px">⚠️ Los productos por fracción NO se muestran en el catálogo web — solo POS.</div>
    </div>
    <!-- STOCK -->
    <div style="border:1px solid var(--borde);border-radius:10px;padding:14px;margin:14px 0">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <label style="font-size:13px;font-weight:600">Control de stock</label>
        <input type="checkbox" id="pf-stock-activo" ${prod?.stock_activo ? 'checked' : ''} onchange="onStockToggle()" ${hasActiveVariants ? 'disabled' : ''}>
      </div>
      ${hasActiveVariants ? '<div style="font-size:11px;color:var(--naranja);margin-bottom:6px">El stock lo controla cada variante</div>' : '<div style="font-size:11px;color:var(--texto2);margin-bottom:6px">Stock desactivado = siempre disponible. Actívalo para controlar piezas limitadas.</div>'}
      <div id="pf-stock-field" style="${prod?.stock_activo && !hasActiveVariants ? '' : 'display:none'}">
        <div class="field"><label id="pf-stock-label">${prod?.vender_por_fraccion ? 'Stock (gramos)' : 'Unidades en stock'}</label><input type="number" id="pf-stock" value="${prod?.stock||0}" min="0"></div>
      </div>
    </div>
    <!-- VARIANTES -->
    <div style="border:1px solid var(--borde);border-radius:10px;padding:14px;margin:14px 0">
      <div style="font-size:13px;font-weight:600;margin-bottom:10px">Variantes</div>
      ${['color','tamaño','estilo','sabor','presentación'].map(tipo => {
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
    <button class="btn-primary" id="btn-guardar-prod" onclick="guardarProducto(${prod?.id||'null'})" style="width:100%;margin-top:12px">Guardar producto</button>
  `;
  onCatChange();
  document.getElementById('modal-producto').classList.add('active');
  // Scroll al inicio del modal
  const modalBody = document.querySelector('#modal-producto .modal');
  if (modalBody) modalBody.scrollTop = 0;
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
      <div class="field" style="margin-bottom:6px"><label style="font-size:11px;display:flex;align-items:center;gap:4px">Controlar stock <input type="checkbox" class="vr-stock-activo" ${v.stock_activo ? 'checked' : ''} onchange="toggleStockVariante(this)"></label></div>
      <div class="field vr-stock-wrap" style="margin-bottom:6px;${v.stock_activo ? '' : 'display:none'}"><label style="font-size:11px">Stock</label><input type="number" class="vr-stock" value="${v.stock||0}" min="0" style="font-size:12px;padding:6px 8px"></div>
      <div class="field" style="margin-bottom:0;grid-column:1/-1"><label style="font-size:11px">Foto</label>
        <div style="display:flex;align-items:center;gap:8px">
          <div class="vr-img-preview" style="width:48px;height:48px;border-radius:6px;background:var(--borde);overflow:hidden;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:18px;color:var(--texto2)">${v.imagen_url ? `<img src="${esc(v.imagen_url)}" style="width:100%;height:100%;object-fit:cover">` : '📷'}</div>
          <div style="flex:1">
            <input type="file" class="vr-img-file" accept="image/*" style="font-size:11px" onchange="subirImagenVariante(this)">
            <div class="vr-img-status" style="font-size:10px;color:var(--texto2);margin-top:2px"></div>
          </div>
          <input type="hidden" class="vr-img" value="${esc(v.imagen_url||'')}">
        </div>
      </div>
    </div>
  </div>`;
}

function toggleStockVariante(cb) {
  const row = cb.closest('.var-row');
  if (!row) return;
  const wrap = row.querySelector('.vr-stock-wrap');
  if (!wrap) return;
  wrap.style.display = cb.checked ? '' : 'none';
}

async function subirImagenVariante(input) {
  const row = input.closest('.var-row');
  const status = row.querySelector('.vr-img-status');
  const preview = row.querySelector('.vr-img-preview');
  const hidden = row.querySelector('.vr-img');
  if (!input.files?.length) return;
  const file = input.files[0];
  if (file.size > 10 * 1024 * 1024) {
    status.textContent = '⚠️ Archivo muy grande (>10MB)';
    status.style.color = 'var(--rojo)';
    input.value = '';
    return;
  }
  status.textContent = 'Subiendo...';
  status.style.color = 'var(--texto2)';
  try {
    const fd = new FormData();
    fd.append('imagen', file);
    const r = await fetch(API + '/productos/subir-imagen', {method:'POST', body:fd, credentials:'include'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    if (!d.url) throw new Error('Sin URL en respuesta');
    hidden.value = d.url;
    preview.innerHTML = `<img src="${d.url}" style="width:100%;height:100%;object-fit:cover">`;
    status.textContent = '✓ Subida';
    status.style.color = 'var(--verde)';
  } catch(e) {
    status.textContent = '❌ Error: ' + (e?.message || e);
    status.style.color = 'var(--rojo)';
    input.value = '';
  }
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

function onFraccionToggle() {
  const checked = document.getElementById('pf-fraccion').checked;
  const warn = document.getElementById('pf-fraccion-warn');
  if (warn) warn.style.display = checked ? '' : 'none';
  // Cambiar label del stock dinámicamente
  const stockLabel = document.getElementById('pf-stock-label');
  if (stockLabel) stockLabel.textContent = checked ? 'Stock (gramos)' : 'Unidades en stock';
  // Si se activa fracción, automáticamente desmarcar "Mostrar en catálogo" porque no aplica
  if (checked) {
    const web = document.getElementById('pf-web');
    if (web && web.checked) web.checked = false;
  }
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

async function eliminarProducto(id, nombre) {
  if (!confirm(`¿Eliminar el producto "${nombre}"?\nSe desactivará y dejará de aparecer en el catálogo.`)) return;
  const clave = prompt('Ingresa la clave de administrador para confirmar:');
  if (!clave) return;
  try {
    const v = await fetch(API + '/pos/verificar-clave-admin', {
      method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
      body: JSON.stringify({clave})
    });
    if (!v.ok) { alert('Clave incorrecta'); return; }
    const r = await fetch(API + '/productos/' + id, {method:'DELETE', credentials:'include'});
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Error'); return; }
    showToast('Producto eliminado ✓');
    _lastProdHash = '';
    loadProductos();
  } catch(e) { alert('Error de conexión'); }
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

async function subirFotosExtra() {
  const files = document.getElementById('pf-extras-file').files;
  if (!files.length) return;
  const status = document.getElementById('pf-extras-status');
  const extras = JSON.parse(document.getElementById('pf-extras').value || '[]');
  for (let i = 0; i < files.length; i++) {
    status.textContent = `Subiendo ${i+1} de ${files.length}...`;
    const fd = new FormData();
    fd.append('imagen', files[i]);
    try {
      const r = await fetch(API + '/productos/subir-imagen', {method:'POST', body:fd, credentials:'include'});
      const data = await r.json();
      if (data.url) extras.push(data.url);
    } catch(e) { status.textContent = `Error en foto ${i+1}`; return; }
  }
  document.getElementById('pf-extras').value = JSON.stringify(extras);
  renderExtrasPreview(extras);
  status.textContent = `${files.length} foto(s) subida(s) ✓`;
  document.getElementById('pf-extras-file').value = '';
}

function quitarFotoExtra(idx) {
  const extras = JSON.parse(document.getElementById('pf-extras').value || '[]');
  extras.splice(idx, 1);
  document.getElementById('pf-extras').value = JSON.stringify(extras);
  renderExtrasPreview(extras);
}

function renderExtrasPreview(extras) {
  document.getElementById('pf-extras-preview').innerHTML = extras.map((url, i) => `
    <div style="position:relative;width:80px;height:80px;border-radius:8px;overflow:hidden;background:var(--borde)">
      <img src="${esc(url)}" style="width:100%;height:100%;object-fit:cover">
      <button onclick="quitarFotoExtra(${i})" style="position:absolute;top:2px;right:2px;background:rgba(0,0,0,.6);color:#fff;border:none;border-radius:50%;width:20px;height:20px;font-size:12px;cursor:pointer;line-height:20px;padding:0">&times;</button>
    </div>
  `).join('');
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
  const btnSave = document.getElementById('btn-guardar-prod');
  if (btnSave?.disabled) return; // anti double-click
  if (btnSave) { btnSave.disabled = true; btnSave.textContent = 'Guardando...'; }
  try {
  const body = {
    nombre: document.getElementById('pf-nombre').value.trim(),
    descripcion: document.getElementById('pf-desc').value.trim() || null,
    codigo: document.getElementById('pf-sku').value.trim() || null,
    categoria: document.getElementById('pf-cat').value.trim(),
    precio: Math.round(parseFloat(document.getElementById('pf-precio').value || 0) * 100),
    precio_descuento: document.getElementById('pf-precio-desc').value ? Math.round(parseFloat(document.getElementById('pf-precio-desc').value) * 100) : null,
    imagen_url: document.getElementById('pf-img').value.trim() || null,
    activo: true,
    visible_catalogo: document.getElementById('pf-web').checked,
    stock_activo: document.getElementById('pf-stock-activo').checked,
    stock: parseInt(document.getElementById('pf-stock')?.value || 0),
    costo_unitario: document.getElementById('pf-costo')?.value ? parseFloat(document.getElementById('pf-costo').value) : null,
    medida_alto: document.getElementById('pf-alto')?.value ? parseFloat(document.getElementById('pf-alto').value) : null,
    medida_ancho: document.getElementById('pf-ancho')?.value ? parseFloat(document.getElementById('pf-ancho').value) : null,
    destacado: document.getElementById('pf-destacado').checked,
    vender_por_fraccion: document.getElementById('pf-fraccion')?.checked || false,
    imagenes_extra: document.getElementById('pf-extras').value || null,
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
  } catch(e) {
    alert('Error al guardar: ' + (e?.message || e));
    if (btnSave) { btnSave.disabled = false; btnSave.textContent = 'Guardar producto'; }
  }
}

async function saveAllVariantes(prodId) {
  // Collect all variante rows from DOM
  const rows = document.querySelectorAll('.var-row');
  // Validar: ningún tipo+nombre duplicado. Resaltar las filas conflictivas.
  const seenRows = new Map(); // key → primera row
  const dupRows = [];
  for (const row of rows) {
    row.style.outline = ''; // limpiar resaltado previo
    const tipo = row.dataset.tipo;
    const nombre = row.querySelector('.vr-nombre')?.value?.trim();
    if (!nombre) continue;
    const key = (tipo||'') + '|' + nombre.toLowerCase();
    if (seenRows.has(key)) {
      dupRows.push(seenRows.get(key));
      dupRows.push(row);
    } else {
      seenRows.set(key, row);
    }
  }
  if (dupRows.length > 0) {
    dupRows.forEach(r => { r.style.outline = '2px solid var(--rojo)'; r.style.outlineOffset = '2px'; });
    dupRows[0].scrollIntoView({behavior:'smooth', block:'center'});
    const nombre = dupRows[0].querySelector('.vr-nombre')?.value?.trim();
    const tipo = dupRows[0].dataset.tipo;
    throw new Error(`Variante duplicada: "${nombre}" (${tipo}). Hay ${dupRows.length} filas con el mismo nombre marcadas en rojo. Borra las de más con la ❌ y vuelve a guardar.`);
  }
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
    // La imagen ya se subió al seleccionar el archivo (subirImagenVariante);
    // .vr-img (hidden) ya tiene la URL final.
    if (varId && varId !== '') {
      await fetch(API + '/api/admin/variantes/' + varId, {method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(data)});
      existingIds.add(parseInt(varId));
    } else {
      const cr = await fetch(API + '/api/admin/variantes/' + prodId, {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(data)});
      try {
        const created = await cr.json();
        if (created?.id) {
          row.dataset.varId = created.id; // marca la fila para que un re-save no duplique
          existingIds.add(created.id);
        }
      } catch(e) {}
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

async function abrirHistorialStock(catFiltro) {
  const url = catFiltro
    ? API + '/api/admin/stock-historial?categoria=' + encodeURIComponent(catFiltro)
    : API + '/api/admin/stock-historial';
  try {
    const r = await fetch(url, {credentials:'include'});
    if (!r.ok) { alert('Error al cargar historial'); return; }
    const data = await r.json();
    // Extract unique categories for filter
    const cats = [...new Set(data.map(d => d.categoria).filter(Boolean))].sort();
    let html = '<div style="margin-bottom:12px"><select id="stock-hist-cat" onchange="abrirHistorialStock(this.value||undefined)" style="padding:6px 10px;border:1px solid #ccc;border-radius:8px">';
    html += '<option value="">Todas las categorías</option>';
    cats.forEach(c => {
      html += `<option value="${c}" ${c===catFiltro?'selected':''}>${c}</option>`;
    });
    html += '</select></div>';
    if (data.length === 0) {
      html += '<p style="color:#888">No hay productos con stock activo.</p>';
    } else {
      let totalActual = 0, totalVendidos = 0, totalInicial = 0;
      html += '<div style="overflow-x:auto"><table class="data-table" style="width:100%"><thead><tr>';
      html += '<th>Producto</th><th>Categoría</th><th style="text-align:right">Stock actual</th><th style="text-align:right">Vendidos</th><th style="text-align:right">Stock inicial est.</th>';
      html += '</tr></thead><tbody>';
      data.forEach(p => {
        totalActual += p.stock_actual;
        totalVendidos += p.vendidos;
        totalInicial += p.stock_inicial_estimado;
        const img = p.imagen_url ? `<img src="${p.imagen_url}" style="width:32px;height:32px;object-fit:cover;border-radius:4px;vertical-align:middle;margin-right:6px">` : '';
        html += `<tr>`;
        html += `<td>${img}${p.nombre}</td>`;
        html += `<td>${p.categoria || '—'}</td>`;
        html += `<td style="text-align:right;font-weight:600">${p.stock_actual}</td>`;
        html += `<td style="text-align:right;color:#2d5a3d;font-weight:600">${p.vendidos}</td>`;
        html += `<td style="text-align:right;color:#888">${p.stock_inicial_estimado}</td>`;
        html += `</tr>`;
      });
      html += `<tr style="border-top:2px solid #193a2c;font-weight:700">`;
      html += `<td>Total (${data.length} productos)</td><td></td>`;
      html += `<td style="text-align:right">${totalActual}</td>`;
      html += `<td style="text-align:right;color:#2d5a3d">${totalVendidos}</td>`;
      html += `<td style="text-align:right;color:#888">${totalInicial}</td>`;
      html += `</tr></tbody></table></div>`;
    }
    document.getElementById('modal-stock-body').innerHTML = html;
    document.getElementById('modal-stock-historial').classList.add('active');
  } catch(e) { alert('Error: ' + e.message); }
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

// ══════ CLAUDIA + TEMPORADA ══════
async function loadClaudia() {
  try {
    // Load config
    const r = await fetch(API + '/configuracion/', {credentials:'include'});
    const data = await r.json();
    const cfg = {};
    data.forEach(c => cfg[c.clave] = c.valor);

    // Bot controls
    document.getElementById('claudia-toggle').checked = cfg.claudia_activa === 'true';
    document.getElementById('claudia-abierto').checked = (cfg.claudia_abierto || 'true') === 'true';
    document.getElementById('claudia-msg').value = cfg.claudia_mensaje_bienvenida || '';
    const msgAlta = document.getElementById('claudia-msg-alta');
    if (msgAlta) msgAlta.value = cfg.claudia_mensaje_bienvenida_alta || '';

    // Temporada mode
    const modo = cfg.temporada_modo || 'regular';
    const isAlta = modo === 'alta';
    document.getElementById('temp-toggle-master').checked = isAlta;
    actualizarModoUI(isAlta);

    // Show/hide temporada catalog button
    const btnTemp = document.getElementById('btn-catalogo-temporada');
    if (btnTemp) btnTemp.style.display = isAlta ? '' : 'none';

    // Alta config fields
    document.getElementById('temp-nombre').value = cfg.temporada_nombre || '';
    document.getElementById('temp-fecha').value = cfg.temporada_fecha_fuerte || '';
    document.getElementById('temp-dias').value = cfg.temporada_dias_restriccion || '2';
    document.getElementById('temp-funerales').checked = (cfg.temporada_acepta_funerales || 'true') === 'true';
    document.getElementById('temp-horario-apertura').value = cfg.temporada_horario_apertura || '';
    document.getElementById('temp-horario-cierre').value = cfg.temporada_horario_cierre || '';



    // Load categories for dropdown
    await cargarCategoriasTemporada(cfg.temporada_categoria || '');
  } catch(e) { console.error('loadClaudia error:', e); }

  // Load chats
  loadClaudiaChats();
}

async function cargarCategoriasTemporada(selectedCat) {
  try {
    const r = await fetch(API + '/api/admin/categorias', {credentials:'include'});
    const cats = await r.json();
    const sel = document.getElementById('temp-categoria');
    // Keep first option (placeholder)
    sel.innerHTML = '<option value="">— Seleccionar categoría —</option>';
    cats.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.nombre;
      opt.textContent = `${c.nombre} (${c.productos_activos} productos)`;
      if (c.nombre === selectedCat) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch(e) { console.error(e); }
}

async function toggleTemporadaMaster(checked) {
  actualizarModoUI(checked);
  await Promise.all([
    toggleConfig('temporada_modo', checked ? 'alta' : 'regular'),
    toggleConfig('claudia_temporada_alta', String(checked)),
  ]);
  // Show/hide temporada catalog button
  const btnTemp = document.getElementById('btn-catalogo-temporada');
  if (btnTemp) btnTemp.style.display = checked ? '' : 'none';
}

function actualizarModoUI(isAlta) {
  const badge = document.getElementById('temporada-badge');
  const altaConfig = document.getElementById('temporada-alta-config');
  const zonasNote = document.getElementById('zonas-temporada-note');

  badge.textContent = isAlta ? 'TEMPORADA ALTA' : 'TEMPORADA REGULAR';
  badge.style.background = isAlta ? 'rgba(212,168,67,0.15)' : 'rgba(45,90,61,0.1)';
  badge.style.color = isAlta ? 'var(--dorado)' : 'var(--verde)';

  altaConfig.style.display = isAlta ? '' : 'none';
  if (zonasNote) zonasNote.style.display = isAlta ? '' : 'none';
}

async function guardarTemporada() {
  const nombre = document.getElementById('temp-nombre').value;
  const categoria = document.getElementById('temp-categoria').value;
  const fecha = document.getElementById('temp-fecha').value;
  const dias = document.getElementById('temp-dias').value;
  const funerales = document.getElementById('temp-funerales').checked;
  const hApertura = document.getElementById('temp-horario-apertura').value;
  const hCierre = document.getElementById('temp-horario-cierre').value;

  const saves = [
    toggleConfig('temporada_nombre', nombre),
    toggleConfig('temporada_categoria', categoria),
    toggleConfig('temporada_fecha_fuerte', fecha),
    toggleConfig('temporada_dias_restriccion', dias),
    toggleConfig('temporada_acepta_funerales', String(funerales)),
    toggleConfig('temporada_horario_apertura', hApertura),
    toggleConfig('temporada_horario_cierre', hCierre),
  ];
  await Promise.all(saves);
}



// ═══ FUNERARIAS (CRUD admin) ═══
async function loadFunerariasAdmin() {
  try {
    const r = await fetch(API+'/funerarias/', {credentials:'include'});
    if (!r.ok) return;
    const funs = await r.json();
    const tbody = document.getElementById('funerarias-tbody');
    if (!tbody) return;
    if (!funs.length) { tbody.innerHTML = '<tr><td colspan="5" style="padding:12px;text-align:center">Sin funerarias</td></tr>'; return; }
    tbody.innerHTML = funs.map(f => `<tr style="border-bottom:1px solid var(--borde)">
      <td style="padding:8px 4px;font-weight:600">${esc(f.nombre)}</td>
      <td style="padding:8px 4px;color:var(--texto2);font-size:12px">${esc(f.direccion||'—')}</td>
      <td style="padding:8px 4px"><span style="background:${zonaColor(f.zona)};padding:2px 8px;border-radius:4px;color:#fff;font-size:11px">${esc(f.zona||'')}</span></td>
      <td style="padding:8px 4px;font-weight:600">$${(f.costo_envio||0)/100}</td>
      <td style="padding:8px 4px">
        <button class="btn-sm" onclick='editarFuneraria(${JSON.stringify(f).replace(/'/g,"&#39;")})'>Editar</button>
        <button class="btn-sm" style="background:#f5e0e0;color:#c0392b" onclick="eliminarFuneraria(${f.id},'${esc(f.nombre)}')">Eliminar</button>
      </td>
    </tr>`).join('');
  } catch(e) { console.error('loadFunerariasAdmin:', e); }
}

function zonaColor(zona) {
  const z = (zona||'').toLowerCase();
  if (z.includes('morada')) return '#8B5CF6';
  if (z.includes('azul')) return '#3B82F6';
  if (z.includes('verde')) return '#10B981';
  return '#6B7280';
}

function abrirNuevaFuneraria() {
  abrirModalFuneraria(null);
}

function editarFuneraria(f) {
  abrirModalFuneraria(f);
}

function abrirModalFuneraria(f) {
  const isNew = !f;
  const div = document.createElement('div');
  div.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;padding:20px';
  div.innerHTML = `
    <div style="background:#fff;border-radius:12px;padding:20px;max-width:500px;width:100%;box-shadow:0 8px 30px rgba(0,0,0,.15)">
      <h3 style="margin:0 0 14px;font-size:16px;color:#193a2c">${isNew ? 'Nueva funeraria' : 'Editar: '+esc(f.nombre)}</h3>
      <div class="field" style="margin-bottom:10px">
        <label>Nombre *</label>
        <input id="fun-mod-nombre" value="${isNew?'':esc(f.nombre)}" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px">
      </div>
      <div class="field" style="margin-bottom:10px">
        <label>Dirección</label>
        <input id="fun-mod-direccion" value="${isNew||!f.direccion?'':esc(f.direccion)}" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px">
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px">
        <div class="field">
          <label>Zona</label>
          <input id="fun-mod-zona" value="${isNew?'Morada':esc(f.zona||'')}" placeholder="Ej: Morada, PONIENTE 1" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px">
        </div>
        <div class="field">
          <label>Costo envío (pesos)</label>
          <input id="fun-mod-costo" type="number" value="${isNew?99:(f.costo_envio||0)/100}" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px">
        </div>
      </div>
      <div style="display:flex;gap:8px">
        <button onclick="this.closest('div[style*=position]').remove()" style="flex:1;padding:10px;border:1px solid #ddd;border-radius:8px;background:#fff;cursor:pointer">Cancelar</button>
        <button onclick="guardarFuneraria(${isNew?'null':f.id},this)" style="flex:1;padding:10px;border:none;border-radius:8px;background:#193a2c;color:#fff;cursor:pointer;font-weight:600">Guardar</button>
      </div>
    </div>
  `;
  document.body.appendChild(div);
}

async function guardarFuneraria(id, btn) {
  const nombre = document.getElementById('fun-mod-nombre').value.trim();
  const direccion = document.getElementById('fun-mod-direccion').value.trim();
  const zona = document.getElementById('fun-mod-zona').value.trim();
  const costo_pesos = parseInt(document.getElementById('fun-mod-costo').value, 10);
  if (!nombre) { alert('Nombre obligatorio'); return; }
  if (isNaN(costo_pesos) || costo_pesos < 0) { alert('Costo inválido'); return; }
  btn.disabled = true; btn.textContent = 'Guardando...';
  const body = JSON.stringify({nombre, direccion: direccion||null, zona, costo_envio: costo_pesos*100});
  const url = id ? API+`/funerarias/${id}` : API+'/funerarias/';
  const method = id ? 'PUT' : 'POST';
  try {
    const r = await fetch(url, {method, headers:{'Content-Type':'application/json'}, credentials:'include', body});
    if (!r.ok) { alert('Error al guardar'); btn.disabled=false; btn.textContent='Guardar'; return; }
    btn.closest('div[style*="position"]').remove();
    loadFunerariasAdmin();
  } catch(e) { alert('Error: '+e.message); btn.disabled=false; btn.textContent='Guardar'; }
}

async function eliminarFuneraria(id, nombre) {
  if (!confirm(`¿Eliminar "${nombre}"?\nNo se puede deshacer.`)) return;
  const r = await fetch(API+`/funerarias/${id}`, {method:'DELETE', credentials:'include'});
  if (!r.ok) { alert('Error al eliminar'); return; }
  loadFunerariasAdmin();
}


// ═══ TURNOS DE ENTREGA ═══
async function loadTurnos() {
  try {
    const r = await fetch(API+'/catalogo/turnos-activos');
    if (!r.ok) return;
    const t = await r.json();
    const m = document.getElementById('turno-manana-toggle');
    const tar = document.getElementById('turno-tarde-toggle');
    const n = document.getElementById('turno-noche-toggle');
    const rec = document.getElementById('turno-recoger-toggle');
    if (m) m.checked = t.manana;
    if (tar) tar.checked = t.tarde;
    if (n) n.checked = t.noche;
    if (rec) rec.checked = t.recoger;
  } catch(e) { console.error('loadTurnos:', e); }
}

async function guardarTurnos() {
  const m = document.getElementById('turno-manana-toggle').checked;
  const tar = document.getElementById('turno-tarde-toggle').checked;
  const n = document.getElementById('turno-noche-toggle').checked;
  const rec = document.getElementById('turno-recoger-toggle').checked;
  await Promise.all([
    toggleConfig('turno_manana_activo', String(m)),
    toggleConfig('turno_tarde_activo', String(tar)),
    toggleConfig('turno_noche_activo', String(n)),
    toggleConfig('turno_recoger_activo', String(rec)),
  ]);
}


// ═══ ZONAS DE ENVÍO ═══
async function loadZonasAdmin() {
  try {
    const r = await fetch(API+'/api/admin/zonas-envio',{credentials:'include'});
    if (!r.ok) return;
    const zonas = await r.json();
    const tbody = document.getElementById('zonas-tbody');
    if (!tbody) return;
    if (!zonas.length) { tbody.innerHTML = '<tr><td colspan="5" style="padding:12px;text-align:center">Sin zonas</td></tr>'; return; }
    tbody.innerHTML = zonas.map(z => {
      const overrideado = z.tarifa_pesos !== z.tarifa_base_pesos;
      const tarifaCelda = overrideado
        ? `<span style="text-decoration:line-through;color:var(--texto2)">$${z.tarifa_base_pesos}</span> <strong style="color:var(--dorado)">$${z.tarifa_pesos}</strong>`
        : `$${z.tarifa_pesos}`;
      const inactivaTag = z.activa ? '' : ' <span style="background:var(--rojo);color:#fff;padding:1px 6px;border-radius:4px;font-size:10px">INACTIVA</span>';
      return `<tr style="border-bottom:1px solid var(--borde)">
        <td style="padding:8px 4px;font-weight:600">${esc(z.nombre)}${inactivaTag}</td>
        <td style="padding:8px 4px;color:var(--texto2)">$${z.tarifa_base_pesos}</td>
        <td style="padding:8px 4px">${tarifaCelda}</td>
        <td style="padding:8px 4px"><input type="checkbox" ${z.activa?'checked':''} onchange="toggleZonaActiva('${esc(z.nombre)}', this.checked, ${z.tarifa_pesos})"></td>
        <td style="padding:8px 4px;display:flex;gap:6px">
          <button class="btn-sm" onclick="editarTarifaZona('${esc(z.nombre)}', ${z.tarifa_pesos})">Editar tarifa</button>
          ${overrideado ? `<button class="btn-sm" style="background:#f5e0e0;color:#c0392b" onclick="resetearZona('${esc(z.nombre)}')">Resetear</button>` : ''}
        </td>
      </tr>`;
    }).join('');
  } catch(e) { console.error('loadZonasAdmin:', e); }
}

async function editarTarifaZona(nombre, tarifaActual) {
  const nuevo = prompt(`Nueva tarifa para "${nombre}" (en pesos):\nActual: $${tarifaActual}`, tarifaActual);
  if (nuevo === null) return;
  const valor = parseInt(nuevo, 10);
  if (isNaN(valor) || valor < 0) { alert('Tarifa inválida'); return; }
  await fetch(API+`/api/admin/zonas-envio/${encodeURIComponent(nombre)}`, {
    method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({tarifa_pesos: valor, activa: true}),
  });
  loadZonasAdmin();
}

async function toggleZonaActiva(nombre, activa, tarifaActual) {
  await fetch(API+`/api/admin/zonas-envio/${encodeURIComponent(nombre)}`, {
    method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({tarifa_pesos: tarifaActual, activa}),
  });
  loadZonasAdmin();
}

async function resetearZona(nombre) {
  if (!confirm(`¿Resetear "${nombre}" a tarifa base del GeoJSON?`)) return;
  await fetch(API+`/api/admin/zonas-envio/${encodeURIComponent(nombre)}`, {
    method:'DELETE', credentials:'include',
  });
  loadZonasAdmin();
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

// ══════ ENVIAR CATÁLOGO ══════
let _catalogoTipo = 'general';

function selCatalogoTipo(tipo, btn) {
  _catalogoTipo = tipo;
  document.querySelectorAll('.catalogo-tipo-btn').forEach(b => {
    b.classList.remove('active');
    b.style.borderColor = 'var(--borde)';
    b.style.background = '';
  });
  btn.classList.add('active');
  btn.style.borderColor = 'var(--verde)';
  btn.style.background = 'rgba(45,90,61,0.08)';
}

async function enviarCatalogo() {
  const pais = document.getElementById('catalogo-pais').value;
  const tel = document.getElementById('catalogo-telefono').value.trim().replace(/\D/g, '');
  const result = document.getElementById('catalogo-result');
  if (!tel || tel.length < 7) { result.textContent = 'Ingresa un telefono valido'; result.style.color = 'var(--rojo)'; return; }

  // Mexico: agregar "1" después del código de país (521XXXXXXXXXX)
  const telefono = pais === '52' ? '521' + tel : pais + tel;
  const baseUrl = 'https://www.florerialucy.com/catalogo/';
  let mensaje = '';
  if (_catalogoTipo === 'general') {
    mensaje = `Hola! 🌸 Aqui te comparto nuestro catalogo de Floreria Lucy: ${baseUrl}`;
  } else if (_catalogoTipo === 'funeral') {
    mensaje = `🕊️ Aqui te comparto nuestro catalogo de arreglos funerales: ${baseUrl}?seccion=funeral`;
  } else if (_catalogoTipo === 'temporada') {
    mensaje = `Hola! 🌸 Aqui te comparto nuestro catalogo de temporada: ${baseUrl}?seccion=temporada`;
  }

  const btn = document.getElementById('btn-enviar-catalogo');
  btn.disabled = true; btn.textContent = 'Enviando...';
  result.textContent = '';

  try {
    const r = await fetch(API + '/api/claudia/enviar-catalogo', {
      method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
      body: JSON.stringify({telefono, mensaje})
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      result.textContent = err.detail || 'Error al enviar';
      result.style.color = 'var(--rojo)';
      return;
    }
    result.textContent = 'Enviado ✓';
    result.style.color = 'var(--verde)';
    document.getElementById('catalogo-telefono').value = '';
    showToast('Catalogo enviado por WhatsApp');
    // Refresh chats
    setTimeout(loadClaudiaChats, 2000);
  } catch(e) {
    result.textContent = 'Error de conexion';
    result.style.color = 'var(--rojo)';
  } finally {
    btn.disabled = false; btn.textContent = 'Enviar por Claudia';
  }
}

// ══════ CLAUDIA CHATS ══════
let _clChatsData = [];
let _clResponderTel = '';

async function loadClaudiaChats() {
  try {
    const r = await fetch(API + '/api/claudia/chats', {credentials:'include'});
    if (!r.ok) return;
    _clChatsData = await r.json();
    renderClaudiaChats();
    updateClaudiaBadge();
  } catch(e) { console.error('loadClaudiaChats:', e); }
}

function renderClaudiaChats() {
  const search = (document.getElementById('claudia-chat-search')?.value || '').toLowerCase();
  const now = Date.now();
  const h24 = 24 * 60 * 60 * 1000;

  const activos = [], espera = [], archivados = [];
  _clChatsData.forEach(c => {
    if (search && !c.telefono.includes(search)) return;
    const ts = c.timestamp ? new Date(c.timestamp).getTime() : 0;
    // Prioridad: campo BD archivado_humano > estado esperando > +24h auto-archivo
    if (c.archivado_humano === true) {
      archivados.push(c);
    } else if (c.estado === 'esperando_humano') {
      espera.push(c);
    } else if (now - ts > h24) {
      archivados.push(c);
    } else {
      activos.push(c);
    }
  });

  document.getElementById('cl-count-activos').textContent = activos.length ? `(${activos.length})` : '';
  document.getElementById('cl-count-espera').textContent = espera.length ? `(${espera.length})` : '';
  document.getElementById('cl-count-archivados').textContent = archivados.length ? `(${archivados.length})` : '';

  document.getElementById('cl-activos-list').innerHTML = activos.length ? activos.map(renderChatRow).join('') : '<div class="cl-empty">Sin chats activos</div>';
  document.getElementById('cl-espera-list').innerHTML = espera.length ? espera.map(renderChatRow).join('') : '<div class="cl-empty">Sin chats esperando</div>';
  document.getElementById('cl-archivados-list').innerHTML = archivados.length ? archivados.map(renderChatRow).join('') : '<div class="cl-empty">Sin chats archivados</div>';
}

function renderChatRow(c) {
  const esEspera = c.estado === 'esperando_humano';
  const dotClass = esEspera ? 'espera' : 'activo';
  const estadoClass = esEspera ? 'espera' : 'activo';
  const estadoLabel = esEspera ? 'Esperando humano' : 'Activo';
  const rolIcon = c.rol === 'user' ? '👤' : '🤖';
  const msg = esc(c.ultimo_mensaje || '');
  const time = c.timestamp ? fmtDateTime(c.timestamp) : '';
  const wait = esEspera && c.estado_desde ? `<div class="cl-chat-wait">⏱ ${tiempoEspera(c.estado_desde)}</div>` : '';

  const btnAccion = esEspera
    ? `<button class="btn-liberar" onclick="liberarChat('${c.telefono}')">Devolver a Claudia</button>`
    : `<button class="btn-intervenir" onclick="intervenirChat('${c.telefono}')">Intervenir</button>`;

  return `<div class="cl-chat-row">
    <div class="cl-chat-dot ${dotClass}"></div>
    <div class="cl-chat-info">
      <div class="cl-chat-tel">${esc(c.telefono)} <span class="cl-estado ${estadoClass}">${estadoLabel}</span></div>
      <div class="cl-chat-msg">${rolIcon} ${msg}</div>
      ${wait}
    </div>
    <div class="cl-chat-meta">
      <div class="cl-chat-time">${time}</div>
    </div>
    <div class="cl-chat-actions">
      <button class="btn-responder" onclick="abrirResponder('${c.telefono}')">Responder</button>
      ${btnAccion}
      <button onclick="toggleNotasClaudia('${c.telefono}',this)" title="Notas">📝</button>
    </div>
  </div>
  <div class="cl-notas-panel" id="notas-${c.telefono}"></div>`;
}

function fmtDateTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('es-MX', {day:'2-digit',month:'short',timeZone:'America/Chihuahua'}) + ' ' +
    d.toLocaleTimeString('es-MX', {hour:'2-digit',minute:'2-digit',timeZone:'America/Chihuahua'});
}

function tiempoEspera(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 60) return `hace ${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h < 24) return `hace ${h}h ${m}min`;
  return `hace ${Math.floor(h / 24)}d`;
}

function filtrarChatsClaudia() { renderClaudiaChats(); }

function claudiaSubTab(id, btn) {
  document.querySelectorAll('#claudia-sub-tabs .sub-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  ['cl-activos','cl-espera','cl-archivados'].forEach(t => {
    document.getElementById(t + '-content').style.display = t === id ? '' : 'none';
  });
}

async function intervenirChat(tel) {
  try {
    await fetch(API + '/api/claudia/bloquear', {
      method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
      body: JSON.stringify({telefono: tel})
    });
    showToast('Chat bloqueado — Claudia no responde');
    loadClaudiaChats();
  } catch(e) { console.error(e); }
}

async function liberarChat(tel) {
  try {
    await fetch(API + '/api/claudia/liberar', {
      method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
      body: JSON.stringify({telefono: tel})
    });
    showToast('Chat devuelto a Claudia');
    loadClaudiaChats();
  } catch(e) { console.error(e); }
}

// --- Responder modal ---
async function abrirResponder(tel) {
  _clResponderTel = tel;
  document.getElementById('modal-responder-title').textContent = 'Responder a ' + tel;
  document.getElementById('responder-input').value = '';
  document.getElementById('responder-historial').innerHTML = '<div style="text-align:center;color:var(--texto2);padding:20px">Cargando...</div>';
  document.getElementById('modal-responder').classList.add('active');

  try {
    const r = await fetch(API + '/api/claudia/historial/' + tel, {credentials:'include'});
    if (!r.ok) { document.getElementById('responder-historial').innerHTML = '<div class="cl-empty">Error al cargar historial</div>'; return; }
    const msgs = await r.json();
    renderHistorial(msgs);
  } catch(e) {
    document.getElementById('responder-historial').innerHTML = '<div class="cl-empty">Error de conexion</div>';
  }

  setTimeout(() => document.getElementById('responder-input').focus(), 100);
}

function renderHistorial(msgs) {
  const container = document.getElementById('responder-historial');
  if (!msgs.length) { container.innerHTML = '<div class="cl-empty">Sin mensajes</div>'; return; }
  container.innerHTML = msgs.map(m => {
    const time = m.timestamp ? fmtDateTime(m.timestamp) : '';
    return `<div class="cl-msg ${m.role}">
      <div>${esc(m.content)}</div>
      <div class="cl-msg-time">${time}</div>
    </div>`;
  }).join('');
  container.scrollTop = container.scrollHeight;
}

async function enviarMensajeHumano() {
  const input = document.getElementById('responder-input');
  const msg = input.value.trim();
  if (!msg || !_clResponderTel) return;

  const btn = document.getElementById('btn-enviar-humano');
  btn.disabled = true;
  btn.textContent = 'Enviando...';

  try {
    const r = await fetch(API + '/api/claudia/enviar-mensaje', {
      method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
      body: JSON.stringify({telefono: _clResponderTel, mensaje: msg})
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      showToast(err.detail || 'Error al enviar');
      return;
    }
    showToast('Mensaje enviado');
    input.value = '';
    // Refresh historial
    const r2 = await fetch(API + '/api/claudia/historial/' + _clResponderTel, {credentials:'include'});
    if (r2.ok) renderHistorial(await r2.json());
    // Refresh chat list
    loadClaudiaChats();
  } catch(e) {
    showToast('Error de conexion');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Enviar';
  }
}

// --- Notas ---
async function toggleNotasClaudia(tel, btn) {
  const panel = document.getElementById('notas-' + tel);
  if (!panel) return;
  if (panel.classList.contains('show')) {
    panel.classList.remove('show');
    return;
  }
  panel.innerHTML = '<div style="padding:8px;color:var(--texto2);font-size:12px">Cargando...</div>';
  panel.classList.add('show');

  try {
    const r = await fetch(API + '/api/claudia/notas/' + tel, {credentials:'include'});
    const notas = r.ok ? await r.json() : [];
    let html = notas.map(n => `<div class="cl-nota-item">
      <span class="cl-nota-texto">${esc(n.nota)}</span>
      <span class="cl-nota-time">${fmtDateTime(n.timestamp)}</span>
      <button class="cl-nota-del" onclick="eliminarNotaClaudia(${n.id},'${tel}')">&times;</button>
    </div>`).join('');
    html += `<div style="display:flex;gap:6px;margin-top:8px">
      <input type="text" id="nota-input-${tel}" placeholder="Nueva nota..." style="flex:1;padding:6px 10px;border:1px solid var(--borde);border-radius:6px;font-size:12px;font-family:inherit">
      <button class="btn-sm" onclick="guardarNotaClaudia('${tel}')">Guardar</button>
    </div>`;
    panel.innerHTML = html;
  } catch(e) {
    panel.innerHTML = '<div style="padding:8px;color:var(--rojo);font-size:12px">Error</div>';
  }
}

async function guardarNotaClaudia(tel) {
  const input = document.getElementById('nota-input-' + tel);
  const nota = input?.value.trim();
  if (!nota) return;
  try {
    await fetch(API + '/api/claudia/notas', {
      method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
      body: JSON.stringify({telefono: tel, nota})
    });
    toggleNotasClaudia(tel); // close
    setTimeout(() => toggleNotasClaudia(tel), 100); // reopen to refresh
  } catch(e) { console.error(e); }
}

async function eliminarNotaClaudia(id, tel) {
  try {
    await fetch(API + '/api/claudia/notas/' + id, {method:'DELETE', credentials:'include'});
    toggleNotasClaudia(tel);
    setTimeout(() => toggleNotasClaudia(tel), 100);
  } catch(e) { console.error(e); }
}

// Badge global (even when not on Claudia section)
function updateClaudiaBadge() {
  const esperando = _clChatsData.filter(c => c.estado === 'esperando_humano').length;
  const badge = document.getElementById('badge-claudia');
  if (badge) {
    if (esperando > 0) { badge.style.display = 'flex'; badge.textContent = esperando > 9 ? '9+' : esperando; }
    else badge.style.display = 'none';
  }
}

// Poll badge every 30s even outside Claudia section
setInterval(async () => {
  try {
    const r = await fetch(API + '/api/claudia/chats', {credentials:'include'});
    if (!r.ok) return;
    const chats = await r.json();
    const esperando = chats.filter(c => c.estado === 'esperando_humano').length;
    const badge = document.getElementById('badge-claudia');
    if (badge) {
      if (esperando > 0) { badge.style.display = 'flex'; badge.textContent = esperando > 9 ? '9+' : esperando; }
      else badge.style.display = 'none';
    }
  } catch(e) {}
}, 30000);

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


  el.innerHTML = `<div style="max-width:700px">
    <div class="toggle-row"><label>Catálogo web activo</label><input type="checkbox" ${webCfg.catalogo_activo==='true'?'checked':''} onchange="saveConfigField('catalogo_activo',String(this.checked))"></div>
    <div class="config-field" style="margin:12px 0"><label>Días mínimos de anticipación</label><input type="number" value="${esc(webCfg.catalogo_fecha_minima_dias||'1')}" min="0" style="width:80px" onchange="saveConfigField('catalogo_fecha_minima_dias',this.value)"></div>
    <h4 style="font-size:14px;color:var(--verde);margin:20px 0 12px;padding-top:16px;border-top:2px solid var(--borde)">Horarios de hora específica</h4>
    ${horariosHtml}

    <div style="margin-top:24px;padding-top:16px;border-top:2px solid var(--borde)">
      <div class="toggle-row"><label>Cerrar catálogo temporalmente</label><input type="checkbox" id="wh-cerrado" ${webCfg.catalogo_cerrado==='true'?'checked':''} onchange="saveConfigField('catalogo_cerrado', String(this.checked))"></div>
    </div>
  </div>`;
}

// toggleFechaEspecial and guardarFechaEspecial removed — unified in Temporada section

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
  if (p === 'anio') return {desde: hoy.substring(0,4)+'-01-01', hasta: hoy};
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
  if (id === 'fin-cuentas') loadCuentas();
}

let _finRawActivos = [];
let _finRawOtros = [];
let _finRawCancelados = [];

async function loadFinanzas() {
  const {desde, hasta} = getFinDates();
  try {
    const periodo = document.getElementById('fin-periodo').value;
    // 'anio' no es nativo del endpoint -> se manda como rango
    const periodoQS = (periodo === 'rango' || periodo === 'anio')
      ? 'rango&fecha_inicio=' + desde + '&fecha_fin=' + hasta
      : periodo;
    const r = await fetch(API + '/pos/pedidos-hoy?filtrar_por=pago_confirmado_at&periodo=' + periodoQS, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    finData.ingresos = data;
    const rows = data.finalizados || [];
    _finRawActivos = rows.filter(p => p.estado !== 'Cancelado' && p.estado !== 'cancelado');
    _finRawCancelados = rows.filter(p => p.estado === 'Cancelado' || p.estado === 'cancelado');
    // Load otros ingresos
    _finRawOtros = [];
    try {
      const or2 = await fetch(API+'/api/admin/otros-ingresos?desde='+desde+'&hasta='+hasta, {credentials:'include'});
      if (or2.ok) _finRawOtros = await or2.json();
    } catch(e) {}
    finData.otrosIngresos = _finRawOtros;
    // Populate payment methods filter
    const metodos = new Set();
    _finRawActivos.forEach(p => (p.forma_pago||'').split(', ').forEach(m => { m = m.trim(); if (m) metodos.add(m); }));
    const pagoSel = document.getElementById('fin-filter-pago');
    const currentVal = pagoSel.value;
    pagoSel.innerHTML = '<option value="">Todos los pagos</option>' + [...metodos].sort().map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('');
    pagoSel.value = currentVal;
    // Render
    renderFinanzasFiltered();
  } catch(e) { console.error(e); }
}

function getFinTipo(p) {
  if (p.tipo_especial === 'Funeral') return 'funeral';
  if (p.direccion_entrega) return 'domicilio';
  if (p.metodo_entrega === 'recoger' || p.tipo_especial === 'Recoger') return 'recoger';
  return 'mostrador';
}

function applyFinFilters() { renderFinanzasFiltered(); }
function resetFinFilters() {
  document.getElementById('fin-filter-canal').value = '';
  document.getElementById('fin-filter-pago').value = '';
  document.getElementById('fin-filter-tipo').value = '';
  renderFinanzasFiltered();
}

function renderFinanzasFiltered() {
  const fCanal = document.getElementById('fin-filter-canal')?.value || '';
  const fPago = document.getElementById('fin-filter-pago')?.value || '';
  const fTipo = document.getElementById('fin-filter-tipo')?.value || '';

  let filtered = _finRawActivos;
  if (fCanal) filtered = filtered.filter(p => p.canal === fCanal);
  if (fPago) filtered = filtered.filter(p => (p.forma_pago||'').includes(fPago));
  if (fTipo) filtered = filtered.filter(p => getFinTipo(p) === fTipo);

  const otrosRows = _finRawOtros;
  const otrosTotal = otrosRows.reduce((s,o) => s + (o.monto||0), 0);
  const totalVentas = filtered.reduce((s,p) => s + (p.total||0), 0);
  const totalIngresos = totalVentas + (fCanal || fPago || fTipo ? 0 : otrosTotal);
  const totalTrans = filtered.length + (fCanal || fPago || fTipo ? 0 : otrosRows.length);
  const ticket = totalTrans ? Math.round(totalIngresos / totalTrans) : 0;
  finData.totalIngresos = totalIngresos;

  // Desglose de pago — usar pagos_detalle (monto exacto por método) cuando existe,
  // fallback a forma_pago dividiendo total entre N métodos para evitar doble conteo
  const desglosePago = {};
  filtered.forEach(p => {
    let usado = false;
    if (p.pagos_detalle) {
      try {
        const pags = JSON.parse(p.pagos_detalle);
        if (Array.isArray(pags) && pags.length) {
          pags.forEach(d => {
            const m = (d.nombre||'').trim();
            const monto = d.monto || 0;
            if (m && monto) desglosePago[m] = (desglosePago[m]||0) + monto;
          });
          usado = true;
        }
      } catch(_) {}
    }
    if (!usado) {
      // Fallback: dividir total entre los métodos listados
      const metodos = (p.forma_pago||'').split(', ').map(m => m.trim()).filter(Boolean);
      if (metodos.length === 0) return;
      const porMetodo = Math.round((p.total||0) / metodos.length);
      metodos.forEach(m => { desglosePago[m] = (desglosePago[m]||0) + porMetodo; });
    }
  });

  // KPIs
  let kpis = `<div class="kpi-card"><div class="kpi-label">Total ingresos</div><div class="kpi-value">${fmt$(totalIngresos)}</div>${!fCanal && !fPago && !fTipo && otrosTotal ? '<div class="kpi-sub">Incluye '+fmt$(otrosTotal)+' de otros ingresos</div>' : ''}${fCanal || fPago || fTipo ? '<div class="kpi-sub" style="color:var(--dorado)">Filtro activo</div>' : ''}</div>
    <div class="kpi-card"><div class="kpi-label">Transacciones</div><div class="kpi-value">${totalTrans}</div></div>
    <div class="kpi-card"><div class="kpi-label">Ticket promedio</div><div class="kpi-value">${fmt$(ticket)}</div></div>`;
  for (const [m,v] of Object.entries(desglosePago)) kpis += `<div class="kpi-card"><div class="kpi-label">${esc(m)}</div><div class="kpi-value">${fmt$(v)}</div></div>`;
  const canales = {};
  filtered.forEach(p => { canales[p.canal] = (canales[p.canal]||0) + (p.total||0); });
  if (!fCanal && !fPago && !fTipo && otrosTotal) canales['Otros'] = otrosTotal;
  for (const [c,v] of Object.entries(canales)) kpis += `<div class="kpi-card"><div class="kpi-label">${esc(c)}</div><div class="kpi-value">${fmt$(v)}</div></div>`;
  document.getElementById('fin-kpis').innerHTML = kpis;

  // Table
  const tbody = document.getElementById('fin-ing-tbody');
  let allRows = filtered.slice(0,200).map(p => `<tr><td>${fmtDate(p.pago_confirmado_at || p.fecha_pedido || p.fecha_entrega)}</td><td style="font-weight:600;color:var(--verde)">${esc(p.folio)}</td><td>${esc(p.cliente_nombre||'Mostrador')}</td><td>${esc(p.canal)}</td><td>${esc(p.forma_pago||'—')}</td><td style="font-weight:600">${fmt$(p.total)}</td></tr>`);
  if (!fCanal && !fPago && !fTipo) {
    otrosRows.forEach(o => {
      allRows.push(`<tr><td>${fmtDate(o.fecha)}</td><td><span style="background:var(--dorado);color:var(--verde);padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700">OTRO</span></td><td>${esc(o.concepto)}</td><td>—</td><td>${esc(o.metodo_pago||'—')}</td><td style="font-weight:600">${fmt$(o.monto)}</td></tr>`);
    });
  }
  tbody.innerHTML = allRows.join('') || '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--texto2)">Sin ingresos</td></tr>';

  // Cancelados (solo sin filtros activos)
  const cancelContainer = document.getElementById('fin-cancelados');
  if (cancelContainer) {
    if (!fCanal && !fPago && !fTipo && _finRawCancelados.length > 0) {
      const totalCancel = _finRawCancelados.reduce((s,p) => s + (p.total||0), 0);
      cancelContainer.innerHTML = `
        <div style="margin-top:16px;border:1px solid #fca5a5;border-radius:10px;overflow:hidden">
          <button onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'':'none';this.querySelector('span').textContent=this.nextElementSibling.style.display==='none'?'▶':'▼'"
            style="width:100%;padding:10px 14px;background:#fef2f2;border:none;cursor:pointer;display:flex;align-items:center;justify-content:space-between;font-family:inherit;font-size:13px;font-weight:600;color:#991b1b">
            <div>Cancelados (${_finRawCancelados.length}) — ${fmt$(totalCancel)} no cobrados</div>
            <span>▶</span>
          </button>
          <div style="display:none">
            <table class="data-table" style="font-size:12px"><tbody>
              ${_finRawCancelados.map(p => `<tr style="background:#fef2f2">
                <td>${fmtDate(p.pago_confirmado_at || p.fecha_pedido || p.fecha_entrega)}</td>
                <td style="color:#991b1b;font-weight:600">${esc(p.folio)}</td>
                <td>${esc(p.cliente_nombre||'Mostrador')}</td>
                <td>${esc(p.canal)}</td>
                <td>${esc(p.forma_pago||'—')}</td>
                <td style="text-decoration:line-through;color:#999">${fmt$(p.total)}</td>
              </tr>`).join('')}
            </tbody></table>
          </div>
        </div>`;
    } else {
      cancelContainer.innerHTML = '';
    }
  }
}

async function abrirModalOtroIngreso() {
  await loadMetodosPago();
  const hoy = new Date().toISOString().split('T')[0];
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4 style="margin-bottom:12px">Registrar otro ingreso</h4>
    <div class="field"><label>Fecha *</label><input type="date" id="oi-fecha" value="${hoy}"></div>
    <div class="field"><label>Concepto *</label><input id="oi-concepto" placeholder="Ej: Clase de arreglos florales"></div>
    <div class="field"><label>Monto * (pesos)</label><input type="number" id="oi-monto" step="0.01"></div>
    <div class="field"><label>Método de pago</label><select id="oi-mp"><option value="">Selecciona...</option>${mpOptions()}</select><div style="font-size:11px;color:var(--texto2);margin-top:4px">💡 Si seleccionas "Caja" o "Caja chica", el ingreso se suma automáticamente al saldo de esa cuenta.</div></div>
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
  await loadCuentasFinList();
  const {desde, hasta} = getFinDates();
  try {
    const r = await fetch(API + '/api/admin/egresos?desde='+desde+'&hasta='+hasta, {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    finData.egresos = data;
    renderEgresos();
  } catch(e) {}
}

function renderEgresos() {
  const all = finData.egresos || [];
  const q = (document.getElementById('fin-egr-search')?.value || '').trim().toLowerCase();
  const data = q ? all.filter(e =>
    (e.concepto||'').toLowerCase().includes(q) ||
    (e.proveedor||'').toLowerCase().includes(q) ||
    (e.categoria||'').toLowerCase().includes(q) ||
    (e.notas||'').toLowerCase().includes(q)
  ) : all;
  {
    // KPIs egresos
    const totalEgr = data.reduce((s,e)=>s+(e.monto||0), 0);
    const numEgr = data.length;
    const promedio = numEgr ? Math.round(totalEgr/numEgr) : 0;
    const porMetodo = {};
    const porCategoria = {};
    data.forEach(e => {
      const m = e.metodo_pago || 'Sin método';
      porMetodo[m] = (porMetodo[m]||0) + (e.monto||0);
      const c = e.categoria || 'Sin categoría';
      porCategoria[c] = (porCategoria[c]||0) + (e.monto||0);
    });
    let kpisEgr = `<div class="kpi-card"><div class="kpi-label">Total egresos</div><div class="kpi-value" style="color:var(--rojo)">${fmt$(totalEgr)}</div></div>
      <div class="kpi-card"><div class="kpi-label">Transacciones</div><div class="kpi-value">${numEgr}</div></div>
      <div class="kpi-card"><div class="kpi-label">Promedio</div><div class="kpi-value">${fmt$(promedio)}</div></div>`;
    for (const [m,v] of Object.entries(porMetodo)) kpisEgr += `<div class="kpi-card"><div class="kpi-label">${esc(m)}</div><div class="kpi-value">${fmt$(v)}</div></div>`;
    for (const [c,v] of Object.entries(porCategoria)) kpisEgr += `<div class="kpi-card"><div class="kpi-label">${esc(c)}</div><div class="kpi-value">${fmt$(v)}</div></div>`;
    const kpisEl = document.getElementById('fin-egr-kpis');
    if (kpisEl) kpisEl.innerHTML = kpisEgr;
    const tbody = document.getElementById('egresos-tbody');
    tbody.innerHTML = data.map(e => `<tr>
      <td>${fmtDate(e.fecha)}</td>
      <td>${esc(e.concepto)}${e.es_recurrente ? ' <span style="color:var(--dorado);font-size:10px">RECURRENTE</span>' : ''}</td>
      <td>${esc(e.categoria)}</td>
      <td>${esc(e.metodo_pago||'—')}</td>
      <td>${esc(e.proveedor||'—')}</td>
      <td style="font-weight:600">${fmt$(e.monto)}</td>
      <td style="white-space:nowrap"><button class="btn-sm" onclick="verEgreso(${e.id})">👁</button> <button class="btn-sm" onclick="editarEgreso(${e.id})">Editar</button> <button class="btn-sm" onclick="eliminarEgreso(${e.id})" style="color:var(--rojo)">🗑</button></td>
    </tr>`).join('') || '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--texto2)">Sin egresos</td></tr>';
  }
}

function mpOptions(selected) {
  return metodosPagoEgreso.filter(m=>m.activo).map(m => `<option value="${esc(m.nombre)}" ${selected===m.nombre?'selected':''}>${esc(m.nombre)}</option>`).join('');
}

async function abrirModalEgreso(eg) {
  await loadMetodosPago();
  await loadCategoriasGasto();
  await loadProveedores();
  await loadCuentasFinList();
  const hoy = new Date().toISOString().split('T')[0];
  document.getElementById('modal-egreso-body').innerHTML = `
    <div class="field"><label>Fecha *</label><input type="date" id="eg-fecha" value="${eg?.fecha||hoy}"></div>
    <div class="field"><label>Concepto *</label><input id="eg-concepto" value="${esc(eg?.concepto||'')}"></div>
    <div class="field"><label>Categoría</label><select id="eg-cat"><option value="">Selecciona...</option>${catGastoOptions(eg?.categoria)}</select></div>
    <div class="field"><label>Método de pago *</label><select id="eg-mp"><option value="">Selecciona...</option>${mpOptions(eg?.metodo_pago)}</select><div style="font-size:11px;color:var(--texto2);margin-top:4px">💡 Si seleccionas "Caja" o "Caja chica", el gasto se descuenta automáticamente del saldo de esa cuenta.</div></div>
    <div class="field"><label>Proveedor</label>
      <div style="display:flex;gap:6px">
        <select id="eg-prov" style="flex:1"><option value="">Sin proveedor</option>${provOptions(eg?.proveedor)}</select>
        <button type="button" class="btn-sm" onclick="agregarProvDesdeEgreso()" style="white-space:nowrap;font-size:11px">+ Nuevo</button>
      </div>
    </div>
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
    // Ajustar filtro para que incluya la fecha del gasto guardado
    const {desde, hasta} = getFinDates();
    if (body.fecha < desde || body.fecha > hasta) {
      document.getElementById('fin-periodo').value = 'mes';
      onFinPeriodoChange();
    } else {
      await loadEgresos();
    }
  } catch(e) {
    alert('Error de conexión al guardar egreso');
  }
}

async function agregarProvDesdeEgreso() {
  const nombre = prompt('Nombre del nuevo proveedor:');
  if (!nombre || !nombre.trim()) return;
  try {
    await fetch(API+'/api/admin/proveedores', {method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({nombre:nombre.trim()})});
    await loadProveedores();
    // Refresh the select keeping current form state
    const sel = document.getElementById('eg-prov');
    if (sel) {
      sel.innerHTML = '<option value="">Sin proveedor</option>' + provOptions(nombre.trim());
      sel.value = nombre.trim();
    }
    showToast('Proveedor agregado');
  } catch(e) { alert('Error al crear proveedor'); }
}

function verEgreso(id) {
  const eg = (finData.egresos || []).find(e => e.id === id);
  if (!eg) return;
  const overlay = document.createElement('div');
  overlay.id = 'ver-egreso-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;padding:20px';
  overlay.onclick = function(ev) { if (ev.target === overlay) overlay.remove(); };
  overlay.innerHTML = `
    <div style="background:#fff;border-radius:16px;padding:24px;max-width:420px;width:100%;box-shadow:0 8px 30px rgba(0,0,0,.15);max-height:80vh;overflow-y:auto">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h3 style="margin:0;font-size:16px;color:#193a2c">Detalle del gasto</h3>
        <button id="ver-eg-close-x" style="background:none;border:none;font-size:20px;cursor:pointer;color:#999">&times;</button>
      </div>
      <div style="display:grid;gap:12px;font-size:13px">
        <div><span style="color:#5a5a5a;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Fecha</span><div style="font-weight:600">${fmtDate(eg.fecha)}</div></div>
        <div><span style="color:#5a5a5a;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Concepto</span><div style="font-weight:600">${esc(eg.concepto)}</div></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div><span style="color:#5a5a5a;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Monto</span><div style="font-weight:700;font-size:18px;color:#193a2c">${fmt$(eg.monto)}</div></div>
          <div><span style="color:#5a5a5a;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Metodo de pago</span><div style="font-weight:500">${esc(eg.metodo_pago||'—')}</div></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div><span style="color:#5a5a5a;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Categoria</span><div>${esc(eg.categoria||'—')}</div></div>
          <div><span style="color:#5a5a5a;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Proveedor</span><div>${esc(eg.proveedor||'—')}</div></div>
        </div>
        ${eg.referencia ? `<div><span style="color:#5a5a5a;font-size:11px;text-transform:uppercase;letter-spacing:.5px"># Factura / Referencia</span><div>${esc(eg.referencia)}</div></div>` : ''}
        ${eg.notas ? `<div><span style="color:#5a5a5a;font-size:11px;text-transform:uppercase;letter-spacing:.5px">Notas</span><div style="white-space:pre-wrap">${esc(eg.notas)}</div></div>` : ''}
        ${eg.es_recurrente ? '<div style="color:#d4a843;font-weight:600;font-size:12px">Este gasto es recurrente</div>' : ''}
      </div>
      <div style="display:flex;gap:8px;margin-top:16px">
        <button id="ver-eg-edit" style="flex:1;padding:10px;border:1px solid #e5e0d8;border-radius:8px;background:#fff;cursor:pointer;font-family:Inter,sans-serif;font-size:13px">Editar</button>
        <button id="ver-eg-close" style="flex:1;padding:10px;border:none;border-radius:8px;background:#193a2c;color:#fff;cursor:pointer;font-family:Inter,sans-serif;font-size:13px;font-weight:600">Cerrar</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  document.getElementById('ver-eg-close-x').addEventListener('click', () => overlay.remove());
  document.getElementById('ver-eg-close').addEventListener('click', () => overlay.remove());
  document.getElementById('ver-eg-edit').addEventListener('click', () => { overlay.remove(); editarEgreso(eg.id); });
}

async function editarEgreso(id) {
  // Find egreso in finData.egresos
  const eg = (finData.egresos || []).find(e => e.id === id);
  if (eg) { abrirModalEgreso(eg); return; }
  // Fallback: fetch from API
  try {
    const r = await fetch(API+'/api/admin/egresos', {credentials:'include'});
    const all = await r.json();
    const found = all.find(e => e.id === id);
    if (found) abrirModalEgreso(found);
  } catch(e) {}
}

async function eliminarEgreso(id) {
  if (!confirm('¿Eliminar este gasto?')) return;
  await fetch(API+'/api/admin/egresos/'+id, {method:'DELETE', credentials:'include'});
  loadEgresos();
}

// --- Gastos recurrentes ---
async function abrirGastosRecurrentes() {
  await loadMetodosPago();
  await loadProveedores();
  try {
    const r = await fetch(API+'/api/admin/gastos-recurrentes', {credentials:'include'});
    const data = await r.json();
    // Check paid status por frecuencia (rodante desde hoy)
    const hoyD = new Date(); hoyD.setHours(0,0,0,0);
    const hastaRec = hoyD.toISOString().split('T')[0];
    const desdeRec = new Date(hoyD.getTime() - 35*24*3600*1000).toISOString().split('T')[0];
    const er = await fetch(API+'/api/admin/egresos?desde='+desdeRec+'&hasta='+hastaRec, {credentials:'include'});
    const egs = await er.json();
    // Mapa concepto -> fecha del pago recurrente más reciente
    const ultimoPago = {};
    egs.filter(e=>e.es_recurrente).forEach(e => {
      const prev = ultimoPago[e.concepto];
      if (!prev || e.fecha > prev) ultimoPago[e.concepto] = e.fecha;
    });
    const diasFrecuencia = {semanal:7, quincenal:15, mensual:30};
    const estaPagado = (g) => {
      const f = ultimoPago[g.nombre];
      if (!f) return null;
      const dias = Math.floor((hoyD - new Date(f+'T00:00:00')) / (24*3600*1000));
      const limite = diasFrecuencia[g.frecuencia] ?? 30;
      return dias < limite ? f : null;
    };

    document.getElementById('modal-egreso-body').innerHTML = `
      <h4 style="margin-bottom:12px">Gastos recurrentes</h4>
      ${data.filter(g=>g.activo).map(g => {
        const paidFecha = estaPagado(g);
        return `<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--borde)">
          <div style="flex:1"><strong>${esc(g.nombre)}</strong><br><span style="font-size:11px;color:var(--texto2)">${g.categoria} · ${g.frecuencia} · ${fmt$(g.monto_sugerido)}${g.metodo_pago ? ' · '+esc(g.metodo_pago) : ''}${g.proveedor ? ' · '+esc(g.proveedor) : ''}</span></div>
          ${paidFecha ? `<span style="color:var(--verde);font-size:12px;font-weight:600" title="Pagado el ${paidFecha}">Pagado ✓<br><span style="font-size:10px;font-weight:400;color:var(--texto2)">${paidFecha}</span></span>` : `<button class="btn-dorado" onclick="pagarRecurrente(${g.id},'${esc(g.nombre)}',${g.monto_sugerido},'${esc(g.categoria)}','${esc(g.proveedor||'')}','${esc(g.metodo_pago||'')}')">Marcar pagado</button>`}
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
          <select id="gr-mp" style="padding:6px;font-size:12px"><option value="">Método de pago</option>${mpOptions()}</select>
          <select id="gr-prov" style="padding:6px;font-size:12px"><option value="">Sin proveedor</option>${provOptions()}</select>
        </div>
        <button class="btn-primary" onclick="crearGastoRec()" style="margin-top:8px;width:100%">Agregar</button>
      </div>
    `;
    document.getElementById('modal-egreso').classList.add('active');
  } catch(e) {}
}

async function pagarRecurrente(id, nombre, monto, categoria, proveedor, metodoPago) {
  await loadMetodosPago();
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4>Pagar: ${esc(nombre)}</h4>
    <div class="field"><label>Monto real (pesos)</label><input type="number" id="pr-monto" value="${(monto/100).toFixed(2)}" step="0.01"></div>
    <div class="field"><label>Método de pago *</label><select id="pr-mp"><option value="">Selecciona...</option>${mpOptions(metodoPago)}</select></div>
    <div class="field"><label>Fecha de pago</label><input type="date" id="pr-fecha" value="${new Date().toISOString().split('T')[0]}"></div>
    <div class="field"><label>Notas</label><input id="pr-notas"></div>
    <input type="hidden" id="pr-proveedor" value="${esc(proveedor||'')}">
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
    proveedor: document.getElementById('pr-proveedor')?.value?.trim() || null,
    monto: Math.round(parseFloat(document.getElementById('pr-monto').value||0)*100),
    notas: document.getElementById('pr-notas').value.trim() || null,
    es_recurrente: true,
  };
  if (!body.monto) return alert('Monto es obligatorio');
  await fetch(API+'/api/admin/egresos', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(body)});
  showToast('Pago registrado ✓');
  loadEgresos();
  abrirGastosRecurrentes();
}

async function crearGastoRec() {
  const nombre = document.getElementById('gr-nombre').value.trim();
  if (!nombre) return alert('Nombre requerido');
  await fetch(API+'/api/admin/gastos-recurrentes', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify({nombre, categoria: document.getElementById('gr-cat').value, frecuencia: document.getElementById('gr-freq').value, monto_sugerido: Math.round(parseFloat(document.getElementById('gr-monto').value||0)*100), metodo_pago: document.getElementById('gr-mp')?.value || null, proveedor: document.getElementById('gr-prov')?.value?.trim() || null})
  });
  abrirGastosRecurrentes();
}

async function eliminarGastoRec(id) {
  if (!confirm('¿Eliminar?')) return;
  await fetch(API+'/api/admin/gastos-recurrentes/'+id, {method:'DELETE', credentials:'include'});
  abrirGastosRecurrentes();
}

// ─────── IMPORTAR EGRESOS DESDE KYTE ───────
function abrirImportarKyte() {
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4 style="margin-bottom:12px">Importar egresos desde Kyte</h4>
    <div style="font-size:12px;color:var(--texto2);margin-bottom:12px">
      Sube el export <strong>.xlsx</strong> de Kyte (Expenses). El sistema:<br>
      • Filtra por rango de fechas opcional<br>
      • Mapea categorías Kyte → tus categorías<br>
      • Detecta duplicados por ID Kyte (puedes correrlo varias veces)<br>
      • Te muestra preview antes de importar
    </div>
    <div class="field"><label>Archivo xlsx *</label><input type="file" id="kyte-file" accept=".xlsx"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
      <div class="field"><label>Desde (opcional)</label><input type="date" id="kyte-desde" value="2026-01-01"></div>
      <div class="field"><label>Hasta (opcional)</label><input type="date" id="kyte-hasta" value="2026-03-31"></div>
    </div>
    <div id="kyte-preview" style="margin-top:12px"></div>
    <div style="display:flex;gap:8px;margin-top:12px">
      <button class="btn-sm" onclick="kyteDryRun()" style="flex:1">👁 Vista previa</button>
      <button class="btn-primary" id="kyte-confirmar" onclick="kyteImportar()" disabled style="flex:1">Importar</button>
    </div>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function _kytePost(dryRun) {
  const f = document.getElementById('kyte-file').files[0];
  if (!f) { alert('Selecciona el archivo xlsx'); return null; }
  const desde = document.getElementById('kyte-desde').value;
  const hasta = document.getElementById('kyte-hasta').value;
  const fd = new FormData();
  fd.append('file', f);
  let url = API+'/api/admin/egresos/importar-kyte?dry_run='+(dryRun?'true':'false');
  if (desde) url += '&desde='+desde;
  if (hasta) url += '&hasta='+hasta;
  try {
    const r = await fetch(url, {method:'POST', credentials:'include', body: fd});
    if (!r.ok) {
      const err = await r.json().catch(()=>({}));
      alert('Error: '+(err.detail||r.status));
      return null;
    }
    return await r.json();
  } catch(e) { alert('Error: '+e.message); return null; }
}

async function kyteDryRun() {
  const cont = document.getElementById('kyte-preview');
  cont.innerHTML = '<div style="padding:12px;color:var(--texto2)">Procesando...</div>';
  const d = await _kytePost(true);
  if (!d) { cont.innerHTML = ''; return; }
  let html = `<div style="background:var(--crema);border-radius:8px;padding:12px;font-size:12px">
    <div style="font-weight:600;color:var(--verde);margin-bottom:6px">Vista previa</div>
    <div>Total filas en xlsx: <strong>${d.total_filas_xlsx}</strong></div>
    <div>Fuera de rango fecha: <strong>${d.skipped_filtro_fecha}</strong></div>
    <div>Inválidos: <strong>${d.skipped_invalido}</strong></div>
    <div style="margin-top:6px;font-size:14px">A insertar (nuevos): <strong style="color:var(--verde)">${d.a_insertar_nuevos||0}</strong></div>
    <div style="font-size:14px">A actualizar (ya existían): <strong style="color:var(--dorado)">${d.a_actualizar_existentes||0}</strong></div>
    <div>Monto total: <strong style="color:var(--verde)">${fmt$(d.monto_total)}</strong></div>`;
  if (Object.keys(d.por_categoria||{}).length) {
    html += '<div style="margin-top:8px"><strong>Por categoría:</strong></div>';
    for (const [k,v] of Object.entries(d.por_categoria)) {
      html += `<div style="padding-left:12px">${esc(k)}: ${fmt$(v)}</div>`;
    }
  }
  if (Object.keys(d.por_metodo_pago||{}).length) {
    html += '<div style="margin-top:8px"><strong>Por método pago:</strong></div>';
    for (const [k,v] of Object.entries(d.por_metodo_pago)) {
      html += `<div style="padding-left:12px">${esc(k)}: ${fmt$(v)}</div>`;
    }
  }
  if (d.primeros_5?.length) {
    html += '<div style="margin-top:8px"><strong>Primeros 5:</strong></div>';
    for (const r of d.primeros_5) {
      html += `<div style="padding-left:12px;font-size:11px">${r.fecha} · ${esc(r.concepto)} · ${esc(r.categoria)} · ${fmt$(r.monto)}${r.proveedor?' · '+esc(r.proveedor):''}</div>`;
    }
  }
  html += '</div>';
  cont.innerHTML = html;
  document.getElementById('kyte-confirmar').disabled = ((d.a_insertar_nuevos||0) + (d.a_actualizar_existentes||0) === 0);
}

async function kyteImportar() {
  if (!confirm('¿Importar/actualizar egresos en la base de datos?')) return;
  const btn = document.getElementById('kyte-confirmar');
  btn.disabled = true; btn.textContent = 'Importando...';
  const d = await _kytePost(false);
  if (!d) { btn.disabled = false; btn.textContent = 'Importar'; return; }
  showToast(`Insertados: ${d.insertados||0} · Actualizados: ${d.actualizados||0} ✓`);
  cerrarModal('modal-egreso');
  loadEgresos();
}

// ─────── CUENTAS FINANCIERAS (Caja + Caja Chica) ───────
let cuentasFin = [];
let cuentasSaldos = [];

async function loadCuentasFinList() {
  try {
    const r = await fetch(API+'/api/admin/cuentas-financieras', {credentials:'include'});
    if (r.ok) cuentasFin = await r.json();
  } catch(e) {}
}

function cuentasOptions(selected) {
  return (cuentasFin||[]).filter(c=>c.activo).map(c =>
    `<option value="${c.id}" ${String(selected)===String(c.id)?'selected':''}>${esc(c.nombre)}</option>`
  ).join('');
}

async function loadCuentas() {
  await loadCuentasFinList();
  try {
    const r = await fetch(API+'/api/admin/cuentas-financieras/saldos', {credentials:'include'});
    if (!r.ok) return;
    cuentasSaldos = await r.json();
    renderCuentasCards();
    loadMovimientosCuentas();
  } catch(e) {}
}

async function crearCuentasDefault() {
  if (!confirm('¿Crear las cuentas Caja y Caja Chica?')) return;
  try {
    const r = await fetch(API+'/api/admin/cuentas-financieras/seed-default', {method:'POST', credentials:'include'});
    if (!r.ok) {
      const err = await r.json().catch(()=>({}));
      return alert('Error: '+(err.detail||r.status));
    }
    showToast('Cuentas creadas ✓');
    loadCuentas();
  } catch(e) { alert('Error: '+e.message); }
}

function renderCuentasCards() {
  const cont = document.getElementById('cuentas-cards');
  if (!cont) return;
  if (!cuentasSaldos || cuentasSaldos.length === 0) {
    cont.innerHTML = `<div style="grid-column:1/-1;background:var(--crema);border:2px dashed var(--borde);border-radius:12px;padding:32px;text-align:center">
      <div style="font-size:14px;color:var(--texto2);margin-bottom:12px">Sin cuentas configuradas</div>
      <button class="btn-primary" onclick="crearCuentasDefault()">+ Crear Caja y Caja Chica</button>
    </div>`;
    return;
  }
  cont.innerHTML = cuentasSaldos.map(c => {
    const color = c.tipo === 'caja' ? 'var(--dorado)' : 'var(--verde)';
    const icon = c.tipo === 'caja' ? '💵' : '🏦';
    return `<div style="background:#fff;border:2px solid ${color};border-radius:12px;padding:18px;box-shadow:0 2px 6px rgba(0,0,0,.05)">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
        <div>
          <div style="font-size:13px;color:var(--texto2);text-transform:uppercase;letter-spacing:.5px">${icon} ${esc(c.nombre)}</div>
          <div style="font-size:11px;color:var(--texto2);margin-top:2px">Desde ${c.fecha_inicio}</div>
        </div>
        <button class="btn-sm" onclick="abrirConfigCuenta(${c.id})" title="Configurar">⚙</button>
      </div>
      <div style="font-size:32px;font-weight:700;color:${color};margin:8px 0">${fmt$(c.saldo_actual)}</div>
      <div style="font-size:11px;color:var(--texto2);line-height:1.6">
        Saldo inicial: ${fmt$(c.saldo_inicial)}<br>
        ${c.tipo==='caja' ? 'Ventas efectivo POS: '+fmt$(c.ingresos_efectivo_pos)+'<br>' : ''}
        ${c.otros_ingresos ? '+ Otros ingresos: '+fmt$(c.otros_ingresos)+'<br>' : ''}
        + Depósitos / transferencias: ${fmt$(c.depositos)}<br>
        − Egresos: ${fmt$(c.egresos)}<br>
        − Retiros / transferencias: ${fmt$(c.retiros)}
        ${c.fondo_base ? '<br><span style="color:var(--dorado)">Fondo físico: '+fmt$(c.fondo_base)+'</span>' : ''}
      </div>
    </div>`;
  }).join('') || '<div style="color:var(--texto2);padding:12px">Sin cuentas configuradas</div>';
}

async function loadMovimientosCuentas() {
  try {
    const r = await fetch(API+'/api/admin/movimientos-cuenta', {credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    const cuentaName = (id) => (cuentasFin.find(c=>c.id===id)||{}).nombre || '—';
    const tipoLabel = {
      deposito_corte_pos: 'Depósito (corte POS)',
      deposito_manual: 'Depósito manual',
      retiro_manual: 'Retiro manual',
      transferencia_in: 'Transferencia ↓',
      transferencia_out: 'Transferencia ↑',
      ajuste_positivo: 'Ajuste +',
      ajuste_negativo: 'Ajuste −',
    };
    const tbody = document.getElementById('cuentas-mvts-tbody');
    tbody.innerHTML = data.map(m => {
      const esOut = m.tipo === 'transferencia_out' || m.tipo === 'retiro_manual' || m.tipo === 'ajuste_negativo';
      const color = esOut ? 'var(--rojo)' : 'var(--verde)';
      const signo = esOut ? '−' : '+';
      return `<tr>
        <td>${fmtDate(m.fecha)}</td>
        <td>${esc(cuentaName(m.cuenta_id))}${m.cuenta_destino_id ? ' → '+esc(cuentaName(m.cuenta_destino_id)) : ''}</td>
        <td>${esc(tipoLabel[m.tipo]||m.tipo)}</td>
        <td>${esc(m.concepto||'')}</td>
        <td style="font-weight:600;color:${color}">${signo} ${fmt$(m.monto)}</td>
        <td><button class="btn-sm" onclick="eliminarMovimiento(${m.id})" style="color:var(--rojo)">🗑</button></td>
      </tr>`;
    }).join('') || '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--texto2)">Sin movimientos</td></tr>';
  } catch(e) {}
}

async function abrirConfigCuenta(id) {
  const c = cuentasFin.find(x => x.id === id);
  if (!c) return;
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4>Configurar: ${esc(c.nombre)}</h4>
    <div class="field"><label>Saldo inicial (pesos)</label><input type="number" id="cf-saldo" value="${(c.saldo_inicial/100).toFixed(2)}" step="0.01"></div>
    <div class="field"><label>Fecha de inicio (desde cuándo se calcula el saldo)</label><input type="date" id="cf-fecha" value="${c.fecha_inicio}"></div>
    <div class="field"><label>Fondo físico base (pesos, solo Caja)</label><input type="number" id="cf-fondo" value="${(c.fondo_base/100).toFixed(2)}" step="0.01"></div>
    <div style="font-size:11px;color:var(--texto2);background:var(--crema);padding:8px;border-radius:6px;margin-top:8px">
      <strong>Saldo inicial</strong>: dinero que ya estaba en la cuenta antes de empezar a usar el sistema. Los egresos y movimientos posteriores a la fecha de inicio se sumarán/restarán automáticamente.
    </div>
    <button class="btn-primary" onclick="guardarConfigCuenta(${id})" style="width:100%;margin-top:12px">Guardar</button>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function guardarConfigCuenta(id) {
  const body = {
    saldo_inicial: Math.round(parseFloat(document.getElementById('cf-saldo').value||0)*100),
    fecha_inicio: document.getElementById('cf-fecha').value,
    fondo_base: Math.round(parseFloat(document.getElementById('cf-fondo').value||0)*100),
  };
  const r = await fetch(API+'/api/admin/cuentas-financieras/'+id, {
    method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include',
    body: JSON.stringify(body)
  });
  if (!r.ok) return alert('Error al guardar');
  cerrarModal('modal-egreso');
  showToast('Cuenta actualizada ✓');
  loadCuentas();
}

async function abrirModalMovimiento() {
  await loadCuentasFinList();
  const hoy = new Date().toISOString().split('T')[0];
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4>Registrar movimiento</h4>
    <div class="field"><label>Cuenta *</label><select id="mv-cuenta"><option value="">Selecciona...</option>${cuentasOptions()}</select></div>
    <div class="field"><label>Tipo *</label>
      <select id="mv-tipo" onchange="onMvTipoChange()">
        <option value="deposito_manual">Depósito manual (entra dinero)</option>
        <option value="retiro_manual">Retiro manual (sale dinero)</option>
        <option value="transferencia_out">Transferencia a otra cuenta</option>
        <option value="ajuste_positivo">Ajuste + (corrección)</option>
        <option value="ajuste_negativo">Ajuste − (corrección)</option>
      </select>
    </div>
    <div class="field" id="mv-destino-wrap" style="display:none"><label>Cuenta destino *</label><select id="mv-destino"><option value="">Selecciona...</option>${cuentasOptions()}</select></div>
    <div class="field"><label>Fecha *</label><input type="date" id="mv-fecha" value="${hoy}"></div>
    <div class="field"><label>Concepto *</label><input id="mv-concepto" placeholder="Ej. Retiro a bolsita, Pago efectivo proveedor"></div>
    <div class="field"><label>Monto * (pesos)</label><input type="number" id="mv-monto" step="0.01"></div>
    <div class="field"><label>Notas</label><textarea id="mv-notas"></textarea></div>
    <button class="btn-primary" onclick="guardarMovimiento()" style="width:100%;margin-top:8px">Guardar</button>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

function onMvTipoChange() {
  const tipo = document.getElementById('mv-tipo').value;
  document.getElementById('mv-destino-wrap').style.display = (tipo === 'transferencia_out') ? '' : 'none';
}

async function guardarMovimiento() {
  const tipo = document.getElementById('mv-tipo').value;
  const cuenta_id = parseInt(document.getElementById('mv-cuenta').value||0);
  if (!cuenta_id) return alert('Selecciona la cuenta');
  const concepto = document.getElementById('mv-concepto').value.trim();
  if (!concepto) return alert('Concepto obligatorio');
  const monto = Math.round(parseFloat(document.getElementById('mv-monto').value||0)*100);
  if (!monto || monto <= 0) return alert('Monto debe ser positivo');
  const body = {
    cuenta_id, tipo,
    fecha: document.getElementById('mv-fecha').value,
    concepto, monto,
    notas: document.getElementById('mv-notas').value.trim() || null,
  };
  const postMv = async (b) => {
    const r = await fetch(API+'/api/admin/movimientos-cuenta', {method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(b)});
    if (!r.ok) {
      const err = await r.json().catch(()=>({}));
      throw new Error(err.detail || ('HTTP '+r.status));
    }
  };
  try {
    if (tipo === 'transferencia_out') {
      const dest = parseInt(document.getElementById('mv-destino').value||0);
      if (!dest) return alert('Selecciona cuenta destino');
      if (dest === cuenta_id) return alert('Cuenta destino debe ser distinta');
      body.cuenta_destino_id = dest;
      await postMv(body);
      const bodyIn = {...body, cuenta_id: dest, cuenta_destino_id: cuenta_id, tipo: 'transferencia_in'};
      await postMv(bodyIn);
    } else {
      await postMv(body);
    }
    cerrarModal('modal-egreso');
    showToast('Movimiento registrado ✓');
    loadCuentas();
  } catch(e) {
    alert('Error al guardar: '+e.message);
  }
}

async function eliminarMovimiento(id) {
  if (!confirm('¿Eliminar movimiento? (Si es transferencia, debes eliminar también el movimiento espejo en la otra cuenta)')) return;
  await fetch(API+'/api/admin/movimientos-cuenta/'+id, {method:'DELETE', credentials:'include'});
  loadCuentas();
}

async function confirmarCerrarSemana() {
  if (!confirm('¿Cerrar semana? Todo el saldo de Caja se transferirá a Caja Chica y Caja arrancará en $0 desde mañana.')) return;
  try {
    const r = await fetch(API+'/api/admin/cuentas-financieras/cerrar-semana', {method:'POST', credentials:'include'});
    if (!r.ok) {
      const err = await r.json().catch(()=>({}));
      return alert('Error: '+(err.detail||r.status));
    }
    const d = await r.json();
    showToast(d.mensaje || ('Transferido '+fmt$(d.transferido||0)+' a Caja Chica ✓'));
    loadCuentas();
  } catch(e) { alert('Error: '+e.message); }
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

// --- Proveedores ---
let proveedoresList = [];

async function loadProveedores() {
  try { const r = await fetch(API+'/api/admin/proveedores',{credentials:'include'}); proveedoresList = await r.json(); } catch(e) {}
}

function provOptions(selected) {
  return proveedoresList.filter(p=>p.activo).map(p => `<option value="${esc(p.nombre)}" ${selected===p.nombre?'selected':''}>${esc(p.nombre)}</option>`).join('');
}

async function abrirProveedores() {
  await loadProveedores();
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4>Proveedores</h4>
    ${proveedoresList.map(p => `<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--borde)">
      <div style="flex:1">
        <input value="${esc(p.nombre)}" id="prov-nom-${p.id}" style="font-size:12px;padding:4px 8px;border:1px solid var(--borde);border-radius:4px;width:100%;margin-bottom:2px">
        <div style="display:flex;gap:4px">
          <input value="${esc(p.contacto||'')}" id="prov-con-${p.id}" placeholder="Contacto" style="font-size:11px;padding:3px 6px;border:1px solid var(--borde);border-radius:4px;flex:1">
          <input value="${esc(p.telefono||'')}" id="prov-tel-${p.id}" placeholder="Teléfono" style="font-size:11px;padding:3px 6px;border:1px solid var(--borde);border-radius:4px;width:100px">
        </div>
      </div>
      <label style="font-size:11px;display:flex;align-items:center;gap:3px"><input type="checkbox" ${p.activo?'checked':''} onchange="toggleProv(${p.id},this.checked)">Act</label>
      <button class="btn-sm" onclick="guardarProv(${p.id})" style="font-size:11px">Guardar</button>
      <button class="btn-danger" style="font-size:11px;padding:4px 6px" onclick="eliminarProv(${p.id})">🗑</button>
    </div>`).join('') || '<div style="color:var(--texto2);padding:12px">Sin proveedores</div>'}
    <div style="border-top:1px solid var(--borde);margin-top:12px;padding-top:12px">
      <strong style="font-size:13px">Nuevo proveedor</strong>
      <div style="display:flex;gap:6px;margin-top:8px">
        <input id="prov-new-nom" placeholder="Nombre *" style="flex:1;padding:6px 10px;border:1px solid var(--borde);border-radius:6px;font-size:13px">
        <input id="prov-new-con" placeholder="Contacto" style="flex:1;padding:6px 10px;border:1px solid var(--borde);border-radius:6px;font-size:13px">
        <input id="prov-new-tel" placeholder="Teléfono" style="width:100px;padding:6px 10px;border:1px solid var(--borde);border-radius:6px;font-size:13px">
        <button class="btn-primary" onclick="crearProv()">Agregar</button>
      </div>
    </div>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function guardarProv(id) {
  await fetch(API+'/api/admin/proveedores/'+id, {method:'PUT',headers:{'Content-Type':'application/json'},credentials:'include',
    body:JSON.stringify({nombre:document.getElementById('prov-nom-'+id)?.value?.trim(), contacto:document.getElementById('prov-con-'+id)?.value?.trim()||null, telefono:document.getElementById('prov-tel-'+id)?.value?.trim()||null})});
  showToast('Guardado');
}

async function toggleProv(id, activo) {
  await fetch(API+'/api/admin/proveedores/'+id, {method:'PUT',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({activo})});
}

async function eliminarProv(id) {
  if (!confirm('Eliminar?')) return;
  const r = await fetch(API+'/api/admin/proveedores/'+id, {method:'DELETE',credentials:'include'});
  if (!r.ok) { const e = await r.json(); alert(e.detail||'Error'); return; }
  abrirProveedores();
}

async function crearProv() {
  const nombre = document.getElementById('prov-new-nom').value.trim();
  if (!nombre) return alert('Nombre requerido');
  await fetch(API+'/api/admin/proveedores', {method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',
    body:JSON.stringify({nombre, contacto:document.getElementById('prov-new-con').value.trim()||null, telefono:document.getElementById('prov-new-tel').value.trim()||null})});
  abrirProveedores();
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
let _cortesLastData = null;

function _cortesPeriodoQS() {
  const p = document.getElementById('cortes-periodo').value;
  const d = document.getElementById('cortes-desde');
  const h = document.getElementById('cortes-hasta');
  d.style.display = (p === 'rango') ? '' : 'none';
  h.style.display = (p === 'rango') ? '' : 'none';
  if (p === 'rango') {
    if (!d.value || !h.value) return null;
    return 'rango&fecha_inicio='+d.value+'&fecha_fin='+h.value;
  }
  // 'anio' no es nativo del backend → calcular rango
  if (p === 'anio') {
    const hoy = new Date();
    const anio = hoy.getFullYear();
    const desde = anio+'-01-01';
    const hasta = hoy.toISOString().split('T')[0];
    return 'rango&fecha_inicio='+desde+'&fecha_fin='+hasta;
  }
  return p;
}

async function loadCortes() {
  const qs = _cortesPeriodoQS();
  if (!qs) return;
  try {
    const r = await fetch(API+'/pos/corte-caja?periodo='+qs, {credentials:'include'});
    if (!r.ok) return;
    const d = await r.json();
    _cortesLastData = d;
    // KPIs
    const kpisEl = document.getElementById('cortes-kpis');
    let kpis = `<div class="kpi-card"><div class="kpi-label">Total vendido</div><div class="kpi-value" style="color:var(--verde)">${fmt$(Math.round(d.total*100))}</div></div>
      <div class="kpi-card"><div class="kpi-label">Transacciones</div><div class="kpi-value">${d.total_transacciones}</div></div>
      <div class="kpi-card"><div class="kpi-label">Ticket promedio</div><div class="kpi-value">${fmt$(d.total_transacciones?Math.round(d.total*100/d.total_transacciones):0)}</div></div>`;
    for (const [m,v] of Object.entries(d.por_metodo||{})) {
      if (v > 0) kpis += `<div class="kpi-card"><div class="kpi-label">${esc(m)}</div><div class="kpi-value">${fmt$(Math.round(v*100))}</div></div>`;
    }
    kpisEl.innerHTML = kpis;
    // Detalle
    document.getElementById('cortes-detalle').innerHTML = `<div style="font-size:13px;color:var(--texto2);background:var(--crema);padding:12px;border-radius:8px">${esc(d.periodo||'')}</div>`;
  } catch(e) {}
  // Histórico cierres semanales (desde movimientos_cuenta)
  try {
    const r = await fetch(API+'/api/admin/movimientos-cuenta', {credentials:'include'});
    if (r.ok) {
      const mvts = await r.json();
      const cierres = mvts.filter(m => m.referencia_tipo === 'cierre_semanal' && m.tipo === 'transferencia_out');
      const tbody = document.getElementById('cortes-historico-tbody');
      tbody.innerHTML = cierres.map(m => `<tr>
        <td>${fmtDate(m.fecha)}</td>
        <td style="font-weight:600;color:var(--verde)">${fmt$(m.monto)}</td>
        <td>${esc(m.concepto||'')}</td>
      </tr>`).join('') || '<tr><td colspan="3" style="text-align:center;padding:20px;color:var(--texto2)">Sin cierres semanales todavía</td></tr>';
    }
  } catch(e) {}
}

function imprimirCorteAdmin() {
  const d = _cortesLastData;
  if (!d) return alert('Carga primero un periodo');
  const fP = (v) => '$' + v.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  const w = window.open('', '_blank');
  let html = `<html><head><title>Corte de caja</title>
    <style>
      body{font-family:'Inter',Arial,sans-serif;padding:24px;max-width:480px;margin:auto}
      h1{font-size:18px;text-align:center;color:#193a2c;margin:0 0 4px}
      .periodo{text-align:center;color:#666;font-size:13px;margin-bottom:16px}
      .row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px dashed #ccc}
      .total{font-size:18px;font-weight:700;color:#193a2c;border-top:2px solid #193a2c;border-bottom:2px solid #193a2c;padding:10px 0;margin-top:8px}
      .footer{text-align:center;color:#999;font-size:11px;margin-top:24px}
    </style></head><body>
    <h1>FLORERÍA LUCY — Corte de caja</h1>
    <div class="periodo">${esc(d.periodo||'')}</div>
    <div class="row"><span>Transacciones</span><span><strong>${d.total_transacciones}</strong></span></div>`;
  for (const [m,v] of Object.entries(d.por_metodo||{})) {
    if (v > 0) html += `<div class="row"><span>${esc(m)}</span><span>${fP(v)}</span></div>`;
  }
  html += `<div class="row total"><span>TOTAL</span><span>${fP(d.total)}</span></div>
    <div class="footer">${new Date().toLocaleString('es-MX',{timeZone:'America/Chihuahua'})}</div>
    </body></html>`;
  w.document.write(html);
  w.document.close();
  setTimeout(() => w.print(), 200);
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

// ══════ FACTURACIÓN ══════
function factSubTab(id) {
  const parent = document.getElementById('sec-facturacion');
  parent.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
  parent.querySelectorAll('.sub-content').forEach(c => c.style.display = 'none');
  event.target.classList.add('active');
  document.getElementById(id + '-content').style.display = '';
  if (id === 'fact-done') loadFacturados();
}

async function loadFacturacion() {
  try {
    const r = await fetch(API+'/api/admin/facturacion/pendientes',{credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    const tbody = document.getElementById('fact-tbody');
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--texto2);padding:40px">Sin pedidos pendientes de facturar</td></tr>'; return; }
    tbody.innerHTML = data.map(p => `<tr>
      <td style="font-weight:600;color:var(--verde)">${esc(p.folio)}</td>
      <td>${fmtDate(p.fecha)}</td>
      <td>${esc(p.cliente)}</td>
      <td>${esc(p.canal)}</td>
      <td>${fmt$(p.subtotal)}</td>
      <td style="color:var(--dorado)">${fmt$(p.iva)}</td>
      <td style="font-weight:600">${fmt$(p.total)}</td>
      <td>${p.datos_fiscales_id ? '<span style="color:var(--verde)" title="Datos fiscales completos">✓</span>' : '<span style="color:var(--rojo)" title="Sin datos fiscales">✗</span>'}</td>
      <td>
        <button class="btn-sm" onclick="verDatosFiscales(${p.id})">Datos</button>
        <button class="btn-sm" onclick="window.open('/pedidos/${p.id}/ticket-digital','_blank')">Ticket</button>
        <button class="btn-dorado" onclick="pedirFolioFiscal(${p.id})">Facturar</button>
      </td>
    </tr>`).join('');
  } catch(e) {}
}

async function loadFacturados() {
  try {
    const r = await fetch(API+'/api/admin/facturacion/facturados',{credentials:'include'});
    if (!r.ok) return;
    const data = await r.json();
    const tbody = document.getElementById('fact-done-tbody');
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--texto2);padding:40px">Sin pedidos facturados</td></tr>'; return; }
    tbody.innerHTML = data.map(p => `<tr>
      <td style="font-weight:600;color:var(--verde)">${esc(p.folio)}</td>
      <td>${fmtDate(p.fecha)}</td>
      <td>${esc(p.cliente)}</td>
      <td>${esc(p.canal)}</td>
      <td style="font-weight:600">${fmt$(p.total)}</td>
      <td style="color:var(--dorado);font-weight:600">${esc(p.folio_fiscal||'—')}</td>
      <td>
        <button class="btn-sm" onclick="verDatosFiscales(${p.id})">Datos</button>
      </td>
    </tr>`).join('');
  } catch(e) {}
}

function pedirFolioFiscal(id) {
  document.getElementById('modal-egreso-body').innerHTML = `
    <h4>Marcar como facturado</h4>
    <div class="field"><label>Folio fiscal (CFDI)</label><input id="ff-folio" placeholder="Ej: ABC-123-456"></div>
    <button class="btn-primary" onclick="confirmarFacturado(${id})" style="width:100%;margin-top:8px">Confirmar</button>
  `;
  document.getElementById('modal-egreso').classList.add('active');
}

async function confirmarFacturado(id) {
  const folio = document.getElementById('ff-folio')?.value?.trim() || '';
  await fetch(API+'/api/admin/facturacion/'+id+'/marcar',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({folio_fiscal:folio})});
  cerrarModal('modal-egreso');
  showToast('Facturado ✓');
  loadFacturacion();
  updateBadgeFact();
}

async function verDatosFiscales(pedidoId) {
  try {
    const r = await fetch(API+'/api/admin/datos-fiscales/pedido/'+pedidoId,{credentials:'include'});
    const d = await r.json();
    document.getElementById('modal-egreso-body').innerHTML = d.existe
      ? `<h4>Datos fiscales</h4>
         <div style="font-size:13px;line-height:1.8">
           <strong>RFC:</strong> ${esc(d.rfc||'—')}<br>
           <strong>Razón social:</strong> ${esc(d.razon_social||'—')}<br>
           <strong>Régimen:</strong> ${esc(d.regimen_fiscal||'—')}<br>
           <strong>Uso CFDI:</strong> ${esc(d.uso_cfdi||'—')}<br>
           <strong>Correo:</strong> ${esc(d.correo_fiscal||'—')}<br>
           <strong>C.P.:</strong> ${esc(d.codigo_postal||'—')}
         </div>`
      : '<h4>Datos fiscales</h4><div style="color:var(--texto2);padding:12px">Sin datos fiscales registrados para este pedido</div>';
    document.getElementById('modal-egreso').classList.add('active');
  } catch(e) {}
}

async function updateBadgeFact() {
  try {
    const r = await fetch(API+'/api/admin/facturacion/count',{credentials:'include'});
    const d = await r.json();
    const badge = document.getElementById('badge-fact');
    if (d.count > 0) { badge.style.display = 'flex'; badge.textContent = d.count > 9 ? '9+' : d.count; }
    else badge.style.display = 'none';
  } catch(e) {}
}
updateBadgeFact();
setInterval(updateBadgeFact, 30000);


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
  loadZonasAdmin();
  loadTurnos();
  loadFunerariasAdmin();
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
      {k:'clave_admin_pos',l:'Clave admin (cancelar/editar transacciones)',secret:true},
      {k:'ticket_mostrar_rfc',l:'Mostrar RFC en tickets',type:'toggle'},
      {k:'ticket_mensaje_footer',l:'Footer ticket digital'},
      {k:'ticket_termico_mensaje',l:'Footer ticket térmico'},
      {k:'pos_iva_default',l:'IVA por default en POS',type:'toggle'},
      {k:'pos_ieps_default',l:'IEPS por default en POS',type:'toggle'},
    ], cfg);
    renderCfgSection('cfg-whatsapp', [
      {k:'whatsapp_numero',l:'Número WhatsApp'},
      {k:'claudia_activa',l:'Claudia activa',type:'toggle'},
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
