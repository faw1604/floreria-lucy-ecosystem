/* ═══════════════════════════════════════════════════════════════════
   STOCK SYNC — Sincronización entre tabs del mismo navegador
   ═══════════════════════════════════════════════════════════════════
   Uso:
     - Llamar `broadcastStockChanged({source, productoId?})` después
       de CUALQUIER acción que modifique stock (vender, ajustar, cancelar).
     - Llamar `onStockChanged(callback)` una vez al cargar el panel para
       registrar la función que refresca la vista cuando llegue un evento.

   Funcionamiento:
     - Usa BroadcastChannel API (nativa). Solo entre tabs del MISMO
       navegador y MISMO origen. Cero costo de servidor.
     - Cross-navegador / cross-dispositivo sigue dependiendo del polling
       (admin 30s, POS 15s, etc.) que ya existe en cada panel.
   ═══════════════════════════════════════════════════════════════════ */
(function() {
  if (typeof window === 'undefined') return;
  if (window.__stockSyncInit) return;
  window.__stockSyncInit = true;

  const CHANNEL_NAME = 'fl_stock_sync';
  let _ch = null;
  try {
    if (typeof BroadcastChannel !== 'undefined') {
      _ch = new BroadcastChannel(CHANNEL_NAME);
    }
  } catch (e) {
    _ch = null;
  }

  const listeners = [];

  if (_ch) {
    _ch.onmessage = (ev) => {
      const data = ev && ev.data;
      if (!data || data.type !== 'stock-changed') return;
      // No reaccionar a nuestro propio broadcast (BroadcastChannel ya
      // excluye al sender, pero por defensa).
      listeners.forEach(fn => {
        try { fn(data); } catch (e) { console.error('[stock-sync] listener err', e); }
      });
    };
  }

  /**
   * Anuncia a todas las tabs del mismo navegador que el stock cambió.
   * @param {Object} info — { source, productoId?, motivo? }
   *   source: 'pos' | 'admin' | 'catalogo' | 'taller' | 'webhook'
   *   productoId: id del producto si se sabe (opcional)
   *   motivo: 'venta' | 'ajuste' | 'cancelacion' | 'devolucion' (opcional)
   */
  window.broadcastStockChanged = function(info) {
    if (!_ch) return;
    try {
      _ch.postMessage({
        type: 'stock-changed',
        source: (info && info.source) || 'unknown',
        productoId: (info && info.productoId) || null,
        motivo: (info && info.motivo) || null,
        ts: Date.now(),
      });
    } catch (e) {
      // Si falla por algun motivo no bloquea la operación
    }
  };

  /**
   * Registra un callback que se ejecuta cuando OTRA tab anuncia cambio de stock.
   * El callback recibe { source, productoId, motivo, ts }.
   */
  window.onStockChanged = function(callback) {
    if (typeof callback !== 'function') return;
    listeners.push(callback);
  };
})();
