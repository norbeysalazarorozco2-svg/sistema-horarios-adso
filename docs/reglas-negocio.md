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
