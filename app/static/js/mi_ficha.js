'use strict';

/* ============================================================
   MI_FICHA.JS — Vista del instructor líder sobre su ficha
   Solo lectura. API: GET /api/v1/instructor/mi-ficha
   ============================================================ */

const DIAS = [
  ['LUNES', 'Lun'], ['MARTES', 'Mar'], ['MIERCOLES', 'Mié'],
  ['JUEVES', 'Jue'], ['VIERNES', 'Vie'],
];
const DIA_CORTO = Object.fromEntries(DIAS);
const JORNADA_INTERFAZ = { Diurna: 'Mañana', Nocturna: 'Noche' };

const obtenerElemento = (id) => document.getElementById(id);

const obtenerHeaders = () => {
  const token = localStorage.getItem('access_token') ?? '';
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const crearElemento = (etiqueta, clase, texto) => {
  const elemento = document.createElement(etiqueta);
  if (clase) elemento.className = clase;
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
};

const formatearRango = (rango) => rango.replace('-', '–');
const formatearHoras = (valor) => `${Number(valor).toLocaleString('es-CO', { maximumFractionDigits: 1 })} h`;
const formatearFecha = (valor) => new Date(`${valor}T00:00:00`).toLocaleDateString('es-CO', {
  day: 'numeric', month: 'short', year: 'numeric',
});
/** "MIERCOLES 09:00-12:00" → { dia, bloque } */
const separarBloque = (texto) => {
  const [dia, bloque] = texto.split(' ');
  return { dia, bloque };
};

const renderVacio = (lista, texto) => {
  lista.replaceChildren(crearElemento('li', 'mi-ficha-lista__vacio', texto));
};

/* ── Encabezado ── */

const renderEncabezado = ({ ficha, fecha_asignacion: fecha }) => {
  const subtitulo = obtenerElemento('mi-ficha-subtitulo');
  if (!subtitulo) return;
  const prioridad = crearElemento(
    'span',
    `pill pill--${ficha.prioridad === 1 ? 'alerta' : 'aviso'} mi-ficha-prioridad`,
    ficha.prioridad === 1 ? 'Prioridad alta' : 'Prioridad baja',
  );
  subtitulo.replaceChildren(
    `${ficha.programa} · Jornada ${JORNADA_INTERFAZ[ficha.jornada] ?? ficha.jornada} · Trimestre ${ficha.trimestre} `,
    prioridad,
    crearElemento('span', 'mi-ficha-desde', ` · Líder desde el ${formatearFecha(fecha)}`),
  );
};

/* ── Semana ── */

const renderSemana = (datos) => {
  const grilla = obtenerElemento('mi-ficha-grilla');
  if (!grilla) return;

  const lider = new Set(datos.bloques_lider.map(({ dia, bloque }) => `${dia}|${bloque}`));
  const huecos = new Map();
  datos.huecos.filter((h) => h.estado !== 'cubierta').forEach((hueco) => hueco.bloques.map(separarBloque).forEach(({ dia, bloque }) => {
    huecos.set(`${dia}|${bloque}`, hueco.rap_nombre);
  }));

  const encabezado = crearElemento('div', 'mi-ficha-grilla__fila');
  encabezado.setAttribute('role', 'row');
  encabezado.appendChild(crearElemento('span', 'mi-ficha-grilla__esquina'));
  DIAS.forEach(([, corto]) => {
    const dia = crearElemento('span', 'mi-ficha-grilla__dia', corto);
    dia.setAttribute('role', 'columnheader');
    encabezado.appendChild(dia);
  });

  const filas = datos.bloques_jornada.map((bloque) => {
    const fila = crearElemento('div', 'mi-ficha-grilla__fila');
    fila.setAttribute('role', 'row');
    const hora = crearElemento('span', 'mi-ficha-grilla__hora', formatearRango(bloque));
    hora.setAttribute('role', 'rowheader');
    fila.appendChild(hora);

    DIAS.forEach(([dia, corto]) => {
      const clave = `${dia}|${bloque}`;
      const celda = crearElemento('span', 'mi-ficha-grilla__celda');
      celda.setAttribute('role', 'cell');
      let descripcion = 'libre';
      if (lider.has(clave)) {
        celda.classList.add('mi-ficha-grilla__celda--lider');
        celda.textContent = '★';
        descripcion = 'tu clase de líder';
      } else if (huecos.has(clave)) {
        celda.classList.add('mi-ficha-grilla__celda--hueco');
        celda.textContent = '!';
        celda.title = huecos.get(clave);
        descripcion = `hueco sin instructor: ${huecos.get(clave)}`;
      }
      celda.setAttribute('aria-label', `${corto} ${formatearRango(bloque)}: ${descripcion}`);
      fila.appendChild(celda);
    });
    return fila;
  });

  grilla.replaceChildren(encabezado, ...filas);

  const regla = obtenerElemento('mi-ficha-regla');
  if (regla) {
    const total = datos.bloques_lider.length;
    regla.className = `mi-ficha-regla mi-ficha-regla--${datos.bloques_ideales ? 'ok' : 'aviso'}`;
    regla.textContent = datos.bloques_ideales
      ? '✓ Tienes 2 bloques seguidos el mismo día con tu ficha: lo ideal.'
      : `◐ Tienes ${total} bloque${total === 1 ? '' : 's'} con tu ficha: cumples el mínimo de una clase semanal. Lo ideal son 2 seguidos el mismo día; si quieres ajustarlo, habla con la gestora.`;
  }
};

/* ── Huecos ── */

const ESTADOS_HUECO = {
  abierta: ['abierta', 'Sin instructor'],
  confirmacion_solicitada: ['confirmacion', 'La gestora pidió confirmación'],
  cubierta: ['cubierta', 'Cubierto con horas extra'],
};

const PILL_HUECO = { abierta: 'alerta', confirmacion: 'info', cubierta: 'ok' };

const renderHuecos = (datos) => {
  const lista = obtenerElemento('mi-ficha-huecos');
  if (!lista) return;
  if (datos.huecos.length === 0) {
    renderVacio(lista, '✅ No hay RAP sin instructor en tu ficha.');
    return;
  }
  lista.replaceChildren(...datos.huecos.map((hueco) => {
    const item = crearElemento('li', 'mi-ficha-hueco');
    const [clase, texto] = ESTADOS_HUECO[hueco.estado];
    item.classList.add(`mi-ficha-hueco--${clase}`);
    item.append(
      crearElemento('span', `pill pill--${PILL_HUECO[clase]} mi-ficha-estado`, texto),
      crearElemento('strong', 'mi-ficha-hueco__rap', hueco.rap_nombre),
      crearElemento('span', 'mi-ficha-hueco__meta',
        `${hueco.competencia_nombre} · ${formatearHoras(hueco.horas_requeridas)} / semana · `
        + hueco.bloques.map(separarBloque).map(({ dia, bloque }) => `${DIA_CORTO[dia] ?? dia} ${formatearRango(bloque)}`).join(', ')),
    );
    return item;
  }));
  if (datos.ficha.prioridad === 1 && datos.huecos.some((h) => h.estado !== 'cubierta')) {
    lista.appendChild(crearElemento('li', 'mi-ficha-lista__nota',
      'Tu ficha es de prioridad alta: no puede quedar con huecos.'));
  }
};

/* ── Equipo y competencias ── */

const renderEquipo = (datos) => {
  const lista = obtenerElemento('mi-ficha-equipo');
  if (lista) {
    lista.replaceChildren(...datos.instructores.map((instructor) => {
      const item = crearElemento('li', 'mi-ficha-persona');
      item.appendChild(crearElemento('span', 'mi-ficha-persona__nombre', instructor.nombre));
      if (instructor.es_lider) item.appendChild(crearElemento('span', 'pill pill--ok mi-ficha-tag', '★ Líder (tú)'));
      return item;
    }));
  }

  const competencias = obtenerElemento('mi-ficha-competencias');
  if (competencias) {
    competencias.replaceChildren(...datos.ficha.competencias.map((c) => crearElemento('li', 'mi-ficha-chip', c)));
  }
};

/* ── Transversales ── */

const renderTransversales = (datos) => {
  const lista = obtenerElemento('mi-ficha-transversales');
  if (!lista) return;
  if (datos.transversales.length === 0) {
    const item = crearElemento('li', 'mi-ficha-lista__vacio', 'Aún no hay solicitudes para esta ficha. ');
    const enlace = crearElemento('a', '', 'Solicitarlas desde tu perfil');
    enlace.href = '/perfil-instructor#transversales-section';
    item.appendChild(enlace);
    lista.replaceChildren(item);
    return;
  }
  lista.replaceChildren(...datos.transversales.map((solicitud) => {
    const item = crearElemento('li', 'mi-ficha-transversal');
    item.append(
      crearElemento('strong', '', solicitud.transversales.join(', ')),
      crearElemento('span', 'pill mi-ficha-tag', solicitud.estado),
    );
    if (solicitud.fecha_limite) {
      item.appendChild(crearElemento('span', 'mi-ficha-hueco__meta', `Límite: ${formatearFecha(solicitud.fecha_limite)}`));
    }
    return item;
  }));
};

/* ── Carga ── */

const cargarMiFicha = async () => {
  try {
    const respuesta = await fetch('/api/v1/instructor/mi-ficha', { headers: obtenerHeaders() });
    const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos?.detail || 'No fue posible cargar tu ficha.');

    renderEncabezado(datos);
    renderSemana(datos);
    renderHuecos(datos);
    renderEquipo(datos);
    renderTransversales(datos);
  } catch (error) {
    const aviso = obtenerElemento('mi-ficha-error');
    if (aviso) {
      aviso.textContent = error.message;
      aviso.classList.remove('hidden');
    }
    obtenerElemento('mi-ficha-contenido')?.classList.add('hidden');
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', cargarMiFicha);
} else {
  cargarMiFicha();
}
