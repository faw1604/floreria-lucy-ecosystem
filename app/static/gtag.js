// Google Tag (gtag.js) — carga condicional segun config
// Fer: configura window.FL_GADS_ID y window.FL_GADS_LABEL en el HTML antes de cargar este script
//
// Ejemplo en cada pagina publica (head):
//   <script>window.FL_GADS_ID='AW-1234567890';window.FL_GADS_LABEL='AbCdEfGhIj';</script>
//   <script src="/static/gtag.js" async></script>
//
// Para crear la conversion en Google Ads: Herramientas > Conversiones > Nueva accion > Sitio web > Compra
// Categoria: Compra | Nombre: "Pedido web confirmado" | Valor: distinto para cada conv | Recuento: Una
// Ventana: 30 dias | Modelo: Ultima interaccion
// Anota el ID (AW-...) y la etiqueta (alfanumerico).

(function() {
  var ID = window.FL_GADS_ID || '';
  if (!ID || !ID.startsWith('AW-') || ID.indexOf('XXXX') !== -1) {
    // Sin configuracion valida: deja un stub no-op para que el resto del codigo no rompa.
    window.flTrackPurchase = function() {};
    window.flTrackPageView = function() {};
    return;
  }

  // Cargar gtag.js
  var s = document.createElement('script');
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(ID);
  document.head.appendChild(s);

  window.dataLayer = window.dataLayer || [];
  function gtag(){ dataLayer.push(arguments); }
  window.gtag = gtag;
  gtag('js', new Date());
  gtag('config', ID, { 'allow_enhanced_conversions': true });

  // Helper para trackear compra/pedido confirmado
  // total en pesos MXN (no centavos), folio = FL-2026-XXXX
  window.flTrackPurchase = function(folio, totalPesos, opts) {
    if (!folio || typeof totalPesos !== 'number' || totalPesos <= 0) return;
    try {
      var send = ID + (window.FL_GADS_LABEL ? '/' + window.FL_GADS_LABEL : '');
      gtag('event', 'conversion', {
        'send_to': send,
        'value': totalPesos,
        'currency': 'MXN',
        'transaction_id': String(folio)
      });
      // Evento adicional GA4 estandar (si en el futuro se vincula GA4)
      gtag('event', 'purchase', {
        'transaction_id': String(folio),
        'value': totalPesos,
        'currency': 'MXN',
        'items': (opts && opts.items) || []
      });
    } catch(e) { /* silencioso, no romper UX */ }
  };

  window.flTrackPageView = function(extra) {
    try { gtag('event', 'page_view', extra || {}); } catch(e) {}
  };
})();
