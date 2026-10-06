'use strict';

/* ============================================================
   HORAS_EXTRA.JS — Solicitudes de horas extra para el instructor
   (docs/reglas-negocio.md §5). El instructor acepta o rechaza; la
   respuesta aparece en las alertas de la gestora.
   API: GET  /api/v1/instructor/horas-extra
        POST /api/v1/instructor/horas-extra/{id}/respuesta
   ============================================================ */

const API_HORAS_EXTRA = '/api/v1/instructor/horas-extra';

const DIA_CORTO = {
  LUNES: 'Lun', MARTES: 'Mar', MIERCOLES: 'Mié', JUEVES: 'Jue', VIERNES: 'Vie',
};
const JORNADA_INTERFAZ = { Diurna: 'Mañana', Nocturna: 'Noche' };

const ESTADOS_HISTORIAL = {
  aceptada: ['✓', 'Aceptada'],
  rechazada: ['✕', 'Rechazada'],
  cancelada: ['⊘', 'Cancelada por la gestora'],
};

/* ── Utilidades ── */

const obtenerElemento = (id) => document.getElementById(id);

const obtenerHeaders = () => {
  const token = localStorage.getItem('access_token') ?? '';
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

const crearElemento = (etiqueta, clase, texto) => {
  const elemento = document.createElement(etiqueta);
  if (clase) elemento.className = clase;
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
};

const formatearHoras = (valor) => `${Number(valor).toLocaleString('es-CO', { maximumFractionDigits: 1 })} h`;
const formatearFecha = (valor) => new Date(`${valor}T00:00:00`).toLocaleDateString('es-CO', {
  day: 'numeric', month: 'short',
});
const formatearBloque = (texto) => {
  const [dia, rango] = texto.split(' ');
  return `${DIA_CORTO[dia] ?? dia} ${rango.replace('-', '–')}`;
};

const extraerDetalle = (datos) => {
  if (typeof datos?.detail === 'string') return datos.detail;
  if (Array.isArray(datos?.detail)) return datos.detail.map((item) => item.msg).join(' · ');
  return 'Ocurrió un error en el servidor.';
};

const pedirApi = async (url, opciones = {}) => {
  const respuesta = await fetch(url, { headers: obtenerHeaders(), ...opciones });
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) throw new Error(extraerDetalle(datos));
  return datos;
};

const mostrarToast = (tipo, titulo, mensaje = '') => {
  const contenedor = obtenerElemento('horas-extra-notificaciones');
  if (!contenedor) return;
  const toast = crearElemento('div', `horas-extra-toast horas-extra-toast--${tipo}`);
  toast.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
  toast.appendChild(crearElemento('strong', '', titulo));
  if (mensaje) toast.appendChild(crearElemento('span', '', mensaje));
  contenedor.appendChild(toast);
  const remover = () => toast.remove();
  setTimeout(remover, 5000);
  toast.addEventListener('click', remover);
};

/* ── Carga ── */

const renderCarga = (carga, compensacion) => {
  const contenedor = obtenerElemento('horas-extra-carga');
  if (!contenedor) return;
  window.SIPA?.carga?.render(contenedor, carga.horas_formacion + carga.horas_extra_aceptadas, carga.horas_administrativas);
  if (carga.horas_extra_aceptadas > 0) {
    contenedor.appendChild(crearElemento('p', 'horas-extra-nota',
      `Incluye ${formatearHoras(carga.horas_extra_aceptadas)} extra que ya aceptaste.`));
  }
  if (compensacion) {
    // Regla de equidad (§6): este trimestre le corresponde menos carga.
    contenedor.appendChild(crearElemento('p', 'horas-extra-equidad',
      `⚖ En ${compensacion.periodo} llegaste a ${formatearHoras(compensacion.horas_totales)} con horas extra. `
      + `Por equidad, este trimestre te corresponde como máximo ${formatearHoras(compensacion.carga_maxima_recomendada)}: `
      + 'puedes rechazar nuevas solicitudes de horas extra.'));
  }
};

/* ── Pendientes ── */

const crearDato = (termino, valor) => {
  const grupo = crearElemento('div', 'horas-extra-dato');
  grupo.append(crearElemento('dt', '', termino), crearElemento('dd', '', valor));
  return grupo;
};

const crearPanelRechazo = (solicitud, acciones) => {
  const panel = crearElemento('form', 'horas-extra-rechazo hidden');
  const id = `motivo-${solicitud.id}`;
  const etiqueta = crearElemento('label', 'form-label', 'Motivo (opcional; la gestora lo verá)');
  etiqueta.htmlFor = id;
  const motivo = crearElemento('textarea', 'form-input');
  motivo.id = id;
  motivo.rows = 2;
  motivo.maxLength = 300;
  motivo.placeholder = 'Ej.: ese día dicto en otra sede.';

  const botones = crearElemento('div', 'horas-extra-acciones');
  const confirmar = crearElemento('button', 'btn btn-danger btn-xs', 'Confirmar rechazo');
  confirmar.type = 'submit';
  const volver = crearElemento('button', 'btn btn-ghost btn-xs', 'Volver');
  volver.type = 'button';
  volver.addEventListener('click', () => {
    panel.classList.add('hidden');
    acciones.classList.remove('hidden');
  });
  botones.append(volver, confirmar);

  panel.append(etiqueta, motivo, botones);
  panel.addEventListener('submit', (evento) => {
    evento.preventDefault();
    responder(solicitud, false, motivo.value, confirmar);
  });
  return panel;
};

const crearPendiente = (solicitud, carga) => {
  const item = crearElemento('li', `horas-extra-solicitud horas-extra-solicitud--p${solicitud.prioridad}`);

  const cabecera = crearElemento('div', 'horas-extra-solicitud__cabecera');
  cabecera.append(
    crearElemento('span', `horas-extra-prioridad horas-extra-prioridad--${solicitud.prioridad === 1 ? 'alta' : 'baja'}`,
      `${solicitud.prioridad === 1 ? '▲ Prioridad alta' : '▽ Prioridad baja'} · Trimestre ${solicitud.trimestre}`),
    crearElemento('span', 'horas-extra-fecha', `Solicitada el ${formatearFecha(solicitud.fecha_solicitud)}`),
  );

  const datos = crearElemento('dl', 'horas-extra-datos');
  datos.append(
    crearDato('Ficha', `${solicitud.ficha_id} · ${JORNADA_INTERFAZ[solicitud.jornada] ?? solicitud.jornada}`),
    crearDato('Bloques', solicitud.bloques.map(formatearBloque).join(', ')),
    crearDato('Horas extra', formatearHoras(solicitud.horas)),
  );

  const impacto = crearElemento('p', `horas-extra-impacto${solicitud.puede_aceptar ? '' : ' horas-extra-impacto--bloqueado'}`);
  impacto.append(
    'Tu carga pasaría de ',
    crearElemento('strong', '', formatearHoras(carga.horas_totales)),
    ' a ',
    crearElemento('strong', '', formatearHoras(solicitud.horas_totales_con_extra)),
    ' de 40 h.',
  );

  const acciones = crearElemento('div', 'horas-extra-acciones');
  const aceptar = crearElemento('button', 'btn btn-primary', `Aceptar ${formatearHoras(solicitud.horas)} extra`);
  aceptar.type = 'button';
  aceptar.disabled = !solicitud.puede_aceptar;
  aceptar.addEventListener('click', () => responder(solicitud, true, '', aceptar));
  const rechazar = crearElemento('button', 'btn btn-secondary', 'Rechazar');
  rechazar.type = 'button';
  acciones.append(rechazar, aceptar);

  const panelRechazo = crearPanelRechazo(solicitud, acciones);
  rechazar.addEventListener('click', () => {
    acciones.classList.add('hidden');
    panelRechazo.classList.remove('hidden');
    panelRechazo.querySelector('textarea')?.focus();
  });

  item.append(
    cabecera,
    crearElemento('h3', 'horas-extra-solicitud__rap', solicitud.rap_nombre),
    crearElemento('p', 'horas-extra-solicitud__competencia', solicitud.competencia_nombre),
    datos,
    impacto,
  );
  if (solicitud.motivo_bloqueo) {
    item.appendChild(crearElemento('p', 'horas-extra-bloqueo', `⛔ ${solicitud.motivo_bloqueo}`));
  }
  item.append(
    crearElemento('p', 'horas-extra-nota',
      'La gestora ya autorizó estas horas al pedírtelas. Si aceptas, el hueco queda asignado a ti y ella recibe tu confirmación.'),
    acciones,
    panelRechazo,
  );
  return item;
};

const renderPendientes = (bandeja) => {
  const lista = obtenerElemento('horas-extra-pendientes');
  if (!lista) return;
  if (bandeja.pendientes.length === 0) {
    lista.replaceChildren(crearElemento('li', 'horas-extra-vacio', '✅ No tienes solicitudes pendientes.'));
    return;
  }
  lista.replaceChildren(...bandeja.pendientes.map((s) => crearPendiente(s, bandeja.carga)));
};

/* ── Historial ── */

const renderHistorial = (bandeja) => {
  const lista = obtenerElemento('horas-extra-historial');
  if (!lista) return;
  if (bandeja.historial.length === 0) {
    lista.replaceChildren(crearElemento('li', 'horas-extra-vacio', 'Aún no has respondido solicitudes.'));
    return;
  }
  lista.replaceChildren(...bandeja.historial.map((solicitud) => {
    const [icono, texto] = ESTADOS_HISTORIAL[solicitud.estado] ?? ['•', solicitud.estado];
    const item = crearElemento('li', 'horas-extra-fila');
    item.append(
      crearElemento('span', `horas-extra-estado horas-extra-estado--${solicitud.estado}`, `${icono} ${texto}`),
      crearElemento('span', 'horas-extra-fila__texto',
        `${solicitud.rap_nombre} · Ficha ${solicitud.ficha_id} · ${formatearHoras(solicitud.horas)}`),
      crearElemento('span', 'horas-extra-fecha',
        solicitud.fecha_respuesta ? formatearFecha(solicitud.fecha_respuesta) : ''),
    );
    if (solicitud.motivo) {
      item.appendChild(crearElemento('span', 'horas-extra-fila__motivo', `“${solicitud.motivo}”`));
    }
    return item;
  }));
};

const render = (bandeja) => {
  renderCarga(bandeja.carga, bandeja.compensacion);
  renderPendientes(bandeja);
  renderHistorial(bandeja);
};

/* ── Acciones ── */

async function responder(solicitud, acepta, motivo, boton) {
  boton.disabled = true;
  try {
    const bandeja = await pedirApi(`${API_HORAS_EXTRA}/${solicitud.id}/respuesta`, {
      method: 'POST',
      body: JSON.stringify({ acepta, motivo }),
    });
    render(bandeja);
    mostrarToast(
      acepta ? 'exito' : 'info',
      acepta ? 'Horas extra aceptadas' : 'Solicitud rechazada',
      `La gestora ya ve tu respuesta para ${solicitud.rap_nombre} (ficha ${solicitud.ficha_id}).`,
    );
  } catch (error) {
    boton.disabled = false;
    mostrarToast('error', 'No se pudo enviar tu respuesta', error.message);
    cargar();
  }
}

const cargar = async () => {
  try {
    render(await pedirApi(API_HORAS_EXTRA));
  } catch (error) {
    const aviso = obtenerElemento('horas-extra-error');
    if (aviso) {
      aviso.textContent = error.message;
      aviso.classList.remove('hidden');
    }
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', cargar);
} else {
  cargar();
}
