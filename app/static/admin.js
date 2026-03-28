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
function debounceProdSearch() { clearTimeout(prodSearchTimeout); prodSearchTimeout = setTimeout(loadProductos, 300); }

async function loadProductos() {
  try {
    const q = (document.getElementById('prod-search')?.value || '').trim();
    const cat = document.getElementById('prod-cat-filter')?.value || '';
    const status = document.getElementById('prod-status-filter')?.value || '';
    const r = await fetch(API + '/productos/', {credentials:'include'});
    if (!r.ok) return;
    let data = await r.json();
    // Client-side filter
    if (q) { const ql = q.toLowerCase(); data = data.filter(p => p.nombre.toLowerCase().includes(ql) || (p.codigo||'').toLowerCase().includes(ql)); }
    if (cat) data = data.filter(p => p.categoria === cat);
    if (status === '1') data = data.filter(p => p.activo);
    if (status === '0') data = data.filter(p => !p.activo);
    // Populate category filter
    const cats = [...new Set(data.map(p => p.categoria))].sort();
    const catSel = document.getElementById('prod-cat-filter');
    if (catSel.options.length <= 1) {
      cats.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; catSel.appendChild(o); });
    }
    const tbody = document.getElementById('prod-tbody');
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--texto2);padding:40px">Sin productos</td></tr>'; return; }
    tbody.innerHTML = data.slice(0, 200).map(p => `<tr>
      <td><input type="checkbox" class="prod-check" data-id="${p.id}"></td>
      <td>${p.imagen_url ? '<img src="'+esc(p.imagen_url)+'" class="thumb">' : '—'}</td>
      <td style="font-weight:500">${esc(p.nombre)}</td>
      <td style="color:var(--texto2)">${esc(p.codigo||'—')}</td>
      <td>${esc(p.categoria)}</td>
      <td style="font-weight:600">${fmt$(p.precio)}</td>
      <td>${p.activo ? '<span style="color:var(--verde)">Si</span>' : '<span style="color:var(--rojo)">No</span>'}</td>
      <td>${p.visible_catalogo !== false ? '🌐' : '—'}</td>
      <td><button class="btn-sm" onclick="editarProducto(${p.id})">Editar</button></td>
    </tr>`).join('');
  } catch(e) { console.error(e); }
}

function toggleAllProds() {
  const checked = document.getElementById('prod-check-all').checked;
  document.querySelectorAll('.prod-check').forEach(c => c.checked = checked);
}

async function masivoProd(accion) {
  const ids = [...document.querySelectorAll('.prod-check:checked')].map(c => parseInt(c.dataset.id));
  if (!ids.length) return alert('Selecciona al menos un producto');
  for (const id of ids) {
    await fetch(API + '/productos/' + id, {
      method: 'PUT', headers: {'Content-Type':'application/json'}, credentials: 'include',
      body: JSON.stringify({activo: accion === 'activar'})
    });
  }
  showToast(`${ids.length} productos ${accion === 'activar' ? 'activados' : 'desactivados'} ✓`);
  loadProductos();
}

function abrirModalProducto(prod) {
  document.getElementById('modal-prod-title').textContent = prod ? 'Editar producto' : 'Nuevo producto';
  document.getElementById('modal-prod-body').innerHTML = `
    <div class="field"><label>Nombre *</label><input id="pf-nombre" value="${esc(prod?.nombre||'')}"></div>
    <div class="field"><label>Descripción</label><textarea id="pf-desc">${esc(prod?.descripcion||'')}</textarea></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div class="field"><label>SKU</label><input id="pf-sku" value="${esc(prod?.codigo||'')}"></div>
      <div class="field"><label>Categoría *</label><input id="pf-cat" value="${esc(prod?.categoria||'')}" list="cat-list"><datalist id="cat-list"></datalist></div>
      <div class="field"><label>Precio *</label><input type="number" id="pf-precio" value="${prod ? (prod.precio/100).toFixed(2) : ''}" step="0.01"></div>
      <div class="field"><label>Precio descuento</label><input type="number" id="pf-precio-desc" value="${prod?.precio_descuento ? (prod.precio_descuento/100).toFixed(2) : ''}" step="0.01"></div>
    </div>
    <div class="field"><label>URL imagen</label><input id="pf-img" value="${esc(prod?.imagen_url||'')}">
      <input type="file" id="pf-img-file" accept="image/*" style="margin-top:6px" onchange="subirImagenProd()">
      ${prod?.imagen_url ? '<img src="'+esc(prod.imagen_url)+'" style="width:80px;height:80px;object-fit:cover;border-radius:8px;margin-top:6px">' : ''}
    </div>
    <div style="display:flex;gap:12px;margin:12px 0">
      <label style="display:flex;align-items:center;gap:6px;font-size:13px"><input type="checkbox" id="pf-activo" ${prod?.activo !== false ? 'checked' : ''}> Activo</label>
      <label style="display:flex;align-items:center;gap:6px;font-size:13px"><input type="checkbox" id="pf-web" ${prod?.visible_catalogo !== false ? 'checked' : ''}> Visible en web</label>
    </div>
    <button class="btn-primary" onclick="guardarProducto(${prod?.id||'null'})" style="width:100%;margin-top:8px">Guardar</button>
  `;
  // Populate datalist
  fetch(API + '/productos/', {credentials:'include'}).then(r => r.json()).then(data => {
    const cats = [...new Set(data.map(p => p.categoria))].sort();
    document.getElementById('cat-list').innerHTML = cats.map(c => `<option value="${esc(c)}">`).join('');
  });
  document.getElementById('modal-producto').classList.add('active');
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
  const fd = new FormData();
  fd.append('imagen', file);
  try {
    const r = await fetch(API + '/productos/subir-imagen', {method:'POST', body:fd, credentials:'include'});
    const data = await r.json();
    if (data.url) {
      document.getElementById('pf-img').value = data.url;
      showToast('Imagen subida ✓');
    }
  } catch(e) { alert('Error al subir imagen'); }
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
  };
  if (!body.nombre || !body.categoria || !body.precio) return alert('Nombre, categoría y precio son obligatorios');
  const url = id ? API + '/productos/' + id : API + '/productos/';
  const method = id ? 'PUT' : 'POST';
  await fetch(url, {method, headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(body)});
  cerrarModal('modal-producto');
  showToast('Producto guardado ✓');
  loadProductos();
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
