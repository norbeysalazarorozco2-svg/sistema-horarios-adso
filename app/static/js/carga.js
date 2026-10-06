'use strict';

/* ============================================================
   CARGA.JS — Indicador de carga horaria semanal del instructor
   Reglas (docs/reglas-negocio.md §1, umbrales en app/core/carga.py):
     · Base: 33 h de formación + 4 h administrativas = 37 h
     · Horas extra de 37 h a 40 h: solo las autoriza la gestora
     · Tope de formación: 36 h · Tope absoluto: 40 h
   API: SIPA.carga.render(contenedor, horasFormacion, horasAdministrativas)
        SIPA.carga.evaluar(horasFormacion, horasAdministrativas)
   ============================================================ */

(function () {
  const FORMACION_BASE = 33;
  const FORMACION_MAXIMA = 36;
  const ADMINISTRATIVAS = 4;
  const TOPE_SEMANAL = 40;

  const formatear = (valor) => new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 }).format(valor);

  /* El estado nunca se comunica solo con color: siempre lleva ícono y texto. */
  const evaluar = (formacion, administrativas = ADMINISTRATIVAS) => {
    const total = formacion + administrativas;
    const base = FORMACION_BASE + administrativas;

    if (total > TOPE_SEMANAL) {
      return {
        estado: 'excede', icono: '⛔', titulo: 'Excede el tope',
        texto: `Supera en ${formatear(total - TOPE_SEMANAL)} h el máximo de ${TOPE_SEMANAL} h semanales.`,
      };
    }
    if (formacion >= FORMACION_MAXIMA) {
      return {
        estado: 'tope', icono: '⚠️', titulo: 'Tope alcanzado',
        texto: `Llegó a ${FORMACION_MAXIMA} h de formación: no admite más horas esta semana.`,
      };
    }
    if (formacion >= FORMACION_BASE) {
      return {
        estado: 'rango', icono: '✅', titulo: 'En rango',
        texto: total > base
          ? `${formatear(total - base)} h sobre la base de ${base} h; las horas extra las autoriza la gestora.`
          : `Cumple la base de ${base} h semanales.`,
      };
    }
    return {
      estado: 'bajo', icono: 'ℹ️', titulo: 'Bajo la base',
      texto: `Faltan ${formatear(FORMACION_BASE - formacion)} h de formación para la base de ${FORMACION_BASE} h.`,
    };
  };

  const crear = (etiqueta, clase, texto) => {
    const elemento = document.createElement(etiqueta);
    if (clase) elemento.className = clase;
    if (texto !== undefined) elemento.textContent = texto;
    return elemento;
  };

  const porcentaje = (horas, escala) => `${Math.min(100, (horas / escala) * 100)}%`;

  const render = (contenedor, formacion, administrativas = ADMINISTRATIVAS) => {
    if (!contenedor) return;
    const horasFormacion = Number(formacion) || 0;
    const horasAdmin = Number(administrativas) || 0;
    const total = horasFormacion + horasAdmin;
    const escala = Math.max(TOPE_SEMANAL, total);
    const resultado = evaluar(horasFormacion, horasAdmin);

    const raiz = crear('div', `carga carga--${resultado.estado}`);

    const cifras = crear('p', 'carga__cifras');
    cifras.append(
      crear('strong', 'carga__total', `${formatear(total)} h`),
      crear('span', 'carga__escala', ` / ${TOPE_SEMANAL} h`),
      crear('span', 'carga__desglose',
        `${formatear(horasFormacion)} h formación + ${formatear(horasAdmin)} h administrativas`),
    );

    const barra = crear('div', 'carga__barra');
    barra.setAttribute('role', 'meter');
    barra.setAttribute('aria-valuemin', '0');
    barra.setAttribute('aria-valuemax', String(TOPE_SEMANAL));
    barra.setAttribute('aria-valuenow', String(total));
    barra.setAttribute('aria-valuetext', `${formatear(total)} de ${TOPE_SEMANAL} horas. ${resultado.titulo}`);
    barra.setAttribute('aria-label', 'Carga horaria semanal');

    const segmentoFormacion = crear('span', 'carga__segmento carga__segmento--formacion');
    segmentoFormacion.style.width = porcentaje(horasFormacion, escala);
    const segmentoAdmin = crear('span', 'carga__segmento carga__segmento--admin');
    segmentoAdmin.style.width = porcentaje(horasAdmin, escala);
    barra.append(segmentoFormacion, segmentoAdmin);

    // Una sola marca: el tope ya se lee en "/ 40 h" y es el final de la barra,
    // salvo cuando se excede (la escala crece y hay que señalar dónde estaba).
    const marcas = crear('div', 'carga__marcas');
    marcas.setAttribute('aria-hidden', 'true');
    const [horasMarca, nombreMarca] = total > TOPE_SEMANAL
      ? [TOPE_SEMANAL, 'Tope']
      : [FORMACION_BASE + horasAdmin, 'Base'];
    const marca = crear('span', 'carga__marca', `${nombreMarca} ${formatear(horasMarca)} h`);
    marca.style.left = porcentaje(horasMarca, escala);
    marcas.appendChild(marca);

    const estado = crear('p', 'carga__estado');
    estado.append(
      crear('span', 'carga__icono', resultado.icono),
      crear('strong', '', `${resultado.titulo}. `),
      crear('span', '', resultado.texto),
    );
    estado.firstChild.setAttribute('aria-hidden', 'true');

    raiz.append(cifras, barra, marcas, estado);
    contenedor.replaceChildren(raiz);
  };

  window.SIPA = Object.freeze({ ...(window.SIPA || {}), carga: Object.freeze({ evaluar, render }) });
})();
