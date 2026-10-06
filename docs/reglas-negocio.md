# Reglas de negocio — Sistema de Horarios ADSO

> Basado en las reglas finales entregadas por Javi (30/09/2026).
> Las fichas ya vienen organizadas por el SENA — el sistema solo las **lee**, no las crea.

---

## 1. Carga horaria — Regla dura

| Concepto | Valor |
|---|---|
| Base | 33h formación + 4h administrativas = **37h semanales** |
| Margen normal de formación | 33h a 36h |
| Tope absoluto | **Nunca pasar de 40h.** El sistema bloquea automáticamente si se supera |
| Tope diario | Máximo **9 horas continuas** por instructor, por día |

---

## 2. Orden de programación (importante — define el flujo del motor)

1. **Paso 1 — Transversales primero:** Mónica (gestora) asigna primero las transversales.
   Una vez asignadas, son **inamovibles** — el motor no puede reasignarlas ni moverlas.
2. **Paso 2 — ADSO después:** el sistema toma los bloques libres que quedan (los no
   ocupados por transversales) y ahí asigna a los instructores de ADSO.

Esto significa que el motor de asignación **no corre sobre la disponibilidad completa
de la ficha**, sino sobre el "sobrante" después de las transversales.

### Inglés — transversal fija

La gestora fija Inglés en **todas las fichas, en todos los trimestres**, como parte del Paso 1:

| Jornada de la ficha | Horas semanales | Bloque |
|---|---|---|
| Mañana (Diurna) | 3 h | un bloque de 3 h (06–09 o 09–12) |
| Tarde | 3 h | un bloque de 3 h (12–15 o 15–18) |
| Noche (Nocturna) | 2 h | un bloque de 2 h (18–20 o 20–22) |

- Cada ficha recibe Inglés **exactamente una vez por semana** (un solo bloque). Una
  solicitud de transversales que incluya Inglés no le abre un segundo bloque.
- Por defecto, las fichas de un mismo trimestre y jornada tienen Inglés el mismo día
  (martes), en bloques distintos, para que no quede repartido en varios días.
- El bloqueo es **por ficha**: ese bloque queda `bloqueado = true` para la ficha y no
  se puede usar para formación técnica, para el bloque del líder ni para otro instructor
  de esa ficha.
- Un instructor de ADSO sí puede dictar a **otra** ficha en ese mismo horario.
- Solo la gestora puede mover la franja (pantalla *Líderes de ficha*). No puede ponerla
  sobre un bloque del líder de la ficha ni sobre el Inglés de otra ficha del mismo trimestre.
- El bloque es **recurrente**: se repite igual todas las semanas del trimestre. La gestora
  lo cambia o rota al configurar cada trimestre; al aprobarlo queda congelado hasta reabrirlo.
- Solo se ve en las vistas de la gestora (Líderes y horario consolidado). Las pantallas del
  instructor (Disponibilidad, Mi ficha) no muestran Inglés: el instructor marca su
  disponibilidad de lunes a viernes sin avisos de transversales.

---

## 3. Líder de ficha — Regla blanda

| Regla | Tipo |
|---|---|
| Mínimo 1 clase a la semana a su propia ficha | Obligatorio |
| Deseable 2 clases a la semana, en bloque, el mismo día | Blanda |
| Si la ficha necesita más horas de otro RAP, el líder **cede su segundo bloque** | Excepción válida — sigue siendo líder, solo se mueve de día |

---

## 4. Prioridad de fichas

| Prioridad | Fichas | Regla |
|---|---|---|
| **1** | 1º a 5º trimestre | **Nunca** pueden quedar con huecos |
| **2** | 6º y 7º trimestre | Se permite dejar hueco si no hay instructor disponible (son más autónomos) |

---

## 5. Gestión de huecos — Alertas

- Si un RAP queda sin instructor asignado → el sistema lanza una **alerta**.
- El sistema busca instructores que ya tienen 36-37h pero que dominan ese RAP, y los
  propone como **"tentativo para horas extra hasta 40h"**.
- **Solo Mónica (gestora) puede autorizar** esas horas extra.

---

## 6. Equidad entre trimestres

Si en un trimestre un instructor llegó a 40h para tapar un hueco, el sistema debe
**guardar ese historial** para que en el trimestre siguiente se le asigne
**menos carga**, compensando el sobreesfuerzo anterior.

---

## 7. Comodines

- Un instructor con **disponibilidad total** (mañana, tarde y noche) se considera
  **comodín**.
- Siempre se asigna en **bloque corrido** — ejemplo: 6am a 3pm, o 3pm a 10pm.
- **Nunca "picado"** (bloques sueltos con huecos entre medio).

---

## 8. Qué aprueba Mónica (gestora) — únicamente ella

- Aprobar al líder de ficha
- Aprobar las transversales (Paso 1 del orden de programación)
- Autorizar horas extra (de 37h a 40h) para tapar huecos
- Aprobar el trimestre final (cierre / publicación del horario)

---

## Notas para el motor de asignación (implementación)

- El "Paso 1 / Paso 2" del orden de programación implica que el motor debe recibir
  como **entrada fija** los bloques ya ocupados por transversales, no como variables
  a optimizar.
- La regla de equidad intertrimestral (punto 6) requiere que el modelo de `Instructor`
  guarde un historial de carga de trimestres anteriores (ver `modelo_datos.md`,
  campo `historial_carga`).
- La prioridad de fichas (punto 4) debe traducirse en el motor como una restricción
  de mayor peso para fichas de 1º-5º trimestre frente a las de 6º-7º.

---

## 9. Generación automática del horario (MVP)

La gestora elige el trimestre en su panel y pulsa **⚡ Generar horario automático**. El
motor (`app/core/motor.py`, voraz; reemplazable por el de OR-Tools) programa **todas las
fichas a la vez**, porque un instructor dicta en fichas de varios trimestres:

1. Inglés fijo de cada ficha (bloqueado) con un instructor de Inglés libre.
2. Bloques del líder de ficha.
3. Transversales del plan del trimestre (Ética, SST, Matemáticas…) más las aprobadas.
4. Formación técnica en el sobrante: competencia del instructor, **solo en franjas que él
   marcó en Disponibilidad**, máximo 9 h continuas por día y tope de 33 h de formación.
   Prioriza a quien ya dicta en la ficha y luego a quien tiene menos carga; quien debe
   compensar carga (§6) va al final.

Fichas de prioridad 1 se programan primero. Lo que no se puede programar queda como
**pendiente** visible para la gestora. Cada sesión lleva ficha, competencia o transversal,
instructor y ambiente. El instructor ve solo sus sesiones en **Mi horario**; la gestora
ve el consolidado y lo filtra por trimestre, jornada o ficha.
