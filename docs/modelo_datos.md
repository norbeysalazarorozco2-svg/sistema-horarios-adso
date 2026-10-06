# Modelo de datos — Sistema de Horarios ADSO

## 1. Instructor
| Campo | Tipo | Ejemplo |
|---|---|---|
| id | Entero | 101 |
| nombre | Texto | Javier Montoya |
| correo_sena | Texto | jmontoya@sena.edu.co |
| rol | Texto | Instructor |
| es_nuevo | Booleano | false |
| es_lider_ficha | Booleano | true |
| lidera_ficha_id | Entero / NULL | 3142868 |
| turnos_preferidos | Lista | Mañana, Tarde |
| disponibilidad | Objeto | Lun-Vie, 6:00-18:00 |
| rap_dominados | Lista | Construcción de software, Bases de datos |
| competencias | Lista | Desarrollo de software, Programación |
| horas_semanales | Decimal | 32 |
| horas_administrativas | Decimal | 4 |
| es_comodin | Booleano | false |
| horas_extra_autorizadas | Decimal | 0 |
| horas_extra_autorizadas_por | Entero / NULL | NULL |
| historial_carga | Lista de objetos | [{"trimestre": 2, "horas_totales": 40}] |

> `es_comodin` se calcula automáticamente cuando `turnos_preferidos` incluye
> mañana, tarde y noche (disponibilidad total).
> `historial_carga` guarda cuántas horas tuvo el instructor en trimestres
> anteriores, para aplicar la regla de equidad intertrimestral (ver
> `reglas-negocio.md`, punto 6): si llegó a 40h para tapar un hueco, el
> siguiente trimestre debe recibir menos carga.
> `horas_extra_autorizadas` y `horas_extra_autorizadas_por` solo se llenan
> cuando Mónica (gestora) aprueba pasar de 37h a un máximo de 40h.

## 2. Ficha
| Campo | Tipo | Ejemplo |
|---|---|---|
| id | Entero | 3142868 |
| programa | Texto | ADSO |
| jornada | Texto | Diurna |
| trimestre | Entero | 3 |
| instructor_lider_id | Entero | 101 |
| transversales_requeridas | Lista | Inglés, Comunicación |
| transversales_completas | Booleano | false |
| estado_alerta | Texto | Pendiente de transversal |
| estado_horario | Texto | Incompleto |
| prioridad | Entero (1 o 2) | 1 |

> `instructor_lider_id` permanece fijo durante el trimestre.
> `prioridad` se calcula a partir de `trimestre`: **1** para fichas de 1º a 5º
> (nunca pueden quedar con huecos), **2** para fichas de 6º y 7º (se permite
> hueco si no hay instructor disponible). Ver `reglas-negocio.md`, punto 4.

## 3. Solicitud de transversal
| Campo | Tipo | Ejemplo |
|---|---|---|
| id | Entero | 501 |
| ficha_id | Entero | 3142868 |
| solicitada_por | Entero | 101 |
| transversales | Lista | Inglés, Comunicación |
| fecha_solicitud | Fecha | 2026-09-01 |
| fecha_limite | Fecha | 2026-09-10 |
| estado | Texto | Pendiente |
| asignada_por | Entero / NULL | NULL |
| fecha_asignacion | Fecha / NULL | NULL |

## 4. Horario
| Campo | Tipo | Ejemplo |
|---|---|---|
| id | Entero | 9001 |
| ficha_id | Entero | 3142868 |
| instructor_id | Entero | 101 |
| dia | Texto | Lunes |
| hora_inicio | Hora | 06:00 |
| hora_fin | Hora | 08:30 |
| rap | Texto | Construcción de software |
| ambiente | Texto | Laboratorio 3 |
| tipo | Texto | Formación |
| estado | Texto | En concertación |
| bloqueado | Booleano | false |

> `bloqueado = true` en los bloques de transversales una vez Mónica los asigna
> (Paso 1 del orden de programación). El motor de asignación debe tratarlos
> como entrada fija y nunca reasignarlos ni moverlos. Ver `reglas-negocio.md`,
> punto 2.