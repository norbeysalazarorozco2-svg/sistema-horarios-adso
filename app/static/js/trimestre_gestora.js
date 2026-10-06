'use strict';

/* ============================================================
   TRIMESTRE_GESTORA.JS — Aprobación final del trimestre (§8)
   API: GET  /api/v1/gestora/trimestre
        POST /api/v1/gestora/trimestre/aprobar
        POST /api/v1/gestora/trimestre/reabrir
   ============================================================ */

const API_TRIMESTRE = '/api/v1/gestora/trimestre';

let estadoActual = null;

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

const formatearFechaHora = (valor) => new Date(valor).toLocaleString('es-CO', {
  day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
});

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
  const contenedor = obtenerElemento('trimestre-notificaciones');
  if (!contenedor) return;
  const toast = crearElemento('div', `trimestre-toast trimestre-toast--${tipo}`);
  toast.setAttribute('role', 'status');
  toast.appendChild(crearElemento('strong', '', titulo));
  if (mensaje) toast.appendChild(crearElemento('span', '', mensaje));
  contenedor.appendChild(toast);
  const remover = () => toast.remove();
  setTimeout(remover, 6000);
  toast.addEventListener('click', remover);
};

const mostrarErrorEn = (id, mensaje = '') => {
  const error = obtenerElemento(id);
  if (!error) return;
  error.textContent = mensaje;
  error.classList.toggle('hidden', !mensaje);
};

/* ── Encabezado y aviso ── */

const renderEncabezado = (estado) => {
  obtenerElemento('trimestre-titulo').textContent = `Aprobar trimestre ${estado.periodo}`;
  const insignia = obtenerElemento('trimestre-estado');
  const aprobado = estado.estado === 'aprobado';
  insignia.hidden = false;
  insignia.className = `trimestre-estado trimestre-estado--${estado.estado}`;
  insignia.textContent = aprobado ? '✓ Aprobado y publicado' : '● Abierto';
};

const renderAviso = (estado) => {
  const aviso = obtenerElemento('trimestre-aviso');
  if (!aviso) return;
  let variante;
  let texto;
  if (estado.estado === 'aprobado') {
    variante = 'ok';
    texto = `El horario de ${estado.periodo} está publicado. Los cambios están congelados hasta reabrir el trimestre.`;
  } else if (estado.bloqueantes > 0) {
    variante = 'error';
    texto = `Aún no se puede aprobar: ${estado.bloqueantes} ${estado.bloqueantes > 1 ? 'verificaciones bloqueantes' : 'verificación bloqueante'} sin cumplir.`;
  } else if (estado.advertencias > 0) {
    variante = 'aviso';
    texto = `Listo para aprobar con ${estado.advertencias} advertencia${estado.advertencias > 1 ? 's' : ''}.`;
  } else {
    variante = 'ok';
    texto = 'Todo en orden: listo para aprobar y publicar.';
  }
  const iconos = { ok: '✅', error: '⛔', aviso: '⚠️' };
  const icono = crearElemento('span', 'trimestre-aviso__icono', iconos[variante]);
  icono.setAttribute('aria-hidden', 'true');
  aviso.className = `trimestre-aviso trimestre-aviso--${variante}`;
  aviso.replaceChildren(icono, crearElemento('p', 'trimestre-aviso__texto', texto));
};

/* ── Verificaciones ── */

const crearVerificacion = (v) => {
  const tipo = v.cumple ? 'cumple' : v.nivel;
  const item = crearElemento('li', `trimestre-verificacion trimestre-verificacion--${tipo}`);

  const cabecera = crearElemento('div', 'trimestre-verificacion__cabecera');
  const icono = crearElemento('span', 'trimestre-verificacion__icono', v.cumple ? '✓' : (v.nivel === 'bloqueante' ? '✕' : '!'));
  icono.setAttribute('aria-hidden', 'true');
  cabecera.append(icono, crearElemento('strong', 'trimestre-verificacion__titulo', v.titulo));
  if (!v.cumple) {
    cabecera.appendChild(crearElemento('span', `trimestre-nivel trimestre-nivel--${v.nivel}`,
      v.nivel === 'bloqueante' ? 'Bloquea' : 'Advertencia'));
  }

  item.append(cabecera, crearElemento('p', 'trimestre-verificacion__detalle', v.detalle));
  if (v.items.length) {
    const lista = crearElemento('ul', 'trimestre-verificacion__items');
    v.items.forEach((texto) => lista.appendChild(crearElemento('li', '', texto)));
    item.appendChild(lista);
  }
  if (v.enlace && estadoActual?.estado !== 'aprobado') {
    const enlace = crearElemento('a', 'trimestre-verificacion__enlace', 'Resolver →');
    enlace.href = v.enlace;
    item.appendChild(enlace);
  }
  return item;
};

const renderVerificaciones = (estado) => {
  const lista = obtenerElemento('trimestre-verificaciones');
  if (!lista) return;
  // Primero lo que bloquea, luego advertencias y al final lo que ya cumple.
  const orden = (v) => (v.cumple ? 2 : (v.nivel === 'bloqueante' ? 0 : 1));
  const ordenadas = [...estado.verificaciones].sort((a, b) => orden(a) - orden(b));
  lista.replaceChildren(...ordenadas.map(crearVerificacion));
};

/* ── Paneles ── */

const renderAprobar = (estado) => {
  const panel = obtenerElemento('panel-aprobar');
  panel.classList.toggle('hidden', estado.estado === 'aprobado');
  if (estado.estado === 'aprobado') return;

  const wrap = obtenerElemento('confirmar-advertencias-wrap');
  const check = obtenerElemento('confirmar-advertencias');
  wrap.classList.toggle('hidden', estado.advertencias === 0);
  obtenerElemento('confirmar-advertencias-texto').textContent =
    `Revisé ${estado.advertencias === 1 ? 'la advertencia' : `las ${estado.advertencias} advertencias`} y apruebo con ${estado.advertencias === 1 ? 'ella' : 'ellas'}.`;
  if (estado.advertencias === 0) check.checked = false;

  const actualizarBoton = () => {
    const boton = obtenerElemento('btn-aprobar');
    boton.disabled = !estado.puede_aprobar || (estado.advertencias > 0 && !check.checked);
    obtenerElemento('aprobar-motivo').textContent = !estado.puede_aprobar
      ? 'Resuelve las verificaciones bloqueantes para poder aprobar.'
      : (boton.disabled ? 'Marca la casilla para confirmar las advertencias.' : '');
  };
  check.onchange = actualizarBoton;
  actualizarBoton();
};

const renderAprobado = (estado) => {
  const panel = obtenerElemento('panel-aprobado');
  panel.classList.toggle('hidden', estado.estado !== 'aprobado');
  if (estado.estado !== 'aprobado') return;

  const a = estado.aprobacion;
  const detalle = obtenerElemento('aprobado-detalle');
  const partes = [crearElemento('p', 'trimestre-aprobado__quien',
    `Aprobado por ${a.gestora_nombre} el ${formatearFechaHora(a.fecha)}`)];
  if (a.texto) partes.push(crearElemento('p', 'trimestre-aprobado__texto', `“${a.texto}”`));
  if (a.advertencias_aceptadas.length) {
    partes.push(crearElemento('p', 'trimestre-aprobado__etiqueta', 'Advertencias aceptadas:'));
    const lista = crearElemento('ul', 'trimestre-aprobado__lista');
    a.advertencias_aceptadas.forEach((t) => lista.appendChild(crearElemento('li', '', t)));
    partes.push(lista);
  }
  detalle.replaceChildren(...partes);
};

const renderHistorial = (estado) => {
  const lista = obtenerElemento('trimestre-historial');
  if (!lista) return;
  if (!estado.historial.length) {
    lista.replaceChildren(crearElemento('li', 'trimestre-historial__vacio', 'Sin aprobaciones todavía.'));
    return;
  }
  lista.replaceChildren(...estado.historial.map((e) => {
    const item = crearElemento('li', `trimestre-evento trimestre-evento--${e.tipo}`);
    item.append(
      crearElemento('strong', '', e.tipo === 'aprobado' ? '✓ Aprobado' : '↺ Reabierto'),
      crearElemento('span', 'trimestre-evento__meta', ` · ${e.gestora_nombre} · ${formatearFechaHora(e.fecha)}`),
    );
    if (e.texto) item.appendChild(crearElemento('span', 'trimestre-evento__texto', `“${e.texto}”`));
    return item;
  }));
};

const render = (estado) => {
  estadoActual = estado;
  renderEncabezado(estado);
  renderAviso(estado);
  renderVerificaciones(estado);
  renderAprobar(estado);
  renderAprobado(estado);
  renderHistorial(estado);
};

/* ── Acciones ── */

const cargar = async () => {
  try {
    render(await pedirApi(API_TRIMESTRE));
  } catch (error) {
    const aviso = obtenerElemento('trimestre-aviso');
    if (aviso) {
      aviso.className = 'trimestre-aviso trimestre-aviso--error';
      aviso.replaceChildren(crearElemento('p', 'trimestre-aviso__texto', error.message));
    }
  }
};

const aprobar = async (evento) => {
  evento.preventDefault();
  const boton = obtenerElemento('btn-aprobar');
  boton.disabled = true;
  mostrarErrorEn('aprobar-error');
  try {
    const estado = await pedirApi(`${API_TRIMESTRE}/aprobar`, {
      method: 'POST',
      body: JSON.stringify({
        confirma_advertencias: obtenerElemento('confirmar-advertencias').checked,
        observaciones: obtenerElemento('observaciones').value,
      }),
    });
    obtenerElemento('observaciones').value = '';
    render(estado);
    mostrarToast('exito', `Trimestre ${estado.periodo} aprobado`, 'El horario quedó publicado y el cierre se guardó para la regla de equidad.');
  } catch (error) {
    mostrarErrorEn('aprobar-error', error.message);
    await cargar();
  }
};

const reabrir = async (evento) => {
  evento.preventDefault();
  mostrarErrorEn('reabrir-error');
  const motivo = obtenerElemento('motivo-reabrir');
  try {
    const estado = await pedirApi(`${API_TRIMESTRE}/reabrir`, {
      method: 'POST',
      body: JSON.stringify({ motivo: motivo.value }),
    });
    motivo.value = '';
    render(estado);
    mostrarToast('info', `Trimestre ${estado.periodo} reabierto`, 'Ya se pueden hacer cambios. Recuerda aprobarlo de nuevo.');
  } catch (error) {
    mostrarErrorEn('reabrir-error', error.message);
  }
};

const inicializar = () => {
  obtenerElemento('btn-actualizar')?.addEventListener('click', cargar);
  obtenerElemento('form-aprobar')?.addEventListener('submit', aprobar);
  obtenerElemento('form-reabrir')?.addEventListener('submit', reabrir);
  cargar();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', inicializar);
} else {
  inicializar();
}
