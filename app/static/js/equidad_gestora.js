'use strict';

/* ============================================================
   EQUIDAD_GESTORA.JS — Historial de carga entre trimestres (§6)
   API: GET  /api/v1/gestora/equidad
        POST /api/v1/gestora/equidad/cierre
   ============================================================ */

const API_EQUIDAD = '/api/v1/gestora/equidad';

let periodoActual = '';

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

const extraerDetalle = (datos) => (typeof datos?.detail === 'string' ? datos.detail : 'Ocurrió un error en el servidor.');

const pedirApi = async (url, opciones = {}) => {
  const respuesta = await fetch(url, { headers: obtenerHeaders(), ...opciones });
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) throw new Error(extraerDetalle(datos));
  return datos;
};

const mostrarToast = (tipo, titulo, mensaje = '') => {
  const contenedor = obtenerElemento('equidad-notificaciones');
  if (!contenedor) return;
  const toast = crearElemento('div', `equidad-toast equidad-toast--${tipo}`);
  toast.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
  toast.appendChild(crearElemento('strong', '', titulo));
  if (mensaje) toast.appendChild(crearElemento('span', '', mensaje));
  contenedor.appendChild(toast);
  const remover = () => toast.remove();
  setTimeout(remover, 5000);
  toast.addEventListener('click', remover);
};

/* ── Aviso ── */

const renderAviso = (datos) => {
  const aviso = obtenerElemento('equidad-aviso');
  if (!aviso) return;
  const n = datos.a_compensar;
  const icono = crearElemento('span', 'equidad-aviso__icono', n ? '⚖️' : '✅');
  icono.setAttribute('aria-hidden', 'true');
  aviso.className = `aviso aviso--${n ? 'info' : 'ok'} equidad-aviso`;
  aviso.replaceChildren(icono, crearElemento('p', 'equidad-aviso__texto', n
    ? `${n} instructor${n > 1 ? 'es deben' : ' debe'} recibir menos carga en ${datos.periodo_actual}: llegó a 40 h con horas extra el trimestre anterior.`
    : `Nadie debe compensar carga en ${datos.periodo_actual}.`));
};

/* ── Tabla ── */

const crearCeldaCarga = (registro, enCurso = false) => {
  const celda = crearElemento('td', 'equidad-td');
  if (!registro) {
    celda.appendChild(crearElemento('span', 'equidad-vacio', '—'));
    celda.setAttribute('aria-label', 'Sin registro');
    return celda;
  }
  const valor = crearElemento(
    'span',
    `equidad-celda${registro.llego_al_tope ? ' equidad-celda--tope' : ''}${enCurso ? ' equidad-celda--curso' : ''}`,
    `${registro.llego_al_tope ? '▲ ' : ''}${formatearHoras(registro.horas_totales)}`,
  );
  celda.appendChild(valor);

  const barra = crearElemento('span',
    `progreso progreso--${registro.llego_al_tope ? 'aviso' : 'ok'} equidad-barra`);
  barra.style.setProperty('--valor', `${Math.min(registro.horas_totales / 40, 1) * 100}%`);
  barra.setAttribute('aria-hidden', 'true');
  barra.appendChild(crearElemento('span', 'progreso__relleno'));
  celda.appendChild(barra);

  if (registro.horas_extra > 0) {
    celda.appendChild(crearElemento('span', 'equidad-extra', `+${formatearHoras(registro.horas_extra).replace(' h', '')} extra`));
  }
  return celda;
};

const crearCeldaEstado = (instructor) => {
  const celda = crearElemento('td', 'equidad-td equidad-td--estado');
  const { compensacion } = instructor;
  if (compensacion) {
    celda.appendChild(crearElemento('span', 'pill pill--info equidad-estado',
      `Compensar · máx. ${formatearHoras(compensacion.carga_maxima_recomendada)}`));
    celda.appendChild(crearElemento('span', 'equidad-detalle',
      `${compensacion.periodo}: ${formatearHoras(compensacion.horas_totales)} con ${formatearHoras(compensacion.horas_extra)} extra. Sin horas extra este trimestre.`));
    if (instructor.excede_recomendacion) {
      celda.appendChild(crearElemento('span', 'equidad-detalle equidad-detalle--alerta',
        `⚠ Ya tiene ${formatearHoras(instructor.en_curso.horas_totales)} en curso.`));
    }
  } else if (instructor.es_nuevo && instructor.historial.every((r) => r === null)) {
    celda.appendChild(crearElemento('span', 'pill equidad-estado', 'Nuevo · sin historial'));
  } else {
    celda.appendChild(crearElemento('span', 'pill pill--ok equidad-estado', 'Sin restricción'));
  }
  return celda;
};

const renderTabla = (datos) => {
  const cabecera = obtenerElemento('equidad-cabecera');
  const cuerpo = obtenerElemento('equidad-cuerpo');
  if (!cabecera || !cuerpo) return;

  const fila = crearElemento('tr');
  const columnas = [
    'Instructor',
    ...datos.periodos,
    `${datos.periodo_actual} (en curso)`,
    'Este trimestre',
  ];
  columnas.forEach((texto) => {
    const th = crearElemento('th', 'equidad-th', texto);
    th.scope = 'col';
    fila.appendChild(th);
  });
  cabecera.replaceChildren(fila);

  cuerpo.replaceChildren(...datos.instructores.map((instructor) => {
    const tr = crearElemento('tr', instructor.compensacion ? 'equidad-fila--compensa' : '');
    const nombre = crearElemento('th', 'equidad-th equidad-th--fila', instructor.nombre);
    nombre.scope = 'row';
    tr.appendChild(nombre);
    instructor.historial.forEach((registro) => tr.appendChild(crearCeldaCarga(registro)));
    const curso = crearCeldaCarga(instructor.en_curso, true);
    if (instructor.en_curso_registrado) curso.appendChild(crearElemento('span', 'equidad-registrado', '✓ guardado'));
    tr.appendChild(curso);
    tr.appendChild(crearCeldaEstado(instructor));
    return tr;
  }));
};

/* ── Cierre ── */

const renderCierre = (datos) => {
  const boton = obtenerElemento('btn-cierre');
  const texto = obtenerElemento('cierre-texto');
  const registrado = datos.instructores.some((i) => i.en_curso_registrado);
  if (boton) {
    boton.disabled = false;
    boton.textContent = registrado ? `Actualizar cierre de ${datos.periodo_actual}` : `Guardar cierre de ${datos.periodo_actual}`;
  }
  if (texto) {
    texto.textContent = registrado
      ? `El cierre de ${datos.periodo_actual} ya está guardado. Si hubo cambios de carga, puedes actualizarlo.`
      : `Guarda la carga de cada instructor en su historial. El trimestre siguiente usará ${datos.periodo_actual} para la regla de equidad.`;
  }
};

const render = (datos) => {
  periodoActual = datos.periodo_actual;
  renderAviso(datos);
  renderTabla(datos);
  renderCierre(datos);
};

const cargar = async () => {
  try {
    render(await pedirApi(API_EQUIDAD));
  } catch (error) {
    const aviso = obtenerElemento('equidad-aviso');
    if (aviso) {
      aviso.className = 'aviso aviso--error equidad-aviso';
      aviso.replaceChildren(crearElemento('p', 'equidad-aviso__texto', error.message));
    }
  }
};

const guardarCierre = async () => {
  const boton = obtenerElemento('btn-cierre');
  if (boton) boton.disabled = true;
  try {
    render(await pedirApi(`${API_EQUIDAD}/cierre`, { method: 'POST' }));
    mostrarToast('exito', `Cierre de ${periodoActual} guardado`,
      'Quien haya llegado a 40 h con horas extra recibirá menos carga el trimestre siguiente.');
  } catch (error) {
    if (boton) boton.disabled = false;
    mostrarToast('error', 'No se pudo guardar el cierre', error.message);
  }
};

const inicializar = () => {
  obtenerElemento('btn-actualizar')?.addEventListener('click', cargar);
  obtenerElemento('btn-cierre')?.addEventListener('click', guardarCierre);
  cargar();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', inicializar);
} else {
  inicializar();
}
