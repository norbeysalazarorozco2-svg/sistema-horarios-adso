'use strict';

/* ============================================================
   MI_HORARIO.JS — Horario semanal del instructor
   Solo lectura: lo que el motor le asignó en el último horario
   generado por la gestora (fichas, competencias y ambientes).
   API: GET /api/v1/instructor/mi-horario
   ============================================================ */

const DIA_CORTO = { LUNES: 'Lun', MARTES: 'Mar', MIERCOLES: 'Mié', JUEVES: 'Jue', VIERNES: 'Vie' };
const JORNADA = (bloque) => (bloque < '12:00' ? 'Mañana' : bloque < '18:00' ? 'Tarde' : 'Noche');

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

const formatearRango = (bloque) => bloque.replace('-', '–');
const formatearHoras = (horas) => `${Number(horas).toLocaleString('es-CO', { maximumFractionDigits: 1 })}`;

const mostrarVacio = (titulo, texto) => {
  obtenerElemento('mi-horario-vacio-titulo').textContent = titulo;
  obtenerElemento('mi-horario-vacio-texto').textContent = texto;
  obtenerElemento('mi-horario-vacio').classList.remove('hidden');
  obtenerElemento('mi-horario-contenido').classList.add('hidden');
};

const crearSesion = (sesion) => {
  const tarjeta = crearElemento('div', `mi-horario-sesion mi-horario-sesion--${sesion.tipo}`);
  tarjeta.append(
    crearElemento('span', 'mi-horario-sesion__ficha', `Ficha ${sesion.ficha_id}`),
    crearElemento('span', 'mi-horario-sesion__materia', sesion.materia ?? ''),
    crearElemento('span', 'mi-horario-sesion__aula', sesion.aula ?? 'Ambiente por asignar'),
  );
  if (sesion.tipo === 'lider') {
    tarjeta.appendChild(crearElemento('span', 'mi-horario-sesion__etiqueta', '★ Líder'));
  }
  return tarjeta;
};

/* Solo se muestran las filas (bloques) en las que el instructor tiene clase. */
const renderGrilla = (datos) => {
  const grilla = obtenerElemento('mi-horario-grilla');
  const porCelda = new Map(datos.sesiones.map((s) => [`${s.dia}|${s.bloque}`, s]));
  const bloques = datos.bloques.filter((b) => datos.sesiones.some((s) => s.bloque === b));

  const celdas = [crearElemento('span', 'mi-horario-grilla__esquina')];
  datos.dias.forEach((dia) => {
    const cabecera = crearElemento('span', 'mi-horario-grilla__dia', DIA_CORTO[dia] ?? dia);
    cabecera.setAttribute('role', 'columnheader');
    celdas.push(cabecera);
  });

  bloques.forEach((bloque) => {
    const hora = crearElemento('span', 'mi-horario-grilla__hora');
    hora.setAttribute('role', 'rowheader');
    hora.append(
      crearElemento('span', 'mi-horario-grilla__jornada', JORNADA(bloque)),
      crearElemento('span', '', formatearRango(bloque)),
    );
    celdas.push(hora);

    datos.dias.forEach((dia) => {
      const sesion = porCelda.get(`${dia}|${bloque}`);
      const celda = crearElemento('div', `mi-horario-grilla__celda${sesion ? '' : ' mi-horario-grilla__celda--libre'}`);
      celda.setAttribute('role', 'cell');
      celda.setAttribute(
        'aria-label',
        sesion
          ? `${DIA_CORTO[dia]} ${formatearRango(bloque)}: ficha ${sesion.ficha_id}, ${sesion.materia}, ${sesion.aula}`
          : `${DIA_CORTO[dia]} ${formatearRango(bloque)}: sin clase`,
      );
      if (sesion) celda.appendChild(crearSesion(sesion));
      celdas.push(celda);
    });
  });

  grilla.replaceChildren(...celdas);
};

const cargar = async () => {
  try {
    const respuesta = await fetch('/api/v1/instructor/mi-horario', { headers: obtenerHeaders() });
    const datos = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) throw new Error(typeof datos.detail === 'string' ? datos.detail : 'No fue posible cargar tu horario.');

    const subtitulo = obtenerElemento('mi-horario-subtitulo');
    if (!datos.generado) {
      subtitulo.textContent = 'Tu horario semanal del trimestre.';
      mostrarVacio(
        'La gestora aún no ha generado el horario',
        'Cuando lo genere verás aquí tus fichas, competencias y ambientes. Mientras tanto, revisa que tu disponibilidad esté al día.',
      );
      return;
    }

    const fecha = new Date(datos.generado_en).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
    subtitulo.textContent = `Generado por la gestora el ${fecha}.`;

    if (datos.sesiones.length === 0) {
      mostrarVacio(
        'No tienes clases asignadas',
        'El horario generado no te asignó fichas. Si esperabas clases, revisa tu disponibilidad y habla con la gestora.',
      );
      return;
    }

    obtenerElemento('dato-horas').textContent = formatearHoras(datos.horas_semanales);
    obtenerElemento('dato-sesiones').textContent = String(datos.sesiones.length);
    obtenerElemento('dato-fichas').textContent = String(datos.fichas.length);
    renderGrilla(datos);
    obtenerElemento('mi-horario-contenido').classList.remove('hidden');
  } catch (error) {
    const aviso = obtenerElemento('mi-horario-error');
    aviso.textContent = error.message;
    aviso.classList.remove('hidden');
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', cargar);
} else {
  cargar();
}
