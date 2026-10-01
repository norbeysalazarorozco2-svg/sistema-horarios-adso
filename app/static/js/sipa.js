'use strict';

/* ============================================================
   SIPA.JS — Comportamiento común de las pantallas SIPA
   Por ahora: toasts (mensajes de confirmación).
   API: SIPA.toast('Texto', 'exito' | 'info' | 'error')
   ============================================================ */

(function () {
  const DURACION_MS = 6000;
  const ICONOS = { exito: 'check-circulo', info: 'info', error: 'triangulo' };

  const crearIcono = (nombre, clase = '') => {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', `sipa-icono ${clase}`.trim());
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    const use = document.createElementNS(ns, 'use');
    use.setAttribute('href', `#i-${nombre}`);
    svg.appendChild(use);
    return svg;
  };

  const cerrar = (toast) => toast?.remove();

  const programarCierre = (toast) => {
    // Los errores permanecen hasta que el usuario los cierre.
    if (toast.classList.contains('sipa-toast--error')) return;
    window.setTimeout(() => cerrar(toast), DURACION_MS);
  };

  const toast = (texto, tipo = 'exito') => {
    const contenedor = document.getElementById('sipa-toasts');
    if (!contenedor) return null;
    const tipoValido = ICONOS[tipo] ? tipo : 'info';

    const elemento = document.createElement('div');
    elemento.className = `sipa-toast sipa-toast--${tipoValido}`;
    elemento.setAttribute('role', tipoValido === 'error' ? 'alert' : 'status');
    elemento.dataset.sipaToast = '';

    const parrafo = document.createElement('p');
    parrafo.className = 'sipa-toast__texto';
    parrafo.textContent = texto;

    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'sipa-toast__cerrar';
    boton.dataset.sipaToastCerrar = '';
    boton.setAttribute('aria-label', 'Cerrar mensaje');
    boton.appendChild(crearIcono('cerrar', 'sipa-icono--sm'));

    elemento.append(crearIcono(ICONOS[tipoValido]), parrafo, boton);
    contenedor.appendChild(elemento);
    programarCierre(elemento);
    return elemento;
  };

  document.addEventListener('click', (evento) => {
    const boton = evento.target.closest('[data-sipa-toast-cerrar]');
    if (boton) cerrar(boton.closest('[data-sipa-toast]'));
  });

  const inicializar = () => {
    document.querySelectorAll('#sipa-toasts [data-sipa-toast]').forEach(programarCierre);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializar);
  } else {
    inicializar();
  }

  window.SIPA = Object.freeze({ ...(window.SIPA || {}), toast });
})();
