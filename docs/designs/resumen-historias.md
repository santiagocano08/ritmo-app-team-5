# PulsoFlota · Resumen de historias y mock-ups (UXUI-01 a UXUI-12)

PulsoFlota es una central web para despachadores y gestores de un sistema integrado de transporte. El despachador ve el corredor en vivo, recibe recomendaciones para evitar agrupamientos y huecos de buses, y decide si las aplica. El gestor consulta indicadores de calidad del servicio por operador. El sistema recomienda y la persona decide.

Cada historia tiene tres pantallas en el lienzo: la ficha de la historia, la versión de escritorio (1280 px) y la de celular (390 px). Las capturas están en `historias/`, `escritorio/` y `celular/`, con el nombre `UXUIxx-historia`, `UXUIxx-escritorio` y `UXUIxx-celular`.

---

## Índice

| Historia | Tema | Rol | Vuelta | Carril |
|---|---|---|---|---|
| UXUI-01 | Iniciar sesión | Despachador / gestor | 2 · Valor | Adaptativo + revisión de seguridad |
| UXUI-02 | Recuperar contraseña | Cualquier usuario | 2 · Valor | Depende de UXUI-01 |
| UXUI-03 | Navegación principal por rol y estado del dato | Despachador / gestor | 2 · Valor | Adaptativo · hipótesis |
| UXUI-04 | Ver el corredor en vivo | Despachador | 2 · Valor | Adaptativo · consume el contrato |
| UXUI-05 | Atender una recomendación de regularidad | Despachador | 2 · Valor | Mixto · tiempo real firme |
| UXUI-06 | Indicadores de calidad del servicio | Gestor | 2 · Valor | Disciplinado · afecta el pago |
| UXUI-07 | Bandeja de Alertas | Despachador | 2 · Valor | Adaptativo · depende de UXUI-05 |
| UXUI-08 | Consultar el plan del día | Despachador | 2 · Valor | Adaptativo · sin tiempo real |
| UXUI-09 | Calidad del dato por operador | Gestor | 1 · Dato y fábrica | Disciplinado · DataOps |
| UXUI-10 | Hacer llegar la instrucción al conductor | Despachador | 2 · Valor | Mixto · depende de UXUI-05 |
| UXUI-11 | Ver si la recomendación funcionó | Despachador | 2 · Valor | Adaptativo · depende de UXUI-10 |
| UXUI-12 | Reportar una novedad operativa | Despachador | 2 · Valor | Mixto · afecta las recomendaciones |

---

## UXUI-01 · Iniciar sesión

**Relacionada con:** acceso a la aplicación.

El usuario entra con su usuario institucional y contraseña y llega a la vista inicial de su rol.

- **Escritorio:** dos paneles. A la izquierda un panel azul marino con la marca y el mensaje «Central del despachador». A la derecha el formulario de 400 px con usuario, contraseña (con botón Mostrar/Ocultar) y el enlace «¿Olvidaste tu contraseña?».
- **Celular:** una columna con campos y botón de 48 px, el botón a todo el ancho.
- **Estados:** normal, error («Usuario o contraseña incorrectos», sin indicar cuál falló) y cuenta bloqueada tras 5 intentos fallidos en 15 min, con la hora de desbloqueo.
- **Por definir con el cliente:** si el gestor entra con inicio de sesión único (SSO) institucional.

## UXUI-02 · Recuperar contraseña

**Relacionada con:** acceso, continuación de UXUI-01.

Restablecer la contraseña con un enlace enviado al correo, sin depender de soporte en pleno turno.

- **Flujo en tres pasos:** pedir el enlace, ver la confirmación y definir la nueva contraseña.
- **Reglas visibles:** el mensaje de confirmación es siempre el mismo exista o no la cuenta; el enlace es de un solo uso y vence a los 30 min; la nueva contraseña exige 12 caracteres o más, una letra y un número, con requisitos marcados en vivo.
- **Al guardar:** se cierran todas las sesiones abiertas y se vuelve a Iniciar sesión con aviso de éxito.
- **Escritorio:** tarjeta centrada de máximo 440 px. **Celular:** ancho completo con márgenes de 20 px.
- **Por definir:** quién desbloquea una cuenta bloqueada antes de los 15 min.

## UXUI-03 · Navegación principal por rol y estado del dato

**Relacionada con:** estructura de la aplicación y confianza en el dato.

El marco fijo de la app: muestra las secciones del rol, el corredor activo, la hora y si los datos están al día.

- **Menú por rol:** el despachador ve Central en vivo, Alertas y Plan del día; el gestor ve Indicadores de calidad y Plan del día. Una URL fuera del rol responde «Sin permiso» (403).
- **Indicador del dato:** En vivo, Estimado (cayó una fuente) o Sin datos, siempre con texto y con la hora del último evento. En los dos últimos aparece un banner explicativo.
- **Escritorio:** barra lateral de 248 px y barra superior. **Celular:** barra superior compacta y navegación inferior de máximo 4 ítems; el perfil y Cerrar sesión van en «Más».
- **Sesión:** cerrar sesión la invalida, y hay aviso 2 min antes de que expire.
- **Hipótesis:** «En vivo» si el último evento llegó hace menos de 30 s; «Sin datos» tras 2 min sin eventos.

## UXUI-04 · Ver el corredor en vivo

**Relacionada con:** monitoreo en tiempo real, pantalla principal del despachador.

Diagrama del corredor con la posición de cada bus y su intervalo con el bus de adelante, para detectar agrupamientos y huecos a tiempo.

- **Escritorio:** cuatro indicadores arriba (buses en servicio, intervalo programado, agrupamientos, huecos), diagrama horizontal con estaciones y buses, y tabla de buses con estado y tipo de dato.
- **Celular:** el corredor se lee de arriba abajo, con los buses entre sus paradas.
- **Reglas:** la posición se actualiza con un retraso de 10 s o menos. Un bus es «Agrupado» si su intervalo es menos del 50 % del programado y «Hueco» si pasa del 150 %. Un bus cuya fuente no responde se dibuja con borde punteado y la etiqueta «Estimado».
- **Hipótesis:** los umbrales de 50 % y 150 %. Los datos del mock-up son de ejemplo.
- **Control de prototipo:** un botón punteado «Simular recomendación» lleva a UXUI-05.

## UXUI-05 · Atender una recomendación de regularidad

**Relacionada con:** recomendaciones del sistema y decisión del despachador.

Cuando se forma un agrupamiento o un hueco, el sistema propone una acción concreta con su efecto esperado, y el despachador la aplica o la descarta dejando registro.

- **Contenido de cada recomendación:** acción, bus, parada, duración, motivo, efecto esperado en la espera excesiva (EWT) y confianza del dato.
- **Reglas:** aparece en 10 s o menos; sin respuesta en 2 min vence; nunca hay más de 3 activas; la retención no supera 90 s; descartar exige un motivo; dos recomendaciones sobre el mismo tramo se marcan «en conflicto».
- **Escritorio:** panel lateral de 400 px junto al corredor, con la zona afectada resaltada y un historial de decisiones del turno. **Celular:** aviso arriba y hoja inferior con la lista y los botones al alcance del pulgar.
- **Riesgo que atiende:** fatiga de alertas. **Por definir:** el canal con el que el despachador avisa al conductor.

## UXUI-06 · Indicadores de calidad del servicio

**Relacionada con:** pago a operadores por calidad (rol gestor).

El gestor consulta P(abordar ≤ t) y la espera excesiva (EWT) por operador y franja, junto con cuánto dato confiable las respalda.

- **Escritorio:** filtros (fecha, corredor, franja y t de 5, 10 o 15 min), tres indicadores y tabla por operador. **Celular:** resumen de filtros en una línea y una tarjeta por operador.
- **Reglas:** cada valor muestra su cobertura (% de eventos válidos y % estimados); con menos de 90 % el operador se marca «No apto para pago». Solo se usan eventos que pasaron la compuerta del dato. La tabla se exporta a CSV.
- **Por definir con el cliente:** el umbral de 90 % y la fórmula de pago.

## UXUI-07 · Bandeja de Alertas

**Relacionada con:** seguimiento de avisos y recomendaciones del turno.

Una bandeja con todo lo que el sistema avisó durante el turno, para retomar lo que se cerró sin decidir.

- **Tres pestañas con contador:** Activas (las mismas recomendaciones de UXUI-05), Avisos del dato e Historial.
- **Avisos del dato:** fuente caída, bus sin señal más de 2 min o eventos rechazados. Indican qué afecta y desde cuándo, y se marcan resueltos cuando el dato vuelve. No suenan.
- **Historial:** filtra por resultado (aplicada, descartada, vencida) y muestra hora, acción, motivo y quién decidió.
- **Escritorio:** pestañas y tablas. **Celular:** pestañas en segmento y tarjetas.
- **Abrir una activa** lleva a la central con esa recomendación abierta.

## UXUI-08 · Consultar el plan del día

**Relacionada con:** programación, demanda y operación sin datos en vivo.

Muestra las salidas programadas desde el transbordo junto a las reales, y la demanda esperada del Metro, como guía cuando no hay datos en vivo.

- **Salidas:** hora programada, bus, hora real y desviación; más de 2 min se marca «Atrasada» o «Adelantada».
- **Demanda esperada:** por franjas de 30 min, calculada con la afluencia histórica del Metro, junto al intervalo planeado.
- **Al abrir:** se ubica en la hora actual con una línea «Ahora» y la próxima salida resaltada. Sin datos en vivo, las salidas reales aparecen como «Sin dato».
- **Escritorio:** barras de demanda y tabla. **Celular:** barras compactas y lista de salidas.
- **Solo lectura:** muestra quién cargó el plan y cuándo. **Por definir:** quién lo carga y con qué frecuencia.

## UXUI-09 · Calidad del dato por operador

**Relacionada con:** confianza en los indicadores de pago (rol gestor, vuelta 1 · Dato y fábrica).

El gestor ve cuántos eventos envía cada operador, cuántos se rechazan y por qué, la latencia y los huecos por bus.

- **Por operador y día:** eventos recibidos, % rechazados, latencia p95 y huecos.
- **Detalle del operador:** causas de rechazo (duplicado, fuera del contrato, posición imposible, hora fuera de rango) y buses con más huecos.
- **Marcas:** «Revisar» si el rechazo pasa de 5 % o la latencia p95 de 10 s; «Posible manipulación» para patrones sospechosos, siempre para revisión humana, nunca sanción automática.
- **Escritorio:** tabla y detalle del operador elegido. **Celular:** tarjetas que se abren con el detalle.
- **Impacto en UXUI-03:** el menú del gestor suma «Calidad del dato».

## UXUI-10 · Hacer llegar la instrucción al conductor

**Relacionada con:** ejecución de las recomendaciones aplicadas.

Después de aplicar una recomendación, el despachador envía la instrucción al conductor y sigue su estado.

- **Estados:** Enviada, Recibida (el conductor confirma) y Ejecutada (los datos muestran que se cumplió). Sin confirmación en 30 s se marca «Sin confirmación» y se puede reenviar o avisar por radio.
- **Reglas:** la instrucción llega a la consola del bus en 5 s o menos; sin consola o con la fuente caída solo se ofrece la radio; una retención se da por ejecutada si el bus permanece la duración indicada más o menos 15 s.
- **Escritorio:** seguimiento en el panel lateral, con lo que ve el conductor. **Celular:** tarjeta de seguimiento a pantalla completa.
- **Supuesto fuerte:** los buses tienen consola para recibir mensajes; hay que validarlo con los operadores. La app del conductor queda fuera.

## UXUI-11 · Ver si la recomendación funcionó

**Relacionada con:** aprendizaje y evaluación de las recomendaciones.

Minutos después de ejecutar una recomendación, muestra cómo cambiaron el intervalo y la espera excesiva.

- **Gráfica:** intervalo entre los buses involucrados desde 6 min antes hasta 10 min después, junto al intervalo programado.
- **Resultado:** «Funcionó» (logró al menos 50 % del efecto esperado), «Efecto parcial», «No funcionó» o «Sin dato suficiente» (cobertura menor a 90 %). Hay un resumen del turno.
- **Se accede** desde el Historial de Alertas (UXUI-07).
- **Nota en pantalla:** los resultados evalúan las recomendaciones, no al despachador, y el resultado es una señal, no una prueba.
- **Escritorio:** lista del turno y detalle con gráfica. **Celular:** tarjetas con una gráfica pequeña.

## UXUI-12 · Reportar una novedad operativa

**Relacionada con:** contexto que los datos no ven, y su efecto en las recomendaciones.

El despachador reporta en segundos una novedad (bus varado, parada cerrada, desvío, conductor ausente) para que el sistema la tenga en cuenta.

- **Formulario:** tipo, bus o parada afectada y duración estimada (o «hasta nuevo aviso»); la nota es opcional. Se completa en menos de 15 s.
- **Efecto:** un bus varado sale del cálculo de intervalos; una parada cerrada no se usa para retenciones. Las recomendaciones afectadas se recalculan y se marcan «Recalculada por novedad».
- **Visibilidad:** la novedad se ve en el diagrama y en Alertas hasta cerrarse; queda registrado quién la reportó y cuándo. El gestor la ve como contexto en sus indicadores.
- **Escritorio:** formulario en el panel lateral sin perder de vista el corredor. **Celular:** formulario a pantalla completa con el botón abajo.
- **Por definir con el cliente:** si una novedad ajena al operador, como un cierre vial, excluye esas horas del cálculo de pago (UXUI-06).

---

## Relación entre historias

- **Acceso:** UXUI-01 → UXUI-02 → UXUI-03.
- **Despachador, tiempo real:** UXUI-04 → UXUI-05 → UXUI-10 → UXUI-11, con UXUI-07 (bandeja) y UXUI-12 (novedades) alrededor.
- **Despachador, sin tiempo real:** UXUI-08.
- **Gestor:** UXUI-06 (indicadores) y UXUI-09 (calidad del dato). UXUI-06 depende de la cobertura que mide UXUI-09.
- **Pantalla compartida:** UXUI-03 enmarca a todas; el menú cambia según el rol.
