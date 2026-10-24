# Frontera de Decisión: Arquitectura Dual Chico / Grande

Este documento define la frontera técnica y el contrato de desacople entre el modelo de control reflejo (modelo chico) y el modelo de control estratégico (modelo grande).

---

## 1. Qué decide el chico

El modelo chico corre en el bucle de tiempo real (por tick de motor o ciclo de control). Decide únicamente sobre un **vocabulario cerrado y tipado**, validable en tiempo constante contra el estado visible actual.

### Mapeo a primitivas reales de los bridges

Las primitivas reales de los bridges existentes se proyectan a la gramática cerrada del chico:

| Primitivas de bridges reales | Mapeo canónico chico | Semántica |
|---|---|---|
| `forward`, `left`, `right`, `jump`, `explore` (Minecraft / Factorio) | `goto:<id>` | Desplazamiento reactivo hacia una entidad o coordenada conocida |
| Maniobras evasivas, esquivar proyectil / mob hostil | `flee:<id>` | Retirada inmediata alejándose del peligro visible más próximo |
| `attack`, `dig`, combate cuerpo a cuerpo, uso de arma | `attack:<id>` | Interacción hostil o daño físico sobre un objetivo visible |
| Espera de tick, idle, sincronización de ciclo | `wait` | No emite acción; preserva stamina o espera actualización |
| Escalado explícito a la capa estratégica | `call_big` | Dispara una solicitud asíncrona de intervención al modelo grande |
| Movimiento algebraico legal (Ajedrez) | `move:<uci>` | Selección de jugada legal filtrada por el motor de ajedrez |
| Voto directo de fase (Werewolf / Social) | `vote:<id>` | Voto tabular sobre candidatos vivos |

### Criterio de asignación
- **Acciones por tick**: decisiones que no pueden esperar más de 100–300 ms sin degradar la física o la supervivencia.
- **Estado visible local**: sólo consume entidades en rango de visión y atributos numéricos directos (`hp`, `stamina`, `pos`, `dist`).
- **Cero generación de lenguaje natural**: no genera texto libre, pensamientos ni explicaciones.
- **Validación barata O(1)**: cualquier acción emitida se valida al instante con un simple lookup en `legal_actions`.

---

## 2. Qué decide el grande

El modelo grande es asíncrono y estratégico. No toca el bucle de física ni emite comandos motores elementales (no dice "caminá a la izquierda un tick").

### Responsabilidades exclusivas del grande
1. **Override de objetivo (`override`)**: cambiar la meta táctica del agente (por ejemplo, cambiar la orden de retirada a un contraataque coordinado o forzar un destino).
2. **Diálogo, narrativa y persona (`say`)**: comunicación con otros agentes, NPCs o humanos, manteniendo coherencia de rol.
3. **Ruptura de regla deliberada**: asumir riesgos calculados (ej. pasar a través de una zona de fuego para salvar a un aliado clave).
4. **Negociación social y deducción**: alianzas, acusaciones en juegos de votación oculta, análisis de patrones de engaño.
5. **Criterio**: opera cuando se requiere memoria histórica acumulada, razonamiento contrafáctico o generación lingüística.

---

## 3. Contrato entre capas

El desacople se basa en un **log append-only** de eventos inmutables (`event_id`) y snapshots periódicos. El modelo grande **jamás accede a los punteros internos del motor de juego**.

### Flujo de datos

```
+-----------------------------------------------------------------------------+
|                               MOTOR / SIMULADOR                            |
|  - Mantiene grilla, entidades, colisiones, hp, stamina                      |
|  - Emite tick cada N ms                                                     |
+-----------------------------------------------------------------------------+
         |                                                   ^
         | obs + legal_actions                               | apply(action)
         v                                                   |
+----------------------+                            +-------------------------+
|    MODELO CHICO      | ---(acción elegida)------> | Validación de Legalidad |
| (GBNF, <=12 tokens)  |                            +-------------------------+
+----------------------+                                     |
         |                                                   v Eventos generados
         | (emite call_big o tick regular)          +-------------------------+
         +----------------------------------------> |   LOG APPEND-ONLY       |
                                                    | [e1, e2, e3, e4, ...]   |
                                                    +-------------------------+
                                                                 |
                                       Ventana últimos K eventos | + Snapshot
                                                                 v
                                                    +-------------------------+
                                                    |      MODELO GRANDE      |
                                                    |  (Auditoría / Estratega)|
                                                    +-------------------------+
                                                                 |
                                   Emite: {"say", "override", "refs": [e_ids]}
                                                                 v
                                                    +-------------------------+
                                                    | Validador / Inyector    |
                                                    +-------------------------+
                                                                 |
                           ¿Orden ilegal / objetivo muerto?      |
                           +-------------------------------------+
                           |
                           v
              Emite `game_action_rejected` al Log
```

### Reglas del contrato
- **Referencias obligatorias (`refs`)**: el grande debe fundamentar toda directiva citando los `event_id` reales de la ventana observada. Si cita un evento inexistente, se registra como alucinación **H1**.
- **Vocabulario de órdenes**: el grande emite verbos de nivel comando (`goto`, `attack`, `say`, `interact`, `stop`), nunca primitivas de motor ni teclas directas.
- **Retroalimentación por fallo**: si la orden del grande no se puede cumplir en el mundo (ej. target muerto entre turnos), el puente emite un evento `rejected` al log; el estado no se corrompe.

---

## 4. Reglas duras de la arquitectura

1. **Cuota de escalado**: `call_big` tiene un rate-limit estricto (máximo una llamada cada N ticks, por defecto 10 ticks).
2. **Aislamiento de bajo nivel**: el grande tiene prohibido emitir comandos de traslación física directa.
3. **Fallback scripted inmediato**: si el chico no responde dentro de la ventana de tolerancia del tick, se ejecuta una política de resguardo fija (`wait` o `flee` al peligro visible más próximo).
4. **Inmutabilidad del estado**: el grande sólo añade propuestas de acción y eventos narrativos; nunca altera el estado del simulador directamente.
5. **El vocabulario cerrado se impone con grammar GBNF, no con prompt**:
   - Medición verificada: sin gramática y con thinking habilitado, con `max_tokens=12`, los modelos chicos devuelven `content` vacío porque consumen todo el presupuesto en `reasoning_content`.
   - Con gramática GBNF restringida a la regla `root ::= "accion1" | "accion2"` y `enable_thinking: false`, la latencia cae a **125 ms en MiniCPM5-1B** con **GPU libre** (sin contención) y la tasa de acciones ilegales es 0%. Bajo contención (GPU use 93 %, otro `llama-server` en Vulkan0, VRAM 3,35/4,28 GB) la medición real del bench da **p50 458 ms y p95 999,4 ms** con 0,0 % de acciones ilegales, es decir **999 ms > tick de 500 ms**: con GPU compartida el chico **no cumple el tick**.

---

## 5. Frontera de latencia por juego

| Entorno / Tarea | Tick del motor | Presupuesto del chico | Comportamiento si excede presupuesto |
|---|---|---|---|
| **Minecraft (cuerpo a cuerpo)** | ~50 ms (física) / ~500 ms (decisión útil) | <= 200 ms | Fallback scripted: retener último vector de movimiento o saltar/bloquear |
| **Factorio (ciclo logístico)** | ~1000 ms por plano | <= 400 ms | Espera tick (`wait`), mantiene inserción previa sin modificar cinta |
| **Ajedrez (Bullet / Blitz)** | 1 s a 5 s por jugada | <= 500 ms | Ejecuta jugada segura del libro de aperturas o heurística de captura |
| **Werewolf / Social deduction** | Por turno de votación | <= 300 ms (voto) | Vota al jugador más sospechoso según tabla previa o abstención |
| **Costo de primera llamada (Arranque en frío)** | 2.000 ms – 6.800 ms (medido) | N/A | **Bloqueante**: requiere precarga obligatoria del modelo en GPU antes de iniciar la partida o fallback scripted durante los primeros 10-15 ticks |

Los presupuestos de la tabla (200/400/500/300 ms) se sostienen **sólo con GPU exclusiva**; con GPU compartida el p95 medido es **999 ms**, así que el chico no cumple el tick de 500 ms y hace falta **GPU exclusiva para el modelo chico o subir el presupuesto a ~1 s** (y en ese caso aceptar que el chico deja de ser "reflejo por tick" en Minecraft, cuyo tick útil es 500 ms).

---

## 6. Anti-hack y calidad de juego

Evaluar un sistema de agentes basándose exclusivamente en el costo computacional genera un incentivo perverso: un agente que apaga el modelo grande y sólo hace `wait` tiene latencia mínima y cero costo de tokens, pero pierde la partida de inmediato.

### Detección en el benchmark
El summary monitorea explícitamente:
- `action_diversity`: relación entre tipos de acciones ejecutadas y el total de decisiones. Si el chico entra en bucles de un solo verbo, la diversidad colapsa a 0.
- `big_orders`: cuenta cuántas veces el grande intervino efectivamente con un `override`. Si el modelo grande no interviene o emite `null` permanentemente, `big_orders` es 0.
- `damage_taken` y `survival_ticks`: miden el resultado objetivo de la partida. Si el chico no esquiva o no ataca, la vida llega a 0 rápidamente.
- `unparseable`: cuenta cuántas respuestas del modelo grande rompieron formato y no pudieron ser parseadas como JSON válido (se mide y contabiliza separado de `hallucinated`).

La métrica de éxito es la **efectividad de juego combinada**: supervivencia máxima con cumplimiento temporal estricto del chico y tasa de alucinación cero en el grande.

### 6.1 El riesgo del grande no es alucinar, es no devolver JSON

- En la medición de replay (24 ventanas, Sharp-MiniCPM5-2B) las alucinaciones de `refs` fueron **0/24 (0,0 %)**, pero **4/24 (16,7 %)** no devolvieron JSON parseable (`unparseable`).
- **Conclusión de diseño**: el validador del grande **no puede asumir JSON bien formado**. Necesita **reintento acotado y/o gramática de forma (JSON schema/GBNF de salida)** para el grande, y un camino de degradación (ignorar la respuesta y quedarse con la última orden válida) cuando el parseo falla.
- **`unparseable` se cuenta aparte de `hallucinated`**: alucinar = JSON válido citando `event_id` inexistentes; `unparseable` = no se pudo parsear. Mezclarlos esconde el problema real de protocolo detrás de una tasa de alucinación que da 0 %.
- **Latencia del grande en esa corrida**: p50 25,2 s (25.179 ms), p95 32,0 s (32.018 ms) ⇒ confirma que el grande es asíncrono y no puede estar en el bucle de tick.

---

## 7. Aspectos no verificados y limitaciones

1. **Motores reales de producción**: no se evaluó todavía contra el tick server real de Minecraft Java Edition ni contra la API C++ de Factorio.
2. **Partidas de larga duración**: las mediciones cubren ventanas de hasta cientos de ticks; falta evaluar degradación de memoria de contexto tras miles de eventos acumulados.
3. **Disponibilidad de GPU**: el benchmark asume un host local con 4 GB de VRAM compartida con Vulkan0. En entornos con múltiples GPU o instancias cloud con VRAM holgada, no es necesario el modo `--record-windows` / `--replay-windows`.
4. **Fallo de descarga de Ornith-1.0-9B**: no se pudo evaluar este modelo porque la partición raíz del entorno de prueba se encontraba al 99% de capacidad y abortó la descarga desde HuggingFace.
