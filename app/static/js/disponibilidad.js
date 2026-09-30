/**
 * disponibilidad.js
 * ─────────────────────────────────────────────────────────────
 * Módulo de cliente para la Matriz de Disponibilidad de Instructores.
 * Sistema de Horarios ADSO — SENA
 *
 * Responsabilidades:
 *  1. Mantener el estado de bloques seleccionados en memoria.
 *  2. Toggle de la clase `.selected` al hacer clic / Enter en celdas.
 *  3. Dinámica de RAPs según la competencia seleccionada.
 *  4. Validar competencia, RAP y mínimo un bloque antes de enviar.
 *  5. Enviar el payload JSON al endpoint POST /api/v1/instructor/disponibilidad.
 *  6. Mostrar notificaciones tipo toast sin recargar la página.
 * ─────────────────────────────────────────────────────────────
 */

'use strict';

/* ═══════════════════════════════════════════════════════════
   ESTADO DE LA APLICACIÓN
   ═══════════════════════════════════════════════════════════ */

/** @type {Set<string>}  Claves únicas: `"DIA|BLOQUE"` */
const estadoSeleccionado = new Set();

/** Mapa de RAPs por código de competencia (datos de demostración) */
const RAPS_POR_COMPETENCIA = {
  'COMP-001': [
    { value: 'RAP-001-1', label: 'RAP 1 · Modelar procesos de negocio' },
    { value: 'RAP-001-2', label: 'RAP 2 · Diseñar arquitectura de software' },
    { value: 'RAP-001-3', label: 'RAP 3 · Documentar requerimientos' },
  ],
  'COMP-002': [
    { value: 'RAP-002-1', label: 'RAP 1 · Implementar lógica de negocio' },
    { value: 'RAP-002-2', label: 'RAP 2 · Aplicar patrones de diseño' },
    { value: 'RAP-002-3', label: 'RAP 3 · Desarrollar pruebas unitarias' },
  ],
  'COMP-003': [
    { value: 'RAP-003-1', label: 'RAP 1 · Diseñar modelo relacional' },
    { value: 'RAP-003-2', label: 'RAP 2 · Optimizar consultas SQL' },
  ],
  'COMP-004': [
    { value: 'RAP-004-1', label: 'RAP 1 · Construir APIs RESTful' },
    { value: 'RAP-004-2', label: 'RAP 2 · Integrar frontend y backend' },
    { value: 'RAP-004-3', label: 'RAP 3 · Implementar autenticación' },
  ],
  'COMP-005': [
    { value: 'RAP-005-1', label: 'RAP 1 · Configurar entornos de CI/CD' },
    { value: 'RAP-005-2', label: 'RAP 2 · Desplegar en la nube' },
  ],
};

/* ═══════════════════════════════════════════════════════════
   REFERENCIAS AL DOM
   ═══════════════════════════════════════════════════════════ */

/** @returns {NodeListOf<HTMLElement>} */
const getBloques = () => document.querySelectorAll('.time-block');

const getContador       = () => document.getElementById('contador-bloques');
const getBtnGuardar     = () => document.getElementById('btn-guardar');
const getBtnLimpiar     = () => document.getElementById('btn-limpiar');
const getBtnSiguiente   = () => document.getElementById('btn-siguiente');
const getSelectComp     = () => document.getElementById('select-competencia');
const getSelectRap     = () => document.getElementById('select-rap');
const getNotifContainer= () => document.getElementById('dispon-notifications');

/* ═══════════════════════════════════════════════════════════
   OBTENCIÓN DE CREDENCIALES Y HEADERS HTTP
   ═══════════════════════════════════════════════════════════ */

/** @returns {string} Token JWT de sesión, si existe. */
const leerToken = () => localStorage.getItem('access_token') ?? '';

/** @returns {Object} Headers comunes para las peticiones a la API. */
const apiHeaders = () => {
  const token = leerToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
  };
};

/* ═══════════════════════════════════════════════════════════
   UTILIDADES DE ESTADO
   ═══════════════════════════════════════════════════════════ */

/**
 * Genera la clave única de un bloque.
 * @param {string} dia
 * @param {string} bloque
 * @returns {string}
 */
const buildKey = (dia, bloque) => `${dia}|${bloque}`;

/**
 * Actualiza el contador visual de bloques seleccionados.
 */
const actualizarContador = () => {
  const contador = getContador();
  if (!contador) return;
  contador.textContent = estadoSeleccionado.size;
};

const ocultarSiguiente = () => {
  const btnSiguiente = getBtnSiguiente();
  if (!btnSiguiente) return;
  btnSiguiente.hidden = true;
  btnSiguiente.disabled = true;
};

const mostrarSiguiente = () => {
  const btnSiguiente = getBtnSiguiente();
  if (!btnSiguiente) return;
  btnSiguiente.hidden = false;
  btnSiguiente.disabled = false;
};

/* ═══════════════════════════════════════════════════════════
   LÓGICA DE TOGGLE DE CELDAS
   ═══════════════════════════════════════════════════════════ */

/**
 * Alterna el estado de un bloque horario.
 * @param {HTMLElement} celda - El elemento `.time-block` clicado.
 */
const toggleBloque = (celda) => {
  if (celda.classList.contains('disabled')) return;

  const dia    = celda.dataset.dia;
  const bloque = celda.dataset.bloque;
  const key    = buildKey(dia, bloque);

  if (estadoSeleccionado.has(key)) {
    estadoSeleccionado.delete(key);
    celda.classList.remove('selected');
    celda.setAttribute('aria-pressed', 'false');
  } else {
    estadoSeleccionado.add(key);
    celda.classList.add('selected');
    celda.setAttribute('aria-pressed', 'true');
  }

  actualizarContador();
  ocultarSiguiente();
};

/**
 * Limpia todos los bloques seleccionados.
 * @param {boolean} [silencioso=false] - Si `true`, no muestra el toast informativo.
 */
const limpiarSeleccion = (silencioso = false) => {
  estadoSeleccionado.clear();

  getBloques().forEach((celda) => {
    celda.classList.remove('selected');
    celda.setAttribute('aria-pressed', 'false');
  });

  actualizarContador();
  ocultarSiguiente();
  if (!silencioso) {
    mostrarToast('info', 'Selección limpiada', 'Todos los bloques han sido deseleccionados.');
  }
};

/* ═══════════════════════════════════════════════════════════
   SISTEMA DE NOTIFICACIONES TOAST
   ═══════════════════════════════════════════════════════════ */

const ICONOS_TOAST = { success: '✅', error: '❌', info: 'ℹ️' };

/**
 * Crea y muestra un toast de notificación.
 * @param {'success'|'error'|'info'} tipo
 * @param {string} titulo
 * @param {string} [mensaje]
 * @param {number} [duracion=4000] - Milisegundos antes de auto-cerrar.
 */
const mostrarToast = (tipo, titulo, mensaje = '', duracion = 4000) => {
  const container = getNotifContainer();
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${tipo}`;
  toast.setAttribute('role', 'alert');

  const icon = document.createElement('span');
  icon.className = 'toast__icon';
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = ICONOS_TOAST[tipo] ?? 'ℹ️';

  const contenido = document.createElement('div');
  const encabezado = document.createElement('strong');
  encabezado.textContent = titulo;
  contenido.appendChild(encabezado);
  if (mensaje) {
    const detalle = document.createElement('span');
    detalle.style.opacity = '0.85';
    detalle.style.fontSize = '0.8rem';
    detalle.textContent = mensaje;
    contenido.appendChild(document.createElement('br'));
    contenido.appendChild(detalle);
  }

  toast.appendChild(icon);
  toast.appendChild(contenido);
  container.appendChild(toast);

  // Auto-remover con animación de salida
  const remover = () => {
    toast.classList.add('removing');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  };

  const timer = setTimeout(remover, duracion);

  // Click para cerrar manualmente
  toast.addEventListener('click', () => {
    clearTimeout(timer);
    remover();
  });
};

/* ═══════════════════════════════════════════════════════════
   DINÁMICA DE RAPs
   ═══════════════════════════════════════════════════════════ */

/**
 * Popula el select de RAPs según la competencia elegida.
 * @param {string} codigoCompetencia
 */
const cargarRaps = (codigoCompetencia) => {
  const selectRap = getSelectRap();
  if (!selectRap) return;

  // Limpiar opciones anteriores
  selectRap.innerHTML = '';

  if (!codigoCompetencia) {
    selectRap.innerHTML = '<option value="">— Selecciona primero una competencia —</option>';
    selectRap.disabled = true;
    return;
  }

  const raps = RAPS_POR_COMPETENCIA[codigoCompetencia] ?? [];

  if (raps.length === 0) {
    selectRap.innerHTML = '<option value="">Sin RAPs disponibles</option>';
    selectRap.disabled = true;
    return;
  }

  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = '— Selecciona un RAP —';
  selectRap.appendChild(placeholder);

  raps.forEach(({ value, label }) => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = label;
    selectRap.appendChild(opt);
  });

  selectRap.disabled = false;
};

/* ═══════════════════════════════════════════════════════════
   ENVÍO A LA API — POST /api/v1/instructor/disponibilidad
   ═══════════════════════════════════════════════════════════ */

/**
 * Construye el payload a enviar a partir del estado actual.
 * @returns {{ competencia: string, rap: string, bloques: Array<{dia:string, bloque:string}> }}
 */
const construirPayload = () => {
  const selectComp = getSelectComp();
  const selectRap  = getSelectRap();

  const bloques = [...estadoSeleccionado].map((key) => {
    const [dia, bloque] = key.split('|');
    return { dia, bloque };
  });

  return {
    competencia: selectComp?.value ?? '',
    rap:         selectRap?.value  ?? '',
    bloques,
  };
};

/**
 * Valida el payload antes de enviarlo.
 * @param {{ competencia: string, rap: string, bloques: Array }} payload
 * @returns {{ valido: boolean, errores?: string[] }}
 */
const validarPayload = (payload) => {
  const errores = [];

  if (!String(payload.competencia ?? '').trim()) {
    errores.push('Debes seleccionar una competencia.');
  }

  if (!String(payload.rap ?? '').trim()) {
    errores.push('Debes seleccionar un RAP.');
  }

  if (payload.bloques.length === 0) {
    errores.push('Debes seleccionar al menos un bloque de horario.');
  }

  if (errores.length > 0) {
    return { valido: false, errores };
  }
  return { valido: true };
};

/**
 * Envía la disponibilidad al backend mediante Fetch API.
 */
const guardarDisponibilidad = async () => {
  const payload = construirPayload();
  const validacion = validarPayload(payload);

  if (!validacion.valido) {
    const resumen = validacion.errores.join(' ');
    mostrarToast('error', 'Formulario incompleto', resumen, 6000);
    return;
  }

  const payloadGuardado = JSON.stringify(payload);
  const btnGuardar = getBtnGuardar();
  ocultarSiguiente();

  // Estado de carga
  if (btnGuardar) {
    btnGuardar.disabled = true;
    btnGuardar.classList.add('saving');
    btnGuardar.innerHTML = `
      <span class="spinner" aria-hidden="true"></span>
      Guardando…
    `;
  }

  try {
    const respuesta = await fetch('/api/v1/instructor/disponibilidad', {
      method:  'POST',
      headers: apiHeaders(),
      body:    JSON.stringify(payload),
    });

    const datos = await respuesta.json();

    if (respuesta.ok) {
      mostrarToast(
        'success',
        '¡Disponibilidad guardada!',
        `Se registraron ${datos.bloques_recibidos ?? payload.bloques.length} bloque(s) correctamente. Ya puedes continuar al perfil.`,
        5000
      );
      if (payloadGuardado === JSON.stringify(construirPayload())) {
        mostrarSiguiente();
      }
    } else {
      const detalle = datos?.detail ?? 'Ocurrió un error en el servidor.';
      const esUnauthorized = respuesta.status === 401;

      mostrarToast(
        'error',
        esUnauthorized ? 'Sesión no iniciada' : 'Error al guardar',
        esUnauthorized
          ? 'Debes iniciar sesión para guardar tu disponibilidad.'
          : detalle,
        6000
      );
    }
  } catch (error) {
    console.error('[disponibilidad.js] Error de red:', error);
    mostrarToast(
      'error',
      'Error de conexión',
      'No se pudo conectar con el servidor. Verifica tu conexión e inténtalo de nuevo.',
      6000
    );
  } finally {
    // Restaurar botón
    if (btnGuardar) {
      btnGuardar.disabled = false;
      btnGuardar.classList.remove('saving');
      btnGuardar.innerHTML = '💾 Guardar disponibilidad';
    }
  }
};

/* ═══════════════════════════════════════════════════════════
   REGISTRO DE EVENT LISTENERS
   ═══════════════════════════════════════════════════════════ */

/**
 * Inicializa todos los event listeners de la página.
 */
const inicializar = () => {
  // ── Celdas de la grilla ──
  getBloques().forEach((celda) => {
    // Clic con ratón
    celda.addEventListener('click', () => toggleBloque(celda));

    // Accesibilidad: activar con teclado (Enter / Espacio)
    celda.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleBloque(celda);
      }
    });
  });

  // ── Botón Guardar ──
  const btnGuardar = getBtnGuardar();
  if (btnGuardar) {
    btnGuardar.addEventListener('click', guardarDisponibilidad);
  }

  const btnSiguiente = getBtnSiguiente();
  if (btnSiguiente) {
    btnSiguiente.addEventListener('click', () => {
      window.location.href = '/perfil-instructor';
    });
  }

  // ── Botón Limpiar ──
  const btnLimpiar = getBtnLimpiar();
  if (btnLimpiar) {
    btnLimpiar.addEventListener('click', () => limpiarSeleccion());
  }

  // ── Select de Competencias ──
  const selectComp = getSelectComp();
  if (selectComp) {
    selectComp.addEventListener('change', (e) => {
      ocultarSiguiente();
      cargarRaps(e.target.value);
    });
  }

  const selectRap = getSelectRap();
  if (selectRap) {
    selectRap.addEventListener('change', ocultarSiguiente);
  }

  // Inicializar contador en 0
  actualizarContador();

  console.info('[disponibilidad.js] Módulo iniciado correctamente ✓');
};

/* ── Bootstrap ── */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', inicializar);
} else {
  inicializar();
}
