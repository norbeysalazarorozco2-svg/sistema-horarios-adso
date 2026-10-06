'use strict';

/* ============================================================
   PERFIL_GESTORA.JS — Vista independiente de la Gestora
   Acciones: Solicitudes · Consultas: Trimestres, Fichas, Instructores, Jornadas
   ============================================================ */

const obtenerElemento = (id) => document.getElementById(id);
const obtenerToken = () => localStorage.getItem('access_token') ?? '';

const obtenerHeaders = () => {
  const token = obtenerToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

let solicitudes = [];
let trimestre = 1;
let filtroEstado = '';
let filtroJornada = 'todas';

const formatearNumero = (valor) => Number(valor).toLocaleString('es-CO', {
  maximumFractionDigits: 1,
});

const formatearFecha = (valor) => {
  if (!valor) return '—';
  const fecha = new Date(`${String(valor).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(fecha.getTime())) return String(valor);
  return fecha.toLocaleDateString('es-CO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
};

const extraerDetalle = (datos) => {
  if (typeof datos?.detail === 'string') return datos.detail;
  if (Array.isArray(datos?.detail)) {
    return datos.detail.map((item) => item.msg).filter(Boolean).join(' · ');
  }
  return 'Ocurrió un error en el servidor.';
};

const crearElemento = (etiqueta, clase, texto) => {
  const elemento = document.createElement(etiqueta);
  if (clase) elemento.className = clase;
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
};

/* ── Notificaciones ── */

const mostrarToast = (tipo, titulo, mensaje = '') => {
  const contenedor = obtenerElemento('gestora-notifications');
  if (!contenedor) return;

  const toast = crearElemento('div', `gestora-toast gestora-toast--${tipo}`);
  toast.setAttribute('role', 'alert');

  const contenido = crearElemento('div');
  contenido.appendChild(crearElemento('strong', '', titulo));
  if (mensaje) contenido.appendChild(crearElemento('div', '', mensaje));
  toast.appendChild(contenido);
  contenedor.appendChild(toast);

  const remover = () => {
    toast.classList.add('removing');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  };
  setTimeout(remover, 5000);
  toast.addEventListener('click', remover);
};

const mostrarError = (mensaje) => {
  const error = obtenerElemento('gestora-error');
  if (!error) return;
  error.textContent = mensaje;
  error.hidden = !mensaje;
};

const ocultarError = () => {
  const error = obtenerElemento('gestora-error');
  if (error) {
    error.textContent = '';
    error.hidden = true;
  }
};

/* ── Peticiones ── */

const pedir = async (ruta) => {
  const respuesta = await fetch(ruta, {
    headers: obtenerHeaders(),
    credentials: 'same-origin',
  });
  const datos = await respuesta.json().catch(() => null);
  if (respuesta.status === 401) {
    window.location.href = '/auth/login';
    throw new Error('Tu sesión expiró.');
  }
  if (!respuesta.ok) throw new Error(extraerDetalle(datos));
  return datos;
};

/* ── Encabezado y acción de solicitudes ── */

const renderResumen = (perfil) => {
  const nombre = obtenerElemento('gestora-nombre');
  const correo = obtenerElemento('gestora-correo');
  const trimestreBadge = obtenerElemento('gestora-trimestre-badge');
  const pendientes = obtenerElemento('accion-solicitudes-total');
  const vencidas = obtenerElemento('accion-solicitudes-vencidas');

  if (nombre) nombre.textContent = perfil.nombre;
  if (correo) correo.textContent = perfil.correo_sena || 'Correo no registrado';
  if (trimestreBadge) trimestreBadge.textContent = `Trimestre ${perfil.trimestre_actual}`;
  if (pendientes) pendientes.textContent = `(${formatearNumero(perfil.solicitudes_abiertas)})`;
  if (vencidas) {
    const total = perfil.solicitudes_vencidas;
    vencidas.textContent = `${formatearNumero(total)} ${total === 1 ? 'vencida' : 'vencidas'}`;
    vencidas.classList.toggle('hidden', total === 0);
  }
};

/* ── Navegación por vistas: una sola acción o consulta visible a la vez ── */

const VISTA_INICIAL = 'trimestres';

/* Las anclas anteriores siguen llevando a la vista que las reemplaza. */
const ALIAS_VISTAS = {
  bandeja: 'solicitudes',
  horarios: 'trimestres',
};

const vistasDisponibles = () => new Set(
  [...document.querySelectorAll('section[data-vista]')].map((seccion) => seccion.dataset.vista),
);

const vistaDesdeHash = () => {
  const clave = decodeURIComponent(window.location.hash.slice(1)).trim().toLowerCase();
  const vista = ALIAS_VISTAS[clave] || clave;
  return vistasDisponibles().has(vista) ? vista : VISTA_INICIAL;
};

const mostrarVista = (vista) => {
  document.querySelectorAll('section[data-vista]').forEach((seccion) => {
    seccion.classList.toggle('hidden', seccion.dataset.vista !== vista);
  });
  document.querySelectorAll('a[data-vista-destino]').forEach((enlace) => {
    const activa = enlace.dataset.vistaDestino === vista;
    enlace.classList.toggle('is-activa', activa);
    if (activa) enlace.setAttribute('aria-current', 'page');
    else enlace.removeAttribute('aria-current');
  });
};

const aplicarHash = () => {
  const vista = vistaDesdeHash();
  if (window.location.hash && window.location.hash !== `#${vista}`) {
    history.replaceState(null, '', `#${vista}`);
  }
  mostrarVista(vista);
  return vista;
};

const sincronizarVista = () => prepararConsulta(aplicarHash());

/* ── Bandeja de solicitudes ── */

const claseEstado = (estado) => {
  const normalizado = String(estado || '').toLowerCase();
  if (normalizado === 'pendiente') return 'badge-nuevo';
  if (normalizado === 'en revisión') return 'badge-primary';
  if (normalizado === 'aprobado') return 'badge-success';
  return 'badge-accent';
};

const celdaEstado = (estado) => {
  const celda = document.createElement('td');
  celda.appendChild(crearElemento('span', `badge ${claseEstado(estado)}`, estado));
  return celda;
};

const bloqueInstructor = (instructor) => {
  const bloque = crearElemento('div', 'gestora-instructor');
  bloque.appendChild(crearElemento('span', 'gestora-instructor__nombre', instructor?.nombre || 'Instructor'));
  bloque.appendChild(crearElemento('span', 'gestora-instructor__correo', instructor?.correo_sena || '—'));
  return bloque;
};

const celdaInstructor = (instructor) => {
  const celda = document.createElement('td');
  celda.appendChild(bloqueInstructor(instructor));
  return celda;
};

const celdaTransversales = (transversales) => {
  const celda = document.createElement('td');
  const contenedor = crearElemento('div', 'gestora-transversales');
  (transversales || []).forEach((item) => {
    contenedor.appendChild(crearElemento('span', 'badge badge-accent', item));
  });
  celda.appendChild(contenedor);
  return celda;
};

const celdaSugerencias = (solicitud) => {
  const celda = document.createElement('td');
  const horas = solicitud.horas_sugeridas == null
    ? '—'
    : `${formatearNumero(solicitud.horas_sugeridas)} h`;
  celda.appendChild(crearElemento('div', 'gestora-texto', `Horas: ${horas}`));
  celda.appendChild(crearElemento('div', 'gestora-texto', solicitud.bloque_sugerido?.trim() || 'Sin bloque sugerido'));
  if (solicitud.comentarios?.trim()) {
    celda.appendChild(crearElemento('div', 'gestora-texto text-muted', solicitud.comentarios.trim()));
  }
  return celda;
};

const celdaFechaLimite = (solicitud) => {
  const celda = document.createElement('td');
  celda.appendChild(crearElemento('div', '', formatearFecha(solicitud.fecha_limite)));
  const dias = Number(solicitud.dias_restantes ?? 0);
  const detalle = dias < 0
    ? `Vencida hace ${Math.abs(dias)} d`
    : dias === 0
      ? 'Vence hoy'
      : `Faltan ${dias} d`;
  const urgente = dias <= 1;
  celda.appendChild(crearElemento(
    'div',
    `text-xs ${urgente ? 'badge badge-nuevo' : 'text-muted'}`,
    detalle,
  ));
  return celda;
};

const celdaAcciones = (solicitud) => {
  const celda = document.createElement('td');
  const boton = crearElemento('button', 'btn btn-secondary btn-xs', 'Resolver');
  boton.type = 'button';
  boton.dataset.solicitudId = String(solicitud.id);
  celda.appendChild(boton);
  return celda;
};

const renderBandeja = () => {
  const cuerpo = obtenerElemento('bandeja-body');
  const mensaje = obtenerElemento('bandeja-mensaje');
  const tabla = obtenerElemento('bandeja-tabla-wrap');
  const subtitulo = obtenerElemento('bandeja-subtitle');
  if (!cuerpo || !mensaje || !tabla) return;

  const visibles = filtroEstado
    ? solicitudes.filter((item) => item.estado === filtroEstado)
    : solicitudes;

  if (subtitulo) {
    subtitulo.textContent = `${visibles.length} de ${solicitudes.length} solicitudes del programa.`;
  }

  cuerpo.replaceChildren();

  mensaje.classList.toggle('hidden', visibles.length > 0);
  tabla.hidden = visibles.length === 0;
  if (visibles.length === 0) return;

  visibles.forEach((solicitud) => {
    const fila = document.createElement('tr');
    fila.appendChild(celdaInstructor(solicitud.instructor));
    fila.appendChild(crearElemento('td', '', `Ficha ${solicitud.ficha_id}`));
    fila.appendChild(celdaTransversales(solicitud.transversales));
    fila.appendChild(celdaSugerencias(solicitud));
    fila.appendChild(celdaFechaLimite(solicitud));
    fila.appendChild(celdaEstado(solicitud.estado));
    fila.appendChild(celdaAcciones(solicitud));
    cuerpo.appendChild(fila);
  });
};

/* ── Fichas & Trimestres ── */

const ORDEN_JORNADAS = ['mañana', 'tarde', 'nocturna', 'noche'];
const ICONOS_JORNADA = {
  mañana: '🌅',
  tarde: '🌤',
  nocturna: '🌙',
  noche: '🌙',
};

const claveJornada = (jornada) => String(jornada || '').trim().toLowerCase();

/* La interfaz solo usa Mañana, Tarde y Noche; los datos pueden traer "Diurna" o "Nocturna".
   Un valor desconocido se muestra tal cual para no ocultar fichas. */
const JORNADAS_INTERFAZ = {
  diurna: 'Mañana',
  mañana: 'Mañana',
  manana: 'Mañana',
  tarde: 'Tarde',
  nocturna: 'Noche',
  noche: 'Noche',
};
const JORNADAS_BASE = ['Mañana', 'Tarde', 'Noche'];

const nombreJornada = (jornada) => JORNADAS_INTERFAZ[claveJornada(jornada)]
  || String(jornada || '').trim();

const compararJornadas = (a, b) => {
  const indice = (jornada) => {
    const posicion = ORDEN_JORNADAS.indexOf(claveJornada(jornada));
    return posicion === -1 ? ORDEN_JORNADAS.length : posicion;
  };
  return indice(a) - indice(b) || String(a).localeCompare(String(b), 'es');
};

const agruparPorJornada = (fichas) => {
  const grupos = new Map();
  fichas.forEach((ficha) => {
    const jornada = nombreJornada(ficha.jornada) || 'Sin jornada';
    if (!grupos.has(jornada)) grupos.set(jornada, []);
    grupos.get(jornada).push(ficha);
  });
  return [...grupos.entries()]
    .sort(([a], [b]) => compararJornadas(a, b))
    .map(([jornada, items]) => [jornada, [...items].sort((x, y) => x.id - y.id)]);
};

const textoFichas = (cantidad) => `${cantidad} ${cantidad === 1 ? 'ficha' : 'fichas'}`;

const campoFicha = (etiqueta, contenido) => {
  const campo = crearElemento('div', 'gestora-ficha__campo');
  campo.appendChild(crearElemento('span', 'gestora-ficha__etiqueta', etiqueta));
  const valor = crearElemento('div', 'gestora-ficha__valor');
  valor.appendChild(contenido);
  campo.appendChild(valor);
  return campo;
};

const tarjetaFicha = (ficha) => {
  const tarjeta = crearElemento('li', 'gestora-ficha');

  const cabecera = crearElemento('div', 'gestora-ficha__cabecera');
  const identidad = crearElemento('div', 'gestora-ficha__identidad');
  identidad.appendChild(crearElemento('strong', 'gestora-ficha__numero', `Ficha ${ficha.id}`));
  identidad.appendChild(crearElemento('span', 'gestora-ficha__programa', `${ficha.programa} · ${nombreJornada(ficha.jornada)}`));
  cabecera.appendChild(identidad);
  cabecera.appendChild(crearElemento(
    'span',
    `badge ${ficha.estado === 'Asignada' ? 'badge-success' : 'badge-nuevo'}`,
    ficha.estado,
  ));
  tarjeta.appendChild(cabecera);

  const campos = crearElemento('div', 'gestora-ficha__campos');

  const instructores = crearElemento('div', 'gestora-ficha__instructores');
  if (ficha.instructores.length === 0) {
    instructores.appendChild(crearElemento('span', 'text-muted', 'Sin asignar'));
  } else {
    ficha.instructores.forEach((instructor) => {
      instructores.appendChild(bloqueInstructor(instructor));
    });
  }
  campos.appendChild(campoFicha('Instructores', instructores));

  campos.appendChild(campoFicha(
    'Horas',
    crearElemento('span', 'gestora-ficha__horas', `${formatearNumero(ficha.horas_semanales)} h`),
  ));

  const competencias = crearElemento('div', 'gestora-competencias');
  ficha.competencias.forEach((competencia) => {
    competencias.appendChild(crearElemento('span', 'badge badge-primary', competencia));
  });
  campos.appendChild(campoFicha('Competencias', competencias));

  campos.appendChild(campoFicha(
    'Transversales',
    ficha.solicitudes_abiertas > 0
      ? crearElemento(
        'span',
        'badge badge-nuevo',
        `${ficha.solicitudes_abiertas} abierta(s) · ${formatearNumero(ficha.horas_transversales)} h`,
      )
      : crearElemento('span', 'text-muted', '—'),
  ));

  tarjeta.appendChild(campos);
  return tarjeta;
};

const grupoJornada = (jornada, fichas) => {
  const grupo = crearElemento('div', 'gestora-jornada');
  const titulo = crearElemento('h4', 'gestora-jornada__titulo');
  const icono = crearElemento('span', 'gestora-jornada__icono', ICONOS_JORNADA[claveJornada(jornada)] || '🕘');
  icono.setAttribute('aria-hidden', 'true');
  titulo.appendChild(icono);
  titulo.appendChild(crearElemento('span', '', jornada));
  titulo.appendChild(crearElemento('span', 'gestora-jornada__total', textoFichas(fichas.length)));
  grupo.appendChild(titulo);

  const lista = crearElemento('ul', 'gestora-jornada__fichas');
  fichas.forEach((ficha) => lista.appendChild(tarjetaFicha(ficha)));
  grupo.appendChild(lista);
  return grupo;
};

const renderFichas = (datos) => {
  const lista = obtenerElemento('fichas-gestora-lista');
  const mensaje = obtenerElemento('fichas-gestora-mensaje');
  const subtitulo = obtenerElemento('fichas-gestora-subtitle');
  if (!lista || !mensaje) return;

  const items = datos.items || [];
  const totalFichas = datos.total_fichas ?? items.length;

  if (subtitulo) {
    subtitulo.textContent = totalFichas > 0
      ? `Trimestre ${datos.trimestre} · ${totalFichas} fichas · ${formatearNumero(datos.total_horas)} h semanales · ${datos.fichas_sin_instructor} sin instructor`
      : 'Fichas del trimestre seleccionado, organizadas por jornada.';
  }

  const titulo = mensaje.querySelector('strong');
  if (titulo) titulo.textContent = `No hay fichas registradas en el Trimestre ${datos.trimestre}.`;

  lista.replaceChildren();
  mensaje.classList.toggle('hidden', totalFichas > 0);
  lista.hidden = totalFichas === 0;
  if (totalFichas === 0) return;

  agruparPorJornada(items).forEach(([jornada, fichas]) => {
    lista.appendChild(grupoJornada(jornada, fichas));
  });
};

/* ── Horarios ── */

const renderHorarios = (datos) => {
  const grilla = obtenerElemento('gestora-grid');
  const subtitulo = obtenerElemento('horarios-subtitle');
  if (!grilla) return;

  if (subtitulo) {
    subtitulo.textContent = `${datos.total_asignaciones} asignaciones · ${formatearNumero(datos.horas_asignadas)} h · ${datos.huecos} bloques libres`;
  }

  dibujarGrillaHorario(grilla, datos, datos.asignaciones || []);
};

/* Dibuja la cuadrícula días × bloques con las asignaciones recibidas (ya filtradas si aplica). */
const dibujarGrillaHorario = (grilla, datos, asignaciones) => {
  grilla.replaceChildren();

  const indice = new Map(
    asignaciones.map((item) => [`${item.dia}|${item.bloque}`, item]),
  );

  grilla.appendChild(crearElemento('div', 'gestora-grid__head gestora-grid__head--libre'));
  datos.dias.forEach((dia) => {
    grilla.appendChild(crearElemento('div', 'gestora-grid__head', dia));
  });

  const jornadaAnterior = { valor: null };
  datos.bloques.forEach((bloque) => {
    const jornada = asignaciones.find((item) => item.bloque === bloque)?.jornada
      || jornadaDe(bloque);

    if (jornadaAnterior.valor !== jornada) {
      jornadaAnterior.valor = jornada;
      const separador = crearElemento('div', 'gestora-grid__head gestora-grid__head--libre');
      separador.style.gridColumn = '1 / -1';
      separador.textContent = `Jornada ${jornada}`;
      grilla.appendChild(separador);
    }

    const etiqueta = crearElemento('div', 'gestora-grid__row-label');
    etiqueta.setAttribute('role', 'rowheader');
    etiqueta.appendChild(crearElemento('span', 'gestora-grid__jornada', jornada));
    etiqueta.appendChild(crearElemento('span', 'gestora-grid__bloque', bloque));
    grilla.appendChild(etiqueta);

    (datos.dias || []).forEach((diaCorto) => {
      const dia = diaCompleto(diaCorto);
      const asignacion = indice.get(`${dia}|${bloque}`);
      grilla.appendChild(crearCeldaHorario(asignacion, diaCorto, bloque));
    });
  });
};

const jornadaDe = (bloque) => {
  if (bloque < '12:00') return 'Mañana';
  if (bloque < '18:00') return 'Tarde';
  return 'Noche';
};

const COMPLETOS = {
  Lun: 'LUNES',
  Mar: 'MARTES',
  Mié: 'MIERCOLES',
  Mie: 'MIERCOLES',
  Jue: 'JUEVES',
  Vie: 'VIERNES',
};

const diaCompleto = (diaCorto) => COMPLETOS[diaCorto] || String(diaCorto).toUpperCase();

const crearCeldaHorario = (asignacion, diaCorto, bloque) => {
  const celda = document.createElement('div');
  celda.className = 'gestora-celda';
  celda.setAttribute('role', 'gridcell');

  if (!asignacion) {
    celda.textContent = 'Libre';
    celda.setAttribute('aria-label', `${diaCorto} ${bloque} libre`);
    return celda;
  }

  if (asignacion.bloqueado) {
    celda.classList.add('gestora-celda--fija');
    celda.appendChild(crearElemento('span', 'gestora-celda__ficha', `Ficha ${asignacion.ficha_id}`));
    celda.appendChild(crearElemento('span', 'gestora-celda__detalle', `🔒 ${asignacion.transversal} · fijo`));
    celda.setAttribute(
      'aria-label',
      `${diaCorto} ${bloque}: ficha ${asignacion.ficha_id}, ${asignacion.transversal} fijo, bloqueado`,
    );
    return celda;
  }

  celda.classList.add(
    asignacion.transversal ? 'gestora-celda--transversal' : 'gestora-celda--materia',
  );
  celda.appendChild(crearElemento('span', 'gestora-celda__ficha', `Ficha ${asignacion.ficha_id}`));
  if (asignacion.transversal) {
    celda.appendChild(crearElemento('span', 'gestora-celda__detalle', asignacion.transversal));
  }
  celda.appendChild(crearElemento('span', 'gestora-celda__detalle', asignacion.instructor?.nombre || 'Sin instructor'));
  celda.setAttribute(
    'aria-label',
    `${diaCorto} ${bloque}: ficha ${asignacion.ficha_id}, ${asignacion.instructor?.nombre || 'sin instructor'}`,
  );
  return celda;
};

/* ── Consultas: Fichas, Instructores y Jornadas ── */

/* Datos cargados bajo demanda al abrir cada consulta; "Actualizar" los invalida. */
const consultas = {
  fichas: null,
  instructores: null,
  horarios: new Map(),
  fichaEnFichas: null,
  fichaEnJornadas: null,
  instructor: null,
  jornada: null,
};

const normalizarTexto = (texto) => String(texto ?? '')
  .normalize('NFD')
  .replace(/[̀-ͯ]/g, '')
  .toLowerCase();

const coincideBusqueda = (busqueda, ...campos) => {
  const termino = normalizarTexto(busqueda).trim();
  return !termino || normalizarTexto(campos.join(' ')).includes(termino);
};

/* La API entrega las fichas por trimestre: se piden todos los trimestres del programa. */
const cargarFichasPrograma = async () => {
  if (consultas.fichas) return consultas.fichas;
  const primera = await pedir('/api/v1/gestora/fichas');
  const restantes = await Promise.all(
    (primera.trimestres || [])
      .filter((numero) => numero !== primera.trimestre)
      .map((numero) => pedir(`/api/v1/gestora/fichas?trimestre=${numero}`)),
  );
  consultas.fichas = [primera, ...restantes]
    .flatMap((datos) => datos.items || [])
    .sort((a, b) => a.trimestre - b.trimestre || a.id - b.id);
  return consultas.fichas;
};

const cargarInstructores = async () => {
  if (!consultas.instructores) {
    consultas.instructores = (await pedir('/api/v1/gestora/instructores')).items || [];
  }
  return consultas.instructores;
};

const horarioDelTrimestre = async (numero) => {
  if (!consultas.horarios.has(numero)) {
    consultas.horarios.set(numero, await pedir(`/api/v1/gestora/horarios?trimestre=${numero}`));
  }
  return consultas.horarios.get(numero);
};

const filaConsulta = (titulo, detalle, seleccionada, alElegir) => {
  const item = document.createElement('li');
  const boton = crearElemento('button', `gestora-fila${seleccionada ? ' is-seleccionada' : ''}`);
  boton.type = 'button';
  boton.setAttribute('aria-pressed', String(seleccionada));
  boton.appendChild(crearElemento('span', 'gestora-fila__titulo', titulo));
  boton.appendChild(crearElemento('span', 'gestora-fila__detalle', detalle));
  boton.addEventListener('click', alElegir);
  item.appendChild(boton);
  return item;
};

const resumenFicha = (ficha) => [
  ficha.programa,
  `Trimestre ${ficha.trimestre}`,
  nombreJornada(ficha.jornada) || 'Sin jornada',
  ficha.estado,
].join(' · ');

const enfocarDetalle = (detalle) => {
  if (window.matchMedia('(max-width: 900px)').matches) {
    detalle.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
};

/* "Ver horario": cuadrícula de un solo trimestre con las asignaciones filtradas.
   Con varios trimestres se ofrece un selector limitado a ellos; nunca se mezclan. */
const seccionHorario = ({ trimestres, filtrar, descripcion }) => {
  const seccion = crearElemento('div', 'gestora-detalle__horario');
  const acciones = crearElemento('div', 'gestora-detalle__acciones');
  const boton = crearElemento('button', 'btn btn-secondary', 'Ver horario');
  boton.type = 'button';
  boton.setAttribute('aria-expanded', 'false');
  acciones.appendChild(boton);

  let selector = null;
  if (trimestres.length > 1) {
    selector = crearElemento('select', 'form-input');
    selector.setAttribute('aria-label', 'Trimestre del horario');
    trimestres.forEach((numero) => {
      const opcion = crearElemento('option', '', `Trimestre ${numero}`);
      opcion.value = String(numero);
      selector.appendChild(opcion);
    });
    acciones.appendChild(selector);
  } else {
    acciones.appendChild(crearElemento('span', 'gestora-nota', `Trimestre ${trimestres[0]}`));
  }
  seccion.appendChild(acciones);

  const contenido = crearElemento('div', 'gestora-detalle__horario-contenido hidden');
  seccion.appendChild(contenido);

  const mostrar = async () => {
    const numero = Number(selector?.value ?? trimestres[0]);
    contenido.replaceChildren(crearElemento('p', 'gestora-loading', 'Cargando horario…'));
    try {
      const datos = await horarioDelTrimestre(numero);
      const asignaciones = (datos.asignaciones || []).filter(filtrar);
      const resumen = asignaciones.length > 0
        ? `${descripcion} · Trimestre ${numero} · ${asignaciones.length} ${asignaciones.length === 1 ? 'bloque asignado' : 'bloques asignados'}`
        : `${descripcion} no tiene bloques asignados en el horario del Trimestre ${numero}.`;
      contenido.replaceChildren(crearElemento('p', 'gestora-nota', resumen));
      if (asignaciones.length === 0) return;

      const envoltura = crearElemento('div', 'gestora-grid-wrapper');
      const grilla = crearElemento('div', 'gestora-grid');
      grilla.setAttribute('role', 'grid');
      grilla.setAttribute('aria-label', `Horario de ${descripcion}, Trimestre ${numero}`);
      dibujarGrillaHorario(grilla, datos, asignaciones);
      envoltura.appendChild(grilla);
      const leyenda = document.querySelector('#horarios .gestora-leyenda');
      if (leyenda) envoltura.appendChild(leyenda.cloneNode(true));
      contenido.appendChild(envoltura);
    } catch (error) {
      contenido.replaceChildren(crearElemento('p', 'gestora-nota', error.message || 'No fue posible cargar el horario.'));
    }
  };

  boton.addEventListener('click', () => {
    const abrir = contenido.classList.contains('hidden');
    contenido.classList.toggle('hidden', !abrir);
    boton.textContent = abrir ? 'Ocultar horario' : 'Ver horario';
    boton.setAttribute('aria-expanded', String(abrir));
    if (abrir) mostrar();
  });
  selector?.addEventListener('change', () => {
    if (!contenido.classList.contains('hidden')) mostrar();
  });
  return seccion;
};

const renderDetalleFicha = (contenedor, ficha) => {
  contenedor.dataset.seleccion = ficha ? String(ficha.id) : '';
  if (!ficha) {
    contenedor.replaceChildren(crearElemento('p', 'gestora-detalle__vacio', 'Selecciona una ficha para ver su detalle.'));
    return;
  }
  const tarjeta = crearElemento('ul', 'gestora-jornada__fichas');
  tarjeta.appendChild(tarjetaFicha(ficha));
  contenedor.replaceChildren(
    crearElemento('p', 'gestora-detalle__contexto', `Trimestre ${ficha.trimestre}`),
    tarjeta,
    seccionHorario({
      trimestres: [ficha.trimestre],
      filtrar: (asignacion) => asignacion.ficha_id === ficha.id,
      descripcion: `Ficha ${ficha.id}`,
    }),
  );
};

/* Solo se vuelve a dibujar el detalle si cambió la selección, para no cerrar el horario al buscar. */
const actualizarDetalleFicha = (contenedor, ficha) => {
  if (contenedor.dataset.seleccion !== (ficha ? String(ficha.id) : '')) renderDetalleFicha(contenedor, ficha);
};

const renderConsultaFichas = () => {
  const lista = obtenerElemento('consulta-fichas-lista');
  const detalle = obtenerElemento('consulta-fichas-detalle');
  const mensaje = obtenerElemento('consulta-fichas-mensaje');
  const subtitulo = obtenerElemento('consulta-fichas-subtitle');
  if (!lista || !detalle || !consultas.fichas) return;

  const busqueda = obtenerElemento('buscar-fichas')?.value || '';
  const visibles = consultas.fichas.filter((ficha) => coincideBusqueda(
    busqueda, ficha.id, ficha.programa, nombreJornada(ficha.jornada), `trimestre ${ficha.trimestre}`, ficha.estado,
  ));

  if (subtitulo) subtitulo.textContent = `${visibles.length} de ${textoFichas(consultas.fichas.length)} del programa.`;
  mensaje?.classList.toggle('hidden', visibles.length > 0);
  lista.replaceChildren(...visibles.map((ficha) => filaConsulta(
    `Ficha ${ficha.id}`,
    resumenFicha(ficha),
    ficha.id === consultas.fichaEnFichas,
    () => {
      consultas.fichaEnFichas = ficha.id;
      renderConsultaFichas();
      enfocarDetalle(detalle);
    },
  )));
  actualizarDetalleFicha(detalle, consultas.fichas.find((ficha) => ficha.id === consultas.fichaEnFichas));
};

const renderDetalleInstructor = (contenedor, instructor) => {
  contenedor.dataset.seleccion = instructor ? String(instructor.id) : '';
  if (!instructor) {
    contenedor.replaceChildren(crearElemento('p', 'gestora-detalle__vacio', 'Selecciona un instructor para ver su detalle.'));
    return;
  }

  const tarjeta = crearElemento('div', 'gestora-ficha');
  const cabecera = crearElemento('div', 'gestora-ficha__cabecera');
  cabecera.appendChild(bloqueInstructor(instructor));
  if (instructor.es_nuevo) cabecera.appendChild(crearElemento('span', 'badge badge-nuevo', 'Instructor nuevo'));
  tarjeta.appendChild(cabecera);

  const campos = crearElemento('div', 'gestora-ficha__campos');
  campos.appendChild(campoFicha('Fecha de ingreso', crearElemento('span', '', formatearFecha(instructor.fecha_ingreso))));
  const jornadas = [...new Set(instructor.fichas.map((ficha) => nombreJornada(ficha.jornada) || 'Sin jornada'))]
    .sort(compararJornadas);
  campos.appendChild(campoFicha('Jornadas', crearElemento('span', '', jornadas.join(', ') || '—')));

  const fichas = crearElemento('div', 'gestora-ficha__instructores');
  if (instructor.fichas.length === 0) {
    fichas.appendChild(crearElemento('span', 'text-muted', 'Sin fichas asignadas'));
  } else {
    instructor.fichas.forEach((ficha) => {
      fichas.appendChild(crearElemento(
        'span',
        'gestora-nota gestora-nota--fuerte',
        `Ficha ${ficha.id} · Trimestre ${ficha.trimestre} · ${nombreJornada(ficha.jornada) || 'Sin jornada'}`,
      ));
    });
  }
  campos.appendChild(campoFicha('Fichas', fichas));
  tarjeta.appendChild(campos);

  const trimestres = [...new Set(instructor.fichas.map((ficha) => ficha.trimestre))].sort((a, b) => a - b);
  contenedor.replaceChildren(
    tarjeta,
    trimestres.length > 0
      ? seccionHorario({
        trimestres,
        filtrar: (asignacion) => asignacion.instructor?.id === instructor.id,
        descripcion: instructor.nombre,
      })
      : crearElemento('p', 'gestora-nota', 'Sin fichas asignadas: no hay horario para mostrar.'),
  );
};

const renderConsultaInstructores = () => {
  const lista = obtenerElemento('consulta-instructores-lista');
  const detalle = obtenerElemento('consulta-instructores-detalle');
  const mensaje = obtenerElemento('consulta-instructores-mensaje');
  const subtitulo = obtenerElemento('consulta-instructores-subtitle');
  if (!lista || !detalle || !consultas.instructores) return;

  const busqueda = obtenerElemento('buscar-instructores')?.value || '';
  const visibles = consultas.instructores.filter((instructor) => coincideBusqueda(
    busqueda, instructor.nombre, instructor.correo_sena, ...instructor.fichas.map((ficha) => ficha.id),
  ));

  if (subtitulo) {
    const total = consultas.instructores.length;
    subtitulo.textContent = `${visibles.length} de ${total} ${total === 1 ? 'instructor vinculado' : 'instructores vinculados'}.`;
  }
  mensaje?.classList.toggle('hidden', visibles.length > 0);
  lista.replaceChildren(...visibles.map((instructor) => filaConsulta(
    instructor.nombre,
    `${instructor.correo_sena || 'Sin correo'} · ${textoFichas(instructor.fichas.length)}`,
    instructor.id === consultas.instructor,
    () => {
      consultas.instructor = instructor.id;
      renderConsultaInstructores();
      enfocarDetalle(detalle);
    },
  )));

  const seleccionado = consultas.instructores.find((instructor) => instructor.id === consultas.instructor);
  if (detalle.dataset.seleccion !== (seleccionado ? String(seleccionado.id) : '')) {
    renderDetalleInstructor(detalle, seleccionado);
  }
};

const renderConsultaJornadas = () => {
  const opciones = obtenerElemento('consulta-jornadas-opciones');
  const lista = obtenerElemento('consulta-jornadas-lista');
  const detalle = obtenerElemento('consulta-jornadas-detalle');
  const mensaje = obtenerElemento('consulta-jornadas-mensaje');
  const instructores = obtenerElemento('consulta-jornadas-instructores');
  if (!opciones || !lista || !detalle || !consultas.fichas) return;

  const grupos = new Map(JORNADAS_BASE.map((jornada) => [jornada, []]));
  consultas.fichas.forEach((ficha) => {
    const jornada = nombreJornada(ficha.jornada) || 'Sin jornada';
    if (!grupos.has(jornada)) grupos.set(jornada, []);
    grupos.get(jornada).push(ficha);
  });

  opciones.replaceChildren(...[...grupos.entries()]
    .sort(([a], [b]) => compararJornadas(a, b))
    .map(([jornada, fichas]) => {
      const activa = jornada === consultas.jornada;
      const boton = crearElemento('button', `chip${activa ? ' chip--activo' : ''}`, `${jornada} (${fichas.length})`);
      boton.type = 'button';
      boton.setAttribute('aria-pressed', String(activa));
      boton.addEventListener('click', () => {
        consultas.jornada = jornada;
        consultas.fichaEnJornadas = null;
        renderConsultaJornadas();
      });
      return boton;
    }));

  const fichas = grupos.get(consultas.jornada) || [];
  if (mensaje) {
    mensaje.textContent = consultas.jornada
      ? `No hay fichas en la jornada ${consultas.jornada}.`
      : 'Selecciona una jornada para ver sus fichas.';
    mensaje.classList.toggle('hidden', fichas.length > 0);
  }
  if (instructores) {
    const nombres = [...new Set(fichas.flatMap((ficha) => ficha.instructores.map((instructor) => instructor.nombre)))]
      .sort((a, b) => a.localeCompare(b, 'es'));
    instructores.textContent = nombres.length > 0 ? `Instructores en esta jornada: ${nombres.join(', ')}.` : '';
    instructores.classList.toggle('hidden', nombres.length === 0);
  }
  lista.replaceChildren(...fichas.map((ficha) => filaConsulta(
    `Ficha ${ficha.id}`,
    resumenFicha(ficha),
    ficha.id === consultas.fichaEnJornadas,
    () => {
      consultas.fichaEnJornadas = ficha.id;
      renderConsultaJornadas();
      enfocarDetalle(detalle);
    },
  )));
  actualizarDetalleFicha(detalle, fichas.find((ficha) => ficha.id === consultas.fichaEnJornadas));
};

const CONSULTAS_BAJO_DEMANDA = {
  fichas: async () => {
    await cargarFichasPrograma();
    renderConsultaFichas();
  },
  instructores: async () => {
    await cargarInstructores();
    renderConsultaInstructores();
  },
  jornadas: async () => {
    await cargarFichasPrograma();
    renderConsultaJornadas();
  },
};

const prepararConsulta = async (vista) => {
  const preparar = CONSULTAS_BAJO_DEMANDA[vista];
  if (!preparar) return;
  try {
    await preparar();
  } catch (error) {
    mostrarError(error.message || 'No fue posible cargar la consulta.');
  }
};

const invalidarConsultas = () => {
  consultas.fichas = null;
  consultas.instructores = null;
  consultas.horarios.clear();
  ['consulta-fichas-detalle', 'consulta-instructores-detalle', 'consulta-jornadas-detalle'].forEach((id) => {
    const detalle = obtenerElemento(id);
    if (detalle) detalle.dataset.seleccion = '';
  });
};

/* ── Resolución de solicitudes ── */

const abrirModal = (solicitudId) => {
  const solicitud = solicitudes.find((item) => item.id === solicitudId);
  const modal = obtenerElemento('gestora-modal');
  if (!solicitud || !modal) return;

  obtenerElemento('resolver-solicitud-id').value = String(solicitud.id);
  obtenerElemento('resolver-estado').value = solicitud.estado;
  obtenerElemento('resolver-horas').value = solicitud.horas_sugeridas ?? '';
  obtenerElemento('resolver-bloque').value = solicitud.bloque_sugerido || '';
  obtenerElemento('resolver-comentario').value = solicitud.respuesta_gestora || '';
  obtenerElemento('gestora-modal-subtitle').textContent = [
    solicitud.instructor?.nombre || 'Instructor',
    `Ficha ${solicitud.ficha_id}`,
    (solicitud.transversales || []).join(', '),
  ].join(' · ');

  modal.classList.remove('hidden');
  obtenerElemento('resolver-estado').focus();
};

const cerrarModal = () => {
  obtenerElemento('gestora-modal')?.classList.add('hidden');
};

const resolverSolicitud = async (evento) => {
  evento.preventDefault();

  const solicitudId = Number(obtenerElemento('resolver-solicitud-id').value);
  const estado = obtenerElemento('resolver-estado').value;
  const horas = obtenerElemento('resolver-horas').value.trim();
  const bloque = obtenerElemento('resolver-bloque').value.trim();
  const comentario = obtenerElemento('resolver-comentario').value.trim();
  const boton = obtenerElemento('btn-guardar-resolver');

  if (horas !== '' && (!Number.isFinite(Number(horas)) || Number(horas) < 0 || Number(horas) > 40)) {
    mostrarToast('error', 'Horas inválidas', 'Indica un valor entre 0 y 40 horas.');
    return;
  }
  if (['Aprobado', 'Rechazado'].includes(estado) && !comentario) {
    mostrarToast('error', 'Falta el comentario', 'Explica al instructor por qué se cierra la solicitud.');
    return;
  }

  if (boton) {
    boton.disabled = true;
    boton.innerHTML = '<span class="spinner" aria-hidden="true"></span> Guardando…';
  }

  try {
    const respuesta = await fetch(`/api/v1/gestora/solicitudes/${solicitudId}/estado`, {
      method: 'POST',
      headers: obtenerHeaders(),
      credentials: 'same-origin',
      body: JSON.stringify({
        estado,
        comentario,
        horas_asignadas: horas === '' ? null : Number(horas),
        bloque_asignado: bloque,
      }),
    });
    const datos = await respuesta.json().catch(() => null);
    if (!respuesta.ok) throw new Error(extraerDetalle(datos));

    mostrarToast('success', 'Solicitud actualizada', datos.mensaje);
    cerrarModal();
    await cargarTodo();
  } catch (error) {
    mostrarToast('error', 'No se pudo resolver la solicitud', error.message || 'Intenta nuevamente.');
  } finally {
    if (boton) {
      boton.textContent = 'Guardar';
      boton.disabled = false;
    }
  }
};

/* ── Filtros ── */

const activarChip = (contenedor, chip) => {
  contenedor.querySelectorAll('.chip').forEach((item) => item.classList.remove('chip--activo'));
  chip.classList.add('chip--activo');
};

const filtrarEstado = (chip) => {
  filtroEstado = chip.dataset.estado || '';
  activarChip(chip.parentElement, chip);
  renderBandeja();
};

const filtrarJornada = (chip) => {
  filtroJornada = chip.dataset.jornada || 'todas';
  activarChip(chip.parentElement, chip);
  cargarHorarios();
};

/* ── Carga ── */

const cargarPerfil = async () => {
  renderResumen(await pedir('/api/v1/gestora/perfil'));
};

const cargarBandeja = async () => {
  const datos = await pedir('/api/v1/gestora/bandeja-solicitudes');
  solicitudes = datos.solicitudes || [];
  renderBandeja();
};

/* Las opciones del selector salen de la duración del programa que entrega la API. */
const renderSelectorTrimestres = (trimestres, seleccionado) => {
  const selector = obtenerElemento('selector-trimestre');
  if (!selector || !Array.isArray(trimestres) || trimestres.length === 0) return;

  const actuales = [...selector.options].map((opcion) => Number(opcion.value));
  const cambio = actuales.length !== trimestres.length
    || trimestres.some((numero, indice) => numero !== actuales[indice]);
  if (cambio) {
    selector.replaceChildren(...trimestres.map((numero) => {
      const opcion = crearElemento('option', '', `Trimestre ${numero}`);
      opcion.value = String(numero);
      return opcion;
    }));
  }
  selector.value = String(seleccionado);
};

const cargarFichas = async () => {
  const datos = await pedir(`/api/v1/gestora/fichas?trimestre=${trimestre}`);
  renderSelectorTrimestres(datos.trimestres, datos.trimestre);
  renderFichas(datos);
};

const cargarHorarios = async () => {
  const datos = await pedir(
    `/api/v1/gestora/horarios?trimestre=${trimestre}&jornada=${encodeURIComponent(filtroJornada)}`,
  );
  renderHorarios(datos);
};

const cargarTodo = async () => {
  ocultarError();
  invalidarConsultas();
  const boton = obtenerElemento('btn-actualizar');
  if (boton) boton.disabled = true;
  try {
    await Promise.all([
      cargarPerfil(),
      cargarBandeja(),
      cargarFichas(),
      cargarHorarios(),
      prepararConsulta(vistaDesdeHash()),
    ]);
  } catch (error) {
    mostrarError(error.message || 'No fue posible cargar la información.');
    mostrarToast('error', 'Error al cargar', error.message || 'Intenta nuevamente.');
  } finally {
    if (boton) boton.disabled = false;
  }
};

const cambiarTrimestre = async (evento) => {
  trimestre = Number(evento.currentTarget.value) || 1;
  try {
    await Promise.all([cargarFichas(), cargarHorarios()]);
  } catch (error) {
    mostrarError(error.message || 'No fue posible cargar el trimestre.');
  }
};

/* ── Arranque ── */

const inicializar = () => {
  const selectorTrimestre = obtenerElemento('selector-trimestre');
  trimestre = Number(selectorTrimestre?.value) || 1;

  selectorTrimestre?.addEventListener('change', cambiarTrimestre);
  obtenerElemento('btn-actualizar')?.addEventListener('click', cargarTodo);
  obtenerElemento('btn-cancelar-resolver')?.addEventListener('click', cerrarModal);
  obtenerElemento('form-resolver')?.addEventListener('submit', resolverSolicitud);
  obtenerElemento('gestora-modal')?.addEventListener('click', (evento) => {
    if (evento.target === obtenerElemento('gestora-modal')) cerrarModal();
  });
  document.addEventListener('keydown', (evento) => {
    if (evento.key === 'Escape') cerrarModal();
  });

  obtenerElemento('bandeja-body')?.addEventListener('click', (evento) => {
    const boton = evento.target.closest('button[data-solicitud-id]');
    if (boton) abrirModal(Number(boton.dataset.solicitudId));
  });

  document.querySelectorAll('.chip[data-estado]').forEach((chip) => {
    chip.addEventListener('click', () => filtrarEstado(chip));
  });
  document.querySelectorAll('.chip[data-jornada]').forEach((chip) => {
    chip.addEventListener('click', () => filtrarJornada(chip));
  });

  obtenerElemento('buscar-fichas')?.addEventListener('input', renderConsultaFichas);
  obtenerElemento('buscar-instructores')?.addEventListener('input', renderConsultaInstructores);

  /* La consulta activa se carga dentro de cargarTodo(); los cambios de hash la cargan después. */
  window.addEventListener('hashchange', sincronizarVista);
  aplicarHash();

  cargarTodo();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', inicializar);
} else {
  inicializar();
}
