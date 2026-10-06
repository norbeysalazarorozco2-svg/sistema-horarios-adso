'use strict';

/* ============================================================
   LIDERES_GESTORA.JS — Asignación del instructor líder de ficha
   Reglas (docs/reglas-negocio.md §3 y §8):
     · Obligatorio: mínimo 1 clase a la semana con su ficha.
     · Deseable: 2 bloques seguidos, el mismo día.
     · Un instructor lidera una sola ficha; solo la gestora lo aprueba.
   API: GET    /api/v1/gestora/lideres
        PUT    /api/v1/gestora/lideres/{ficha_id}
        DELETE /api/v1/gestora/lideres/{ficha_id}
        PUT    /api/v1/gestora/lideres/{ficha_id}/ingles   (Inglés fijo)
   ============================================================ */

const API_LIDERES = '/api/v1/gestora/lideres';
const MAX_BLOQUES = 2;

const DIAS = [
  ['LUNES', 'Lun'], ['MARTES', 'Mar'], ['MIERCOLES', 'Mié'],
  ['JUEVES', 'Jue'], ['VIERNES', 'Vie'],
];
const DIA_CORTO = Object.fromEntries(DIAS);
const JORNADA_INTERFAZ = { Diurna: 'Mañana', Nocturna: 'Noche' };

let fichas = [];
let instructores = [];
let filtro = 'sin-lider';

/* Estado del panel abierto */
let fichaActiva = null;
let bloquesElegidos = new Set(); // claves "DIA|HH:MM-HH:MM"

/* Estado del panel de Inglés */
let fichaIngles = null;
let inglesElegido = null; // clave "DIA|HH:MM-HH:MM"

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

const extraerDetalle = (datos) => {
  if (typeof datos?.detail === 'string') return datos.detail;
  if (Array.isArray(datos?.detail)) {
    return datos.detail.map((item) => String(item.msg).replace(/^Value error, /, '')).join(' · ');
  }
  return 'Ocurrió un error en el servidor.';
};

const pedirApi = async (url, opciones = {}) => {
  const respuesta = await fetch(url, { headers: obtenerHeaders(), ...opciones });
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) throw new Error(extraerDetalle(datos));
  return datos;
};

const mostrarToast = (tipo, titulo, mensaje = '') => {
  const contenedor = obtenerElemento('lideres-notificaciones');
  if (!contenedor) return;

  const toast = crearElemento('div', `lideres-toast lideres-toast--${tipo}`);
  toast.setAttribute('role', tipo === 'error' ? 'alert' : 'status');
  toast.appendChild(crearElemento('strong', '', titulo));
  if (mensaje) toast.appendChild(crearElemento('span', '', mensaje));
  contenedor.appendChild(toast);

  const remover = () => toast.remove();
  setTimeout(remover, 5000);
  toast.addEventListener('click', remover);
};

const nombreJornada = (jornada) => JORNADA_INTERFAZ[jornada] ?? jornada;
const formatearRango = (bloque) => bloque.replace('-', '–');
const formatearBloque = ({ dia, bloque }) => `${DIA_CORTO[dia] ?? dia} ${formatearRango(bloque)}`;
const nombreInstructor = (id) => instructores.find((i) => i.id === id)?.nombre ?? `Instructor ${id}`;

/* ── Regla de los bloques (obligatorio 1, deseable 2 seguidos el mismo día) ── */

const aMinutos = (hora) => {
  const [h, m] = hora.split(':').map(Number);
  return h * 60 + m;
};

/** @param {Array<{dia:string, bloque:string}>} bloques */
const evaluarBloques = (bloques) => {
  if (bloques.length === 0) {
    return { nivel: 'error', icono: '✕', texto: 'Elige al menos 1 bloque: el líder debe tener mínimo una clase semanal con su ficha.' };
  }
  if (bloques.length === 1) {
    return { nivel: 'aviso', icono: '◐', texto: 'Cumple el mínimo. Lo deseable son 2 bloques seguidos el mismo día.' };
  }
  const [a, b] = [...bloques].sort((x, y) => aMinutos(x.bloque) - aMinutos(y.bloque));
  const seguidos = a.dia === b.dia && aMinutos(a.bloque.split('-')[1]) === aMinutos(b.bloque.split('-')[0]);
  return seguidos
    ? { nivel: 'ok', icono: '✓', texto: 'Ideal: 2 bloques seguidos el mismo día.' }
    : { nivel: 'aviso', icono: '◐', texto: 'Válido, pero lo deseable es que los 2 bloques sean seguidos el mismo día.' };
};

const crearRegla = (bloques, clase = 'lider-regla') => {
  const resultado = evaluarBloques(bloques);
  const nodo = crearElemento('span', `${clase} ${clase}--${resultado.nivel}`);
  const icono = crearElemento('span', '', resultado.icono);
  icono.setAttribute('aria-hidden', 'true');
  nodo.append(icono, ` ${resultado.texto}`);
  return nodo;
};

/* ── Aviso superior ── */

const renderAviso = (resumen) => {
  const aviso = obtenerElemento('lideres-aviso');
  if (!aviso) return;
  const pendientes = resumen.sin_lider;
  const icono = crearElemento('span', 'lideres-aviso__icono', pendientes ? '⚠️' : '✅');
  icono.setAttribute('aria-hidden', 'true');
  aviso.className = `aviso aviso--${pendientes ? 'aviso' : 'ok'} lideres-aviso`;
  aviso.replaceChildren(icono, crearElemento(
    'p',
    'lideres-aviso__texto',
    pendientes
      ? `${pendientes} de ${resumen.total_fichas} fichas sin líder asignado.`
      : `Las ${resumen.total_fichas} fichas tienen líder asignado.`,
  ));
};

/* ── Lista de fichas ── */

const crearFicha = (ficha) => {
  const item = crearElemento('li', `lider-ficha${ficha.lider ? '' : ' lider-ficha--sin-lider'}`);

  const info = crearElemento('div', 'lider-ficha__info');
  const cabecera = crearElemento('div', 'lider-ficha__cabecera');
  cabecera.append(
    crearElemento('h3', 'lider-ficha__titulo', `Ficha ${ficha.id}`),
    crearElemento(
      'span',
      `pill pill--${ficha.prioridad === 1 ? 'alerta' : 'aviso'} lider-prioridad`,
      `${ficha.prioridad === 1 ? 'Prioridad alta' : 'Prioridad baja'} · Trimestre ${ficha.trimestre}`,
    ),
  );
  info.append(cabecera, crearElemento('p', 'lider-ficha__meta', `${ficha.programa} · ${nombreJornada(ficha.jornada)}`));

  const ingles = crearElemento('p', 'lider-ficha__ingles');
  ingles.appendChild(crearElemento(
    'span',
    '',
    ficha.bloque_ingles ? `🔒 Inglés · ${formatearBloque(ficha.bloque_ingles)} · cada semana` : '🔒 Inglés sin franja',
  ));
  const moverIngles = crearElemento('button', 'btn btn-ghost btn-xs', ficha.bloque_ingles ? 'Mover' : 'Fijar');
  moverIngles.type = 'button';
  moverIngles.setAttribute('aria-label', `Mover el Inglés de la ficha ${ficha.id}`);
  moverIngles.addEventListener('click', () => abrirIngles(ficha));
  ingles.appendChild(moverIngles);
  info.appendChild(ingles);

  const estado = crearElemento('div', 'lider-ficha__estado');
  if (ficha.lider) {
    estado.append(
      crearElemento('p', 'lider-ficha__lider', `★ ${ficha.lider.instructor_nombre}`),
      crearElemento('p', 'lider-ficha__bloques', ficha.lider.bloques.map(formatearBloque).join(' · ')),
      crearRegla(ficha.lider.bloques, 'lider-etiqueta'),
    );
  } else {
    estado.appendChild(crearElemento('span', 'pill pill--alerta', 'Sin líder asignado'));
  }

  const boton = crearElemento('button', `btn ${ficha.lider ? 'btn-secondary' : 'btn-primary'} lider-ficha__accion`,
    ficha.lider ? 'Cambiar' : 'Asignar líder');
  boton.type = 'button';
  boton.addEventListener('click', () => abrirPanel(ficha));

  item.append(info, estado, boton);
  return item;
};

const renderLista = () => {
  const lista = obtenerElemento('lideres-lista');
  const vacio = obtenerElemento('lideres-vacio');
  if (!lista || !vacio) return;

  const visibles = filtro === 'sin-lider' ? fichas.filter((f) => !f.lider) : fichas;
  lista.replaceChildren(...visibles.map(crearFicha));
  vacio.textContent = filtro === 'sin-lider' ? 'Todas las fichas tienen líder. 🎉' : 'No hay fichas registradas.';
  vacio.classList.toggle('hidden', visibles.length > 0);
};

const cargarLideres = async () => {
  try {
    const datos = await pedirApi(API_LIDERES);
    fichas = datos.fichas;
    instructores = datos.instructores;
    renderAviso(datos.resumen);
    renderLista();
  } catch (error) {
    const aviso = obtenerElemento('lideres-aviso');
    if (aviso) {
      aviso.className = 'aviso aviso--error lideres-aviso';
      aviso.replaceChildren(crearElemento('p', 'lideres-aviso__texto', error.message));
    }
  }
};

/* ── Panel de asignación ── */

const bloquesComoLista = () => [...bloquesElegidos].map((clave) => {
  const [dia, bloque] = clave.split('|');
  return { dia, bloque };
});

const instructorElegido = () => {
  const radio = document.querySelector('#lider-instructores input:checked');
  return radio ? Number(radio.value) : null;
};

/* Los toasts quedan detrás del <dialog> modal: los errores del panel se muestran dentro. */
const mostrarErrorPanel = (mensaje = '') => {
  const error = obtenerElemento('lider-error');
  if (!error) return;
  error.textContent = mensaje;
  error.classList.toggle('hidden', !mensaje);
};

const actualizarEstadoPanel = () => {
  const bloques = bloquesComoLista();
  obtenerElemento('lider-regla')?.replaceChildren(crearRegla(bloques));
  const guardar = obtenerElemento('lider-guardar');
  if (guardar) guardar.disabled = instructorElegido() === null || bloques.length === 0;
};

const crearOpcionInstructor = (ficha, instructor) => {
  const liderActual = ficha.lider?.instructor_id;
  const lideraOtra = instructor.lidera_ficha_id !== null && instructor.lidera_ficha_id !== ficha.id;

  const etiqueta = crearElemento('label', `lider-opcion${lideraOtra ? ' lider-opcion--bloqueada' : ''}`);
  const radio = crearElemento('input');
  radio.type = 'radio';
  radio.name = 'lider-instructor';
  radio.value = String(instructor.id);
  radio.checked = instructor.id === liderActual;
  radio.disabled = lideraOtra;

  const cuerpo = crearElemento('span', 'lider-opcion__cuerpo');
  cuerpo.appendChild(crearElemento('span', 'lider-opcion__nombre', instructor.nombre));
  const tags = crearElemento('span', 'lider-opcion__tags');
  if (ficha.instructor_ids.includes(instructor.id)) {
    tags.appendChild(crearElemento('span', 'lider-tag lider-tag--ficha', 'Ya dicta en esta ficha'));
  }
  if (instructor.es_nuevo) {
    tags.appendChild(crearElemento('span', 'lider-tag lider-tag--nuevo', 'Instructor nuevo'));
  }
  if (lideraOtra) {
    tags.appendChild(crearElemento('span', 'lider-tag lider-tag--bloqueo', `Ya lidera la ficha ${instructor.lidera_ficha_id}`));
  }
  cuerpo.appendChild(tags);

  etiqueta.append(radio, cuerpo);
  return etiqueta;
};

const renderInstructores = (ficha) => {
  const contenedor = obtenerElemento('lider-instructores');
  if (!contenedor) return;
  // Primero quienes ya dictan en la ficha; al final quienes ya lideran otra.
  const orden = (i) => [
    i.lidera_ficha_id !== null && i.lidera_ficha_id !== ficha.id,
    !ficha.instructor_ids.includes(i.id),
    i.nombre,
  ];
  const ordenados = [...instructores].sort((a, b) => {
    const [x, y] = [orden(a), orden(b)];
    return (x[0] - y[0]) || (x[1] - y[1]) || x[2].localeCompare(y[2]);
  });
  contenedor.replaceChildren(...ordenados.map((i) => crearOpcionInstructor(ficha, i)));
};

const alternarBloque = (boton, clave) => {
  if (bloquesElegidos.has(clave)) {
    bloquesElegidos.delete(clave);
  } else {
    if (bloquesElegidos.size >= MAX_BLOQUES) {
      mostrarErrorPanel(`Máximo ${MAX_BLOQUES} bloques: quita uno antes de elegir otro.`);
      return;
    }
    bloquesElegidos.add(clave);
  }
  boton.setAttribute('aria-pressed', String(bloquesElegidos.has(clave)));
  mostrarErrorPanel();
  actualizarEstadoPanel();
};

const renderGrilla = (ficha) => {
  const grilla = obtenerElemento('lider-grilla');
  if (!grilla) return;
  grilla.style.setProperty('--lider-columnas', DIAS.length);

  const celdas = [crearElemento('span', 'lider-grilla__esquina')];
  DIAS.forEach(([, corto]) => celdas.push(crearElemento('span', 'lider-grilla__dia', corto)));

  const ingles = ficha.bloque_ingles ? `${ficha.bloque_ingles.dia}|${ficha.bloque_ingles.bloque}` : null;

  ficha.bloques_permitidos.forEach((bloque) => {
    celdas.push(crearElemento('span', 'lider-grilla__hora', formatearRango(bloque)));
    DIAS.forEach(([dia, corto]) => {
      const clave = `${dia}|${bloque}`;
      if (clave === ingles) {
        const fija = crearElemento('span', 'lider-grilla__celda lider-grilla__celda--ingles', 'Inglés');
        fija.title = 'Inglés fijo de la ficha: bloqueado';
        fija.setAttribute('aria-label', `${corto} ${formatearRango(bloque)}: Inglés fijo, bloqueado`);
        celdas.push(fija);
        return;
      }
      const boton = crearElemento('button', 'lider-grilla__celda');
      boton.type = 'button';
      boton.setAttribute('aria-pressed', String(bloquesElegidos.has(clave)));
      boton.setAttribute('aria-label', `${corto} ${formatearRango(bloque)}`);
      boton.addEventListener('click', () => alternarBloque(boton, clave));
      celdas.push(boton);
    });
  });
  grilla.replaceChildren(...celdas);
};

const abrirPanel = (ficha) => {
  fichaActiva = ficha;
  bloquesElegidos = new Set((ficha.lider?.bloques ?? []).map(({ dia, bloque }) => `${dia}|${bloque}`));

  obtenerElemento('lider-dialogo-titulo').textContent = `Líder de la ficha ${ficha.id}`;
  obtenerElemento('lider-dialogo-subtitulo').textContent =
    `${ficha.programa} · Jornada ${nombreJornada(ficha.jornada)} · Trimestre ${ficha.trimestre}`;
  obtenerElemento('lider-quitar').classList.toggle('hidden', !ficha.lider);

  mostrarErrorPanel();
  renderInstructores(ficha);
  renderGrilla(ficha);
  actualizarEstadoPanel();
  obtenerElemento('lider-dialogo').showModal();
};

const cerrarPanel = () => {
  obtenerElemento('lider-dialogo')?.close();
  fichaActiva = null;
};

const guardarLider = async (evento) => {
  evento.preventDefault();
  const instructorId = instructorElegido();
  if (!fichaActiva || instructorId === null || bloquesElegidos.size === 0) return;

  const boton = obtenerElemento('lider-guardar');
  boton.disabled = true;
  try {
    const ficha = await pedirApi(`${API_LIDERES}/${fichaActiva.id}`, {
      method: 'PUT',
      body: JSON.stringify({ instructor_id: instructorId, bloques: bloquesComoLista() }),
    });
    mostrarToast('exito', 'Líder asignado', `${nombreInstructor(instructorId)} lidera la ficha ${ficha.id}.`);
    cerrarPanel();
    await cargarLideres();
  } catch (error) {
    boton.disabled = false;
    mostrarErrorPanel(error.message);
  }
};

const quitarLider = async () => {
  if (!fichaActiva) return;
  const fichaId = fichaActiva.id;
  try {
    await pedirApi(`${API_LIDERES}/${fichaId}`, { method: 'DELETE' });
    mostrarToast('info', 'Líder retirado', `La ficha ${fichaId} queda sin líder.`);
    cerrarPanel();
    await cargarLideres();
  } catch (error) {
    mostrarErrorPanel(error.message);
  }
};

/* ── Panel del Inglés fijo ── */

const claveDe = ({ dia, bloque }) => `${dia}|${bloque}`;

const mostrarErrorIngles = (mensaje = '') => {
  const error = obtenerElemento('ingles-error');
  if (!error) return;
  error.textContent = mensaje;
  error.classList.toggle('hidden', !mensaje);
};

const renderGrillaIngles = (ficha) => {
  const grilla = obtenerElemento('ingles-grilla');
  if (!grilla) return;
  grilla.style.setProperty('--lider-columnas', DIAS.length);

  // No se pueden usar: los bloques del líder de esta ficha ni el Inglés de otras
  // fichas del mismo trimestre (el horario consolidado muestra una por celda).
  const delLider = new Set((ficha.lider?.bloques ?? []).map(claveDe));
  const deOtras = new Map(fichas
    .filter((f) => f.id !== ficha.id && f.trimestre === ficha.trimestre && f.bloque_ingles)
    .map((f) => [claveDe(f.bloque_ingles), f.id]));
  const actual = ficha.bloque_ingles ? claveDe(ficha.bloque_ingles) : null;

  const celdas = [crearElemento('span', 'lider-grilla__esquina')];
  DIAS.forEach(([, corto]) => celdas.push(crearElemento('span', 'lider-grilla__dia', corto)));

  ficha.bloques_permitidos.forEach((bloque) => {
    celdas.push(crearElemento('span', 'lider-grilla__hora', formatearRango(bloque)));
    DIAS.forEach(([dia, corto]) => {
      const clave = `${dia}|${bloque}`;
      const etiqueta = `${corto} ${formatearRango(bloque)}`;
      if (delLider.has(clave) || deOtras.has(clave)) {
        const motivo = delLider.has(clave) ? 'Líder' : `Ficha ${deOtras.get(clave)}`;
        const ocupada = crearElemento('span', 'lider-grilla__celda lider-grilla__celda--ocupada', motivo);
        ocupada.title = delLider.has(clave) ? 'Bloque del líder de la ficha' : `Inglés de la ficha ${deOtras.get(clave)}`;
        ocupada.setAttribute('aria-label', `${etiqueta}: ocupado (${ocupada.title.toLowerCase()})`);
        celdas.push(ocupada);
        return;
      }
      const boton = crearElemento('button', 'lider-grilla__celda');
      boton.type = 'button';
      boton.setAttribute('role', 'radio');
      boton.setAttribute('aria-checked', String(clave === inglesElegido));
      boton.setAttribute('aria-pressed', String(clave === inglesElegido));
      boton.setAttribute('aria-label', etiqueta);
      boton.addEventListener('click', () => {
        inglesElegido = clave;
        mostrarErrorIngles();
        renderGrillaIngles(ficha);
        obtenerElemento('ingles-guardar').disabled = clave === actual;
      });
      celdas.push(boton);
    });
  });
  grilla.replaceChildren(...celdas);
};

const abrirIngles = (ficha) => {
  fichaIngles = ficha;
  inglesElegido = ficha.bloque_ingles ? claveDe(ficha.bloque_ingles) : null;
  const jornada = nombreJornada(ficha.jornada);

  obtenerElemento('ingles-dialogo-titulo').textContent = `Inglés de la ficha ${ficha.id}`;
  obtenerElemento('ingles-dialogo-subtitulo').textContent =
    `${ficha.programa} · Jornada ${jornada} · Trimestre ${ficha.trimestre}`;
  obtenerElemento('ingles-ayuda').textContent =
    `Elige un bloque de la jornada ${jornada}: ${jornada === 'Noche' ? '2 h' : '3 h'} de Inglés que se repiten todas las semanas del trimestre.`;
  obtenerElemento('ingles-guardar').disabled = true;

  mostrarErrorIngles();
  renderGrillaIngles(ficha);
  obtenerElemento('ingles-dialogo').showModal();
};

const cerrarIngles = () => {
  obtenerElemento('ingles-dialogo')?.close();
  fichaIngles = null;
};

const guardarIngles = async (evento) => {
  evento.preventDefault();
  if (!fichaIngles || !inglesElegido) return;
  const [dia, bloque] = inglesElegido.split('|');

  const boton = obtenerElemento('ingles-guardar');
  boton.disabled = true;
  try {
    const ficha = await pedirApi(`${API_LIDERES}/${fichaIngles.id}/ingles`, {
      method: 'PUT',
      body: JSON.stringify({ dia, bloque }),
    });
    mostrarToast('exito', 'Inglés actualizado', `Ficha ${ficha.id}: ${formatearBloque(ficha.bloque_ingles)}.`);
    cerrarIngles();
    await cargarLideres();
  } catch (error) {
    boton.disabled = false;
    mostrarErrorIngles(error.message);
  }
};

/* ── Inicio ── */

const inicializar = () => {
  document.querySelectorAll('.lideres-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      filtro = chip.dataset.filtro;
      document.querySelectorAll('.lideres-chip').forEach((otro) => {
        const activo = otro === chip;
        otro.classList.toggle('lideres-chip--activo', activo);
        otro.setAttribute('aria-pressed', String(activo));
      });
      renderLista();
    });
  });

  obtenerElemento('btn-actualizar')?.addEventListener('click', cargarLideres);
  obtenerElemento('lider-form')?.addEventListener('submit', guardarLider);
  obtenerElemento('lider-instructores')?.addEventListener('change', actualizarEstadoPanel);
  obtenerElemento('lider-quitar')?.addEventListener('click', quitarLider);
  obtenerElemento('ingles-form')?.addEventListener('submit', guardarIngles);
  document.querySelectorAll('[data-cerrar]').forEach((b) => b.addEventListener(
    'click',
    () => (b.closest('#ingles-dialogo') ? cerrarIngles() : cerrarPanel()),
  ));

  cargarLideres();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', inicializar);
} else {
  inicializar();
}
