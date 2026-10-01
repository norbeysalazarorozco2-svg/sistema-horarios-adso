'use strict';

let fichas = [];
let solicitudes = [];
let modoPrueba = 'nuevo';

const obtenerElemento = (id) => document.getElementById(id);
const obtenerToken = () => localStorage.getItem('access_token') ?? '';

const obtenerHeaders = () => {
  const token = obtenerToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

const formatearNumero = (valor) => Number(valor).toLocaleString('es-CO', {
  maximumFractionDigits: 1,
});

const formatearFecha = (valor) => {
  if (!valor) return '—';
  const fecha = new Date(`${valor}T00:00:00`);
  if (Number.isNaN(fecha.getTime())) return valor;
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

const mostrarToast = (tipo, titulo, mensaje = '') => {
  const contenedor = obtenerElemento('perfil-notifications');
  if (!contenedor) return;
  const toast = document.createElement('div');
  toast.className = `perfil-toast perfil-toast--${tipo}`;
  toast.setAttribute('role', 'alert');
  const contenido = document.createElement('div');
  const encabezado = document.createElement('strong');
  encabezado.textContent = titulo;
  contenido.appendChild(encabezado);
  if (mensaje) {
    const detalle = document.createElement('div');
    detalle.textContent = mensaje;
    contenido.appendChild(detalle);
  }
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
  const error = obtenerElemento('perfil-error');
  if (!error) return;
  error.textContent = mensaje;
  error.hidden = false;
};

const ocultarError = () => {
  const error = obtenerElemento('perfil-error');
  if (error) {
    error.textContent = '';
    error.hidden = true;
  }
};

const crearElemento = (etiqueta, clase, texto) => {
  const elemento = document.createElement(etiqueta);
  if (clase) elemento.className = clase;
  if (texto !== undefined) elemento.textContent = texto;
  return elemento;
};

const renderResumen = (datos) => {
  const nombre = obtenerElemento('perfil-nombre');
  const correo = obtenerElemento('perfil-correo');
  const estado = obtenerElemento('perfil-estado-badge');
  const fichasCount = obtenerElemento('perfil-fichas-count');
  const horas = obtenerElemento('perfil-horas');
  const competenciasCount = obtenerElemento('perfil-competencias-count');
  const antiguedad = obtenerElemento('perfil-antiguedad');

  if (nombre) nombre.textContent = datos.nombre;
  if (correo) correo.textContent = datos.correo_sena || 'Correo no registrado';
  if (estado) {
    estado.textContent = datos.es_nuevo ? 'Nuevo instructor' : 'Instructor activo';
    estado.className = `badge ${datos.es_nuevo ? 'badge-nuevo' : 'badge-success'}`;
  }
  if (fichasCount) fichasCount.textContent = formatearNumero(datos.fichas.length);
  if (horas) horas.textContent = `${formatearNumero(datos.horas_semanales)} h`;
  if (competenciasCount) competenciasCount.textContent = formatearNumero(datos.competencias.length);
  if (antiguedad) {
    antiguedad.textContent = datos.antiguedad_dias > 0
      ? `${formatearNumero(datos.antiguedad_dias)} días`
      : 'Sin registro';
  }
};

const renderCompetencias = (competencias) => {
  const contenedor = crearElemento('div', 'perfil-competencias');
  if (competencias.length === 0) {
    contenedor.textContent = 'Sin competencias registradas';
    return contenedor;
  }
  competencias.forEach((competencia) => {
    const etiqueta = crearElemento(
      'span',
      'badge badge-accent',
      `${competencia.codigo} · ${competencia.nombre}`,
    );
    contenedor.appendChild(etiqueta);
  });
  return contenedor;
};

const renderFichas = (datosFichas, esNuevo) => {
  const cuerpo = obtenerElemento('fichas-body');
  const mensaje = obtenerElemento('fichas-mensaje');
  const tabla = obtenerElemento('fichas-tabla-wrap');
  const titulo = mensaje?.querySelector('strong');
  const descripcion = mensaje?.querySelector('p');
  if (!cuerpo || !mensaje || !tabla) return;

  cuerpo.replaceChildren();
  if (datosFichas.length === 0) {
    mensaje.hidden = false;
    tabla.hidden = true;
    if (titulo) {
      titulo.textContent = esNuevo
        ? 'No necesitas fichas a cargo aún.'
        : 'No tienes fichas a cargo asignadas.';
    }
    if (descripcion) {
      descripcion.textContent = esNuevo
        ? 'Como estás en tus primeros 3 meses como instructor, la gestora te asignará fichas más adelante.'
        : 'LaGestora informará las nuevas asignaciones cuando estén disponibles.';
    }
    return;
  }

  mensaje.hidden = true;
  tabla.hidden = false;
  datosFichas.forEach((ficha) => {
    const fila = document.createElement('tr');
    const identificacion = crearElemento('td');
    identificacion.appendChild(crearElemento('strong', '', `Ficha ${ficha.id}`));
    identificacion.appendChild(crearElemento('div', 'text-xs text-muted', ficha.jornada));
    fila.appendChild(identificacion);
    fila.appendChild(crearElemento('td', '', ficha.programa));
    fila.appendChild(crearElemento('td', '', `Trimestre ${ficha.trimestre}`));

    const competencias = document.createElement('td');
    competencias.appendChild(renderCompetencias(ficha.competencias));
    fila.appendChild(competencias);
    fila.appendChild(crearElemento('td', '', `${formatearNumero(ficha.horas_semanales)} h`));
    cuerpo.appendChild(fila);
  });
};

const renderSolicitudes = (datosSolicitudes) => {
  const cuerpo = obtenerElemento('solicitudes-body');
  const mensaje = obtenerElemento('solicitudes-mensaje');
  const tabla = obtenerElemento('solicitudes-tabla-wrap');
  if (!cuerpo || !mensaje || !tabla) return;

  cuerpo.replaceChildren();
  if (datosSolicitudes.length === 0) {
    mensaje.hidden = false;
    tabla.hidden = true;
    return;
  }

  mensaje.hidden = true;
  tabla.hidden = false;
  datosSolicitudes.forEach((solicitud) => {
    const fila = document.createElement('tr');
    fila.appendChild(crearElemento('td', '', `Ficha ${solicitud.ficha_id}`));
    fila.appendChild(crearElemento('td', '', solicitud.transversales.join(', ')));
    fila.appendChild(crearElemento(
      'td',
      'perfil-solicitud-texto',
      solicitud.comentarios?.trim() || '—',
    ));
    fila.appendChild(crearElemento('td', '', formatearFecha(solicitud.fecha_solicitud)));
    const estado = String(solicitud.estado || 'Pendiente');
    const estadoCelda = document.createElement('td');
    const estadoNormalizado = estado.toLowerCase();
    const clase = estadoNormalizado === 'pendiente'
      ? 'badge-nuevo'
      : estadoNormalizado === 'aprobado'
        ? 'badge-success'
        : estadoNormalizado === 'rechazado'
          ? 'badge-accent'
          : 'badge-primary';
    estadoCelda.appendChild(crearElemento('span', `badge ${clase}`, estado));
    fila.appendChild(estadoCelda);
    fila.appendChild(crearElemento('td', '', solicitud.gestora_nombre || '—'));
    cuerpo.appendChild(fila);
  });
};

const pendientesPorFicha = () => solicitudes.reduce((resultado, solicitud) => {
  if (!['pendiente', 'en revisión', 'en_revision'].includes(solicitud.estado.toLowerCase())) {
    return resultado;
  }
  const actuales = resultado.get(solicitud.ficha_id) ?? [];
  resultado.set(solicitud.ficha_id, [...actuales, ...solicitud.transversales]);
  return resultado;
}, new Map());

const renderFormularioTransversales = (datosFichas, esNuevo) => {
  const seccion = obtenerElemento('transversales-section');
  const contenedor = obtenerElemento('transversales-fichas');
  if (!seccion || !contenedor) return;

  seccion.hidden = esNuevo || datosFichas.length === 0;
  contenedor.replaceChildren();
  if (esNuevo || datosFichas.length === 0) return;

  const pendientes = pendientesPorFicha();
  datosFichas.forEach((ficha) => {
    const etiqueta = document.createElement('label');
    etiqueta.className = 'perfil-ficha-option';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.name = 'ficha';
    checkbox.value = String(ficha.id);
    checkbox.dataset.fichaId = String(ficha.id);
    const contenido = crearElemento('span', 'perfil-ficha-option__contenido');
    contenido.appendChild(crearElemento('span', 'perfil-ficha-option__titulo', `Ficha ${ficha.id}`));
    const pendientesFicha = pendientes.get(ficha.id) ?? [];
    const detalle = pendientesFicha.length > 0
      ? `Trimestre ${ficha.trimestre} · Pendiente: ${pendientesFicha.join(', ')}`
      : `Trimestre ${ficha.trimestre} · ${ficha.jornada}`;
    contenido.appendChild(crearElemento('span', 'perfil-ficha-option__detalle', detalle));
    etiqueta.appendChild(checkbox);
    etiqueta.appendChild(contenido);
    if (pendientesFicha.length >= 3) {
      checkbox.disabled = true;
      etiqueta.classList.add('perfil-ficha-option--completa');
    }
    contenedor.appendChild(etiqueta);
  });
  actualizarBotonTransversales();
};

const actualizarBotonTransversales = () => {
  const fichasSeleccionadas = [...document.querySelectorAll('input[name="ficha"]:checked')];
  const asignaturasSeleccionadas = [...document.querySelectorAll('input[name="transversal"]:checked')];
  const boton = obtenerElemento('btn-solicitar-transversales');
  const ayuda = obtenerElemento('transversales-ayuda');
  if (!boton || !ayuda) return;

  if (fichasSeleccionadas.length === 0 || asignaturasSeleccionadas.length === 0) {
    boton.disabled = true;
    ayuda.textContent = 'Selecciona al menos una ficha y una asignatura para continuar.';
    return;
  }

  const pendientes = pendientesPorFicha();
  const asignaturasConConflicto = asignaturasSeleccionadas.filter((input) => {
    const asignatura = input.value;
    return fichasSeleccionadas.some((ficha) => (pendientes.get(Number(ficha.value)) ?? []).includes(asignatura));
  });
  if (asignaturasConConflicto.length > 0) {
    boton.disabled = true;
    ayuda.textContent = 'Algunas asignaturas ya tienen una solicitud pendiente para una ficha seleccionada.';
    return;
  }

  boton.disabled = false;
  ayuda.textContent = 'La solicitud se enviará a la Gestora para coordinación.';
};

const renderPerfil = (datos) => {
  fichas = datos.fichas ?? [];
  solicitudes = datos.solicitudes_transversales ?? [];
  modoPrueba = datos.modo_prueba ?? (datos.es_nuevo ? 'nuevo' : 'antiguo');
  const selector = obtenerElemento('selector-modo-prueba');
  if (selector) selector.value = modoPrueba;
  renderResumen(datos);
  renderFichas(fichas, datos.es_nuevo);
  renderSolicitudes(solicitudes);
  renderFormularioTransversales(fichas, datos.es_nuevo);
};

const cargarPerfil = async () => {
  ocultarError();
  try {
    const respuesta = await fetch('/api/v1/instructor/perfil', {
      headers: obtenerHeaders(),
      credentials: 'same-origin',
    });
    const datos = await respuesta.json().catch(() => null);
    if (!respuesta.ok) {
      throw new Error(extraerDetalle(datos));
    }
    renderPerfil(datos);
  } catch (error) {
    mostrarError(error.message || 'No fue posible cargar el perfil.');
    mostrarToast('error', 'Error al cargar el perfil', error.message || 'Intenta nuevamente.');
  }
};

const cambiarModoPrueba = async (evento) => {
  const selector = evento.currentTarget;
  const modo = selector.value;
  if (!['nuevo', 'antiguo'].includes(modo)) return;

  const modoAnterior = modoPrueba;
  selector.disabled = true;
  try {
    const respuesta = await fetch('/api/v1/instructor/modo-prueba', {
      method: 'POST',
      headers: obtenerHeaders(),
      credentials: 'same-origin',
      body: JSON.stringify({ modo }),
    });
    const datos = await respuesta.json().catch(() => null);
    if (!respuesta.ok) throw new Error(extraerDetalle(datos));
    await cargarPerfil();
    mostrarToast(
      'info',
      'Modo de prueba actualizado',
      `Ahora simulas el modo Instructor ${modo === 'nuevo' ? 'Nuevo' : 'Antiguo'}.`,
    );
  } catch (error) {
    selector.value = modoAnterior;
    mostrarToast('error', 'No se pudo cambiar el modo', error.message || 'Intenta nuevamente.');
  } finally {
    selector.disabled = false;
  }
};

const solicitarTransversales = async (evento) => {
  evento.preventDefault();
  const formulario = obtenerElemento('form-transversales');
  const fichasSeleccionadas = [...document.querySelectorAll('input[name="ficha"]:checked')]
    .map((input) => Number(input.value));
  const asignaturasSeleccionadas = [...document.querySelectorAll('input[name="transversal"]:checked')]
    .map((input) => input.value);
  const comentariosInput = obtenerElemento('transversales-comentarios');
  if (fichasSeleccionadas.length === 0 || asignaturasSeleccionadas.length === 0) {
    mostrarToast('error', 'Solicitud incompleta', 'Selecciona al menos una ficha y una asignatura.');
    return;
  }

  const boton = obtenerElemento('btn-solicitar-transversales');
  if (boton) {
    boton.disabled = true;
    boton.innerHTML = '<span class="spinner" aria-hidden="true"></span> Enviando…';
  }

  try {
    const respuesta = await fetch('/api/transversales/solicitar', {
      method: 'POST',
      headers: obtenerHeaders(),
      credentials: 'same-origin',
      body: JSON.stringify({
        ficha_ids: fichasSeleccionadas,
        transversales: asignaturasSeleccionadas,
        comentarios: comentariosInput?.value.trim() ?? '',
      }),
    });
    const datos = await respuesta.json().catch(() => null);
    if (!respuesta.ok) throw new Error(extraerDetalle(datos));

    const nuevasSolicitudes = Array.isArray(datos?.solicitudes) ? datos.solicitudes : [];
    const idsExistentes = new Set(solicitudes.map((solicitud) => solicitud.id));
    solicitudes = [
      ...solicitudes,
      ...nuevasSolicitudes.filter((solicitud) => !idsExistentes.has(solicitud.id)),
    ];
    renderSolicitudes(solicitudes);
    formulario?.reset();
    renderFormularioTransversales(fichas, false);
    mostrarToast('success', 'Solicitud registrada', datos.mensaje);
    await cargarPerfil();
  } catch (error) {
    mostrarToast('error', 'No se pudo enviar la solicitud', error.message || 'Intenta nuevamente.');
  } finally {
    if (boton) {
      boton.textContent = 'Enviar solicitud a la Gestora';
      actualizarBotonTransversales();
    }
  }
};

const inicializar = () => {
  const formulario = obtenerElemento('form-transversales');
  const selectorModo = obtenerElemento('selector-modo-prueba');
  if (formulario) {
    formulario.addEventListener('change', actualizarBotonTransversales);
    formulario.addEventListener('submit', solicitarTransversales);
  }
  selectorModo?.addEventListener('change', cambiarModoPrueba);
  cargarPerfil();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', inicializar);
} else {
  inicializar();
}
