'use strict';

/* ============================================================
   ALERTAS_GESTORA.JS — Alertas de huecos (docs/reglas-negocio.md §5)
   · Aviso cuando un RAP queda sin instructor.
   · Desplegable con candidatos tentativos (dominan el RAP y tienen
     36–39 h) para solicitarles confirmación de horas extra hasta 40 h.
   · Respuestas de los instructores (aceptan o rechazan, ver horas_extra.js).
   API: GET    /api/v1/gestora/alertas
        POST   /api/v1/gestora/alertas/{id}/solicitar-confirmacion
        DELETE /api/v1/gestora/alertas/{id}/solicitar-confirmacion
   ============================================================ */

const API_ALERTAS = '/api/v1/gestora/alertas';

const DIA_CORTO = {
  LUNES: 'Lun', MARTES: 'Mar', MIERCOLES: 'Mié', JUEVES: 'Jue', VIERNES: 'Vie',
};

let alertas = [];
let filtroEstado = 'abierta';

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

/** "MARTES 15:00-18:00" → "Mar 15:00–18:00" */
const formatearBloque = (bloque) => {
  const [dia, rango] = bloque.split(' ');
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
  const contenedor = obtenerElemento('alertas-notificaciones');
  if (!contenedor) return;

  const toast = crearElemento('div', `alertas-toast alertas-toast--${tipo}`);
  toast.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
  toast.appendChild(crearElemento('strong', '', titulo));
  if (mensaje) toast.appendChild(crearElemento('span', '', mensaje));
  contenedor.appendChild(toast);

  const remover = () => toast.remove();
  setTimeout(remover, 5000);
  toast.addEventListener('click', remover);
};

/* ── Aviso superior (notificación de huecos) ── */

const renderAviso = (resumen) => {
  const aviso = obtenerElemento('alertas-aviso');
  if (!aviso) return;

  let variante = 'ok';
  let icono = '✅';
  let texto = 'No hay RAP sin instructor. Todas las fichas están cubiertas.';

  if (resumen.abiertas > 0) {
    variante = resumen.abiertas_prioridad_alta > 0 ? 'critico' : 'aviso';
    icono = '⚠️';
    texto = `${resumen.abiertas} RAP sin instructor`;
    if (resumen.abiertas_prioridad_alta > 0) {
      texto += ` · ${resumen.abiertas_prioridad_alta} de prioridad alta (trimestres 1–5 no pueden quedar con huecos)`;
    }
    texto += '.';
  } else if (resumen.en_confirmacion > 0) {
    variante = 'aviso';
    icono = '⏳';
    texto = 'Sin huecos abiertos.';
  }
  if (resumen.en_confirmacion > 0) {
    texto += ` ${resumen.en_confirmacion} esperando confirmación del instructor.`;
  }
  if (resumen.cubiertas > 0) {
    texto += ` ${resumen.cubiertas} cubierto${resumen.cubiertas > 1 ? 's' : ''} con horas extra.`;
  }

  const icon = crearElemento('span', 'alertas-aviso__icono', icono);
  icon.setAttribute('aria-hidden', 'true');
  aviso.className = `aviso aviso--${variante} alertas-aviso`;
  aviso.replaceChildren(icon, crearElemento('p', 'alertas-aviso__texto', texto));
};

/* ── Respuestas de los instructores ── */

const textoRespuesta = (respuesta) => (respuesta.estado === 'aceptada'
  ? `✓ ${respuesta.instructor_nombre} aceptó ${formatearHoras(respuesta.horas)} extra`
  : `✕ ${respuesta.instructor_nombre} rechazó la solicitud`);

const crearRespuesta = (respuesta, clase) => {
  const item = crearElemento('li', `${clase} ${clase}--${respuesta.estado}`);
  item.appendChild(crearElemento('strong', '', textoRespuesta(respuesta)));
  if (respuesta.fecha_respuesta) {
    item.appendChild(crearElemento('span', 'alertas-respuesta__fecha', ` · ${formatearFecha(respuesta.fecha_respuesta)}`));
  }
  if (respuesta.motivo) {
    item.appendChild(crearElemento('span', 'alertas-respuesta__motivo', `“${respuesta.motivo}”`));
  }
  return item;
};

const renderRespuestasRecientes = (respuestas) => {
  const seccion = obtenerElemento('alertas-respuestas');
  const lista = obtenerElemento('alertas-respuestas-lista');
  if (!seccion || !lista) return;
  seccion.classList.toggle('hidden', respuestas.length === 0);
  lista.replaceChildren(...respuestas.map((respuesta) => {
    const item = crearRespuesta(respuesta, 'alertas-respuesta');
    item.insertBefore(
      crearElemento('span', 'alertas-respuesta__contexto', `${respuesta.rap_nombre} · Ficha ${respuesta.ficha_id}`),
      item.children[1] ?? null,
    );
    return item;
  }));
};

/* ── Tarjeta de alerta ── */

const crearDato = (termino, valor) => {
  const grupo = crearElemento('div', 'alerta__dato');
  grupo.append(crearElemento('dt', '', termino), crearElemento('dd', '', valor));
  return grupo;
};

/** Barra de carga semanal sobre el tope de 40 h (verde < 37, ámbar 37–39, rojo 40). */
const crearBarraCarga = (horas) => {
  const variante = horas >= 40 ? 'alerta' : (horas >= 37 ? 'aviso' : 'ok');
  const barra = crearElemento('span', `progreso progreso--${variante} candidato__barra`);
  barra.style.setProperty('--valor', `${Math.min(horas / 40, 1) * 100}%`);
  barra.setAttribute('role', 'img');
  barra.setAttribute('aria-label', `Carga semanal: ${formatearHoras(horas)} de 40 h`);
  barra.appendChild(crearElemento('span', 'progreso__relleno'));
  return barra;
};

const crearCandidato = (alerta, candidato) => {
  const etiqueta = crearElemento('label', 'candidato');

  const radio = crearElemento('input', 'candidato__radio');
  radio.type = 'radio';
  radio.name = `candidato-${alerta.id}`;
  radio.value = String(candidato.id);

  const cuerpo = crearElemento('span', 'candidato__cuerpo');
  cuerpo.appendChild(crearElemento('span', 'candidato__nombre', candidato.nombre));
  cuerpo.appendChild(crearElemento(
    'span',
    'candidato__carga',
    `${formatearHoras(candidato.horas_totales)} de 40 h · margen ${formatearHoras(candidato.margen_horas)}`,
  ));
  cuerpo.appendChild(crearBarraCarga(candidato.horas_totales));

  const etiquetas = crearElemento('span', 'candidato__etiquetas');
  etiquetas.appendChild(candidato.cubre_hueco
    ? crearElemento('span', 'candidato__tag candidato__tag--completo', '✓ Cubre el hueco')
    : crearElemento('span', 'candidato__tag candidato__tag--parcial',
      `◐ Cubre ${formatearHoras(candidato.horas_que_cubre)} de ${formatearHoras(alerta.horas_pendientes)}`));
  if (candidato.extra_trimestre_anterior) {
    etiquetas.appendChild(crearElemento('span', 'candidato__tag candidato__tag--equidad',
      `⚖ ${candidato.nota_equidad}`));
  }
  cuerpo.appendChild(etiquetas);

  etiqueta.append(radio, cuerpo);
  return etiqueta;
};

const crearDesplegableCandidatos = (alerta) => {
  const desplegable = crearElemento('details', 'alerta__candidatos');
  desplegable.appendChild(crearElemento(
    'summary',
    'alerta__candidatos-resumen',
    `Candidatos tentativos (${alerta.candidatos.length})`,
  ));

  if (alerta.candidatos.length === 0) {
    desplegable.appendChild(crearElemento(
      'p',
      'alerta__nota',
      alerta.prioridad === 1
        ? 'Ningún otro instructor que domine este RAP tiene margen hasta 40 h. Prioridad alta: esta ficha no puede quedar con huecos.'
        : 'Ningún otro instructor que domine este RAP tiene margen hasta 40 h. Al ser de 6.º–7.º trimestre, se permite dejar el hueco.',
    ));
    return desplegable;
  }

  const formulario = crearElemento('form', 'alerta__form');
  formulario.dataset.alertaId = String(alerta.id);

  const grupo = crearElemento('fieldset', 'candidatos');
  grupo.appendChild(crearElemento('legend', 'alertas-sr-only', `Instructor para ${alerta.rap_nombre}`));
  alerta.candidatos.forEach((candidato) => grupo.appendChild(crearCandidato(alerta, candidato)));

  const boton = crearElemento('button', 'btn btn-primary alerta__accion', 'Solicitar confirmación');
  boton.type = 'submit';
  boton.disabled = true;

  const pie = crearElemento('div', 'alerta__pie');
  pie.append(
    crearElemento('p', 'alerta__nota',
      'Instructores que dominan el RAP y ya tienen 36–39 h. Las horas extra hasta 40 h solo las autoriza la gestora; el instructor debe confirmar.'),
    boton,
  );
  formulario.append(grupo, pie);
  formulario.addEventListener('change', () => { boton.disabled = false; });
  formulario.addEventListener('submit', solicitarConfirmacion);

  desplegable.appendChild(formulario);
  return desplegable;
};

const crearBloqueSolicitud = (alerta) => {
  const bloque = crearElemento('div', 'alerta__solicitud');
  bloque.appendChild(crearElemento(
    'p',
    '',
    `⏳ ${formatearHoras(alerta.solicitud.horas)} extra solicitadas a ${alerta.solicitud.instructor_nombre} el ${formatearFecha(alerta.solicitud.fecha_solicitud)}. Esperando su respuesta.`,
  ));
  const cancelar = crearElemento('button', 'btn btn-ghost btn-xs', 'Cancelar solicitud');
  cancelar.type = 'button';
  cancelar.addEventListener('click', () => cancelarConfirmacion(alerta.id, cancelar));
  bloque.appendChild(cancelar);
  return bloque;
};

const ESTADOS_ALERTA = {
  abierta: ['abierta', 'Sin instructor'],
  confirmacion_solicitada: ['confirmacion', 'En confirmación'],
  cubierta: ['cubierta', 'Cubierto'],
};

const PILL_ESTADO = { abierta: 'alerta', confirmacion: 'info', cubierta: 'ok' };

const crearAlerta = (alerta) => {
  const abierta = alerta.estado === 'abierta';
  const [claseEstado, textoEstado] = ESTADOS_ALERTA[alerta.estado];
  const item = crearElemento('li', `alerta alerta--p${alerta.prioridad} alerta--${claseEstado}`);

  const cabecera = crearElemento('div', 'alerta__cabecera');
  cabecera.append(
    crearElemento(
      'span',
      `pill pill--${alerta.prioridad === 1 ? 'alerta' : 'aviso'} alerta-prioridad`,
      `${alerta.prioridad === 1 ? 'Prioridad alta' : 'Prioridad baja'} · Trimestre ${alerta.trimestre}`,
    ),
    crearElemento(
      'span',
      `pill pill--${PILL_ESTADO[claseEstado]} alerta-estado`,
      textoEstado,
    ),
  );

  const titulo = crearElemento('h3', 'alerta__rap', alerta.rap_nombre);
  const competencia = crearElemento('p', 'alerta__competencia',
    `${alerta.competencia_codigo} · ${alerta.competencia_nombre}`);

  const datos = crearElemento('dl', 'alerta__datos');
  datos.append(
    crearDato('Ficha', `${alerta.ficha_id} · ${alerta.jornada}`),
    crearDato('Horas', alerta.horas_pendientes < alerta.horas_requeridas
      ? `${formatearHoras(alerta.horas_pendientes)} pendientes de ${formatearHoras(alerta.horas_requeridas)}`
      : `${formatearHoras(alerta.horas_requeridas)} / semana`),
    crearDato('Bloques', alerta.bloques.map(formatearBloque).join(', ')),
  );

  item.append(cabecera, titulo, competencia, datos);
  if (alerta.respuestas.length > 0) {
    const respuestas = crearElemento('ul', 'alerta__respuestas');
    respuestas.setAttribute('aria-label', 'Respuestas de los instructores');
    alerta.respuestas.forEach((r) => respuestas.appendChild(crearRespuesta(r, 'alertas-respuesta')));
    item.appendChild(respuestas);
  }
  if (abierta) item.appendChild(crearDesplegableCandidatos(alerta));
  if (alerta.estado === 'confirmacion_solicitada') item.appendChild(crearBloqueSolicitud(alerta));
  return item;
};

/* ── Listado ── */

const MENSAJES_VACIO = {
  abierta: 'No hay alertas abiertas. 🎉',
  confirmacion_solicitada: 'No hay solicitudes de confirmación pendientes.',
  cubierta: 'Aún no hay huecos cubiertos con horas extra.',
  '': 'No hay alertas registradas.',
};

const renderCuentas = () => {
  document.querySelectorAll('[data-cuenta]').forEach((cuenta) => {
    cuenta.textContent = alertas.filter((a) => a.estado === cuenta.dataset.cuenta).length;
  });
};

const renderLista = () => {
  const lista = obtenerElemento('alertas-lista');
  const vacio = obtenerElemento('alertas-vacio');
  if (!lista || !vacio) return;

  const visibles = filtroEstado ? alertas.filter((a) => a.estado === filtroEstado) : alertas;
  lista.replaceChildren(...visibles.map(crearAlerta));
  vacio.textContent = MENSAJES_VACIO[filtroEstado];
  vacio.classList.toggle('hidden', visibles.length > 0);
};

const cargarAlertas = async () => {
  try {
    const datos = await pedirApi(API_ALERTAS);
    alertas = datos.alertas;
    renderAviso(datos.resumen);
    renderRespuestasRecientes(datos.respuestas_recientes);
    renderCuentas();
    renderLista();
  } catch (error) {
    const aviso = obtenerElemento('alertas-aviso');
    if (aviso) {
      aviso.className = 'aviso aviso--critico alertas-aviso';
      aviso.replaceChildren(crearElemento('p', 'alertas-aviso__texto', error.message));
    }
  }
};

/* ── Acciones ── */

async function solicitarConfirmacion(evento) {
  evento.preventDefault();
  const formulario = evento.currentTarget;
  const seleccionado = formulario.querySelector('input[type="radio"]:checked');
  if (!seleccionado) return;

  const boton = formulario.querySelector('button[type="submit"]');
  boton.disabled = true;
  try {
    const alerta = await pedirApi(`${API_ALERTAS}/${formulario.dataset.alertaId}/solicitar-confirmacion`, {
      method: 'POST',
      body: JSON.stringify({ instructor_id: Number(seleccionado.value) }),
    });
    mostrarToast('exito', 'Confirmación solicitada',
      `${alerta.solicitud.instructor_nombre} · ${alerta.rap_nombre} (ficha ${alerta.ficha_id})`);
    await cargarAlertas();
  } catch (error) {
    boton.disabled = false;
    mostrarToast('error', 'No se pudo solicitar', error.message);
  }
}

async function cancelarConfirmacion(alertaId, boton) {
  boton.disabled = true;
  try {
    await pedirApi(`${API_ALERTAS}/${alertaId}/solicitar-confirmacion`, { method: 'DELETE' });
    mostrarToast('info', 'Solicitud cancelada', 'La alerta vuelve a estar abierta.');
    await cargarAlertas();
  } catch (error) {
    boton.disabled = false;
    mostrarToast('error', 'No se pudo cancelar', error.message);
  }
}

/* ── Inicio ── */

const inicializar = () => {
  document.querySelectorAll('.alertas-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      filtroEstado = chip.dataset.filtro;
      document.querySelectorAll('.alertas-chip').forEach((otro) => {
        const activo = otro === chip;
        otro.classList.toggle('alertas-chip--activo', activo);
        otro.setAttribute('aria-pressed', String(activo));
      });
      renderLista();
    });
  });
  obtenerElemento('btn-actualizar')?.addEventListener('click', cargarAlertas);
  cargarAlertas();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', inicializar);
} else {
  inicializar();
}
