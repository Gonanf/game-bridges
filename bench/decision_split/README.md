# Decision Split Benchmark

Simulador determinista y arnés de medición para desacoplar la arquitectura de decisión en dos niveles:
1. **Modelo chico (control por tick / reflejo reactivo)**: mide latencia estricta de decisión, cumplimiento de presupuesto temporal (`tick_compliance`) y tasa de acciones ilegales.
2. **Modelo grande (reacción estratégica / auditoría / diálogo)**: mide tasa de alucinación (`judge_hallucination`) y latencia de respuesta frente a ventanas de eventos reales y snapshots de estado.

El benchmark evalúa ambas capas sin depender de un motor de juego pesado ni de puentes de red externos.

---

## Mediciones de referencia del runner

Mediciones empíricas tomadas en el entorno local (4 GB VRAM Vulkan0):

| configuración | resultado |
|---|---|
| `max_tokens=12` sin `grammar` y sin desactivar thinking | **content vacío en todos los modelos probados**: los 12 tokens se van a `reasoning_content` |
| `grammar` GBNF del vocabulario legal + `chat_template_kwargs={"enable_thinking":false}` | etiqueta correcta; **MiniCPM5-1B p50 ≈ 125 ms** (primera llamada 2,0 s), **Qwen3.8-2B p50 ≈ 330 ms** (primera 6,8 s), en 4 GB de VRAM Vulkan0 |
| grande FrogNano-4B, prompt de reacción, 43 tokens | **48,7 s** de pared (frío, incluye carga), JSON válido |
| grande Sharp-MiniCPM5-2B, mismo prompt, 27 tokens | **26,3 s** de pared (frío), JSON válido |
| `Ornith-1.0-9B` | **no carga**: la raíz está al 99% y falla la descarga HF |

### Resultados reales del bench (medidos)

| corrida | configuración | resultado |
|---|---|---|
| chico, tiempo real | MiniCPM5-1B + GBNF + `enable_thinking=false`, 3 seeds × 120 ticks (360 decisiones), tick 500 ms | p50 458 ms, **p95 999,4 ms**, cold 15,8 s, invalid_rate 0,0 %, `tick_compliance=false`, action_diversity 0,028 |
| grande, replay | Sharp-MiniCPM5-2B sobre 24 ventanas (`out/windows-subset.jsonl`) | **0/24 alucinados (0,0 %)**, **4/24 unparseable (16,7 %)**, p50 25,2 s, p95 32,0 s |

**Condición de medición**: medido con **GPU compartida** (GPU use 93 %, otro `llama-server` en Vulkan0, VRAM 3,35/4,28 GB); el 125 ms de la tabla de arriba es con GPU libre, sin contención.

### Conclusiones de ingeniería
1. **El vocabulario cerrado se impone con grammar GBNF, no con prompt**: si se pide al LLM generar texto libre en 12 tokens, los modelos modernos con thinking agotan el presupuesto en tokens de razonamiento o generan texto decorativo. Con gramática GBNF y `chat_template_kwargs={"enable_thinking":false}`, el modelo está obligado a emitir únicamente una acción legal en 1-2 tokens.
2. **Penalidad de primera llamada**: la carga del modelo en VRAM toma entre 15× y 20× el tiempo de inferencia en régimen (2,0 s a 6,8 s en frío vs 125–330 ms en caliente).
3. **Restricción de GPU (`--models-max 1`)**: cuando el servidor local corre con `--models-max 1`, alternar entre chico y grande en cada tick descargaría y recargaría pesos continuamente. Por este motivo, la ejecución dividida se desacopla grabando ventanas (`--record-windows`) y reproduciéndolas después (`--replay-windows`).
4. **Fallo por forma vs. contenido en el grande**: el grande puede fallar por **forma** (16,7 % unparseable) más que por contenido (0 % alucinado) ⇒ el diseño necesita reintento/gramática de forma y `unparseable` se cuenta aparte de `hallucinated`.

---

## Cómo se corre

### 1. Modo Mock (sin red, simulación pura)
Ejecuta la corrida determinista con política scripted en el chico y generador fiel en el grande. No requiere servidor LLM:
```bash
python3 run.py --mock --seeds 1,2,3 --ticks 60 --out out/mock-summary.json
```

### 2. Modo Real Integrado (ambos modelos activos)
Si el runner soporta múltiples modelos simultáneos:
```bash
python3 run.py --seeds 1,2,3 --ticks 200 --tick-ms 500 \
  --small-url http://127.0.0.1:11434/v1/chat/completions --small-model MiniCPM5-1B \
  --big-url http://127.0.0.1:11434/v1/chat/completions --big-model Sharp-MiniCPM5-2B \
  --big-every 10 --out out/summary.json
```
*Modelos alternativos*: chico `Qwen3.8-2B`, grande `FrogNano-4B`.

### 3. Modo Desacoplado: Sólo Chico con Grabación de Ventanas
Ejecuta únicamente el modelo chico en tiempo real, registrando las ventanas de eventos y snapshots que se habrían enviado al grande:
```bash
python3 run.py --seeds 1 --ticks 200 --big-every 0 \
  --record-windows out/windows.jsonl \
  --small-url http://127.0.0.1:11434/v1/chat/completions --small-model MiniCPM5-1B \
  --out out/small-only.json
```

### 4. Modo Desacoplado: Replay del Modelo Grande
Carga el modelo grande en la GPU (sin necesidad de tener el modelo chico cargado) y evalúa la tasa de alucinación y latencia sobre las ventanas grabadas:
```bash
python3 run.py --replay-windows out/windows.jsonl \
  --big-url http://127.0.0.1:11434/v1/chat/completions --big-model Sharp-MiniCPM5-2B \
  --out out/big-replay.json
```

---

## Significado de los campos del summary

El JSON de resumen exporta la siguiente estructura:

- `config`: parámetros de la corrida (`seeds`, `ticks`, `tick_ms`, modelos, flags de gramática y mock).
- `per_seed`: métricas por cada semilla simulada:
  - `decisions`: total de ticks donde el chico eligió acción.
  - `p50_ms`: mediana de latencia del chico (ms).
  - `p95_ms`: percentil 95 de latencia del chico con interpolación lineal `(n-1)*0.95`.
  - `max_ms`: latencia máxima observada.
  - `cold_ms`: latencia de la primera decisión de la corrida (arranque en frío).
  - `p95_warm_ms`: percentil 95 descartando la primera llamada (régimen cálido).
  - `invalid_rate`: fracción de decisiones que no eran legales o fallaron el parseo.
  - `tick_compliance`: `p95_ms < tick_ms` (booleano).
  - `big`: métricas del modelo grande (`n` llamadas, `hallucinated` cantidad que alucinó, `rate` proporción alucinada, `unparseable` salidas que rompieron JSON, `p50_ms`, `p95_ms`).
- `pooled`: métricas acumuladas agregando todas las semillas.
- `quality`:
  - `survival_ticks`: ticks sobrevividos por el jugador antes de morir (o total de ticks si sobrevivió).
  - `damage_taken`: puntos de vida totales perdidos por el jugador (`p0`).
  - `action_diversity`: relación de etiquetas legales distintas ejecutadas sobre el total de decisiones.
  - `big_orders`: total de reacciones del grande que incluyeron una orden (`override` no nulo).
- `verdict`: síntesis legible sobre la conformidad del presupuesto temporal y estabilidad de inferencia.

---

## Qué NO mide este benchmark

1. **Calidad de partida en un juego real**: no simula Minecraft ni Factorio ni ajedrez completo; el mundo es un entorno sintético discreto en grilla 2D (0..31) enfocado en estrés de protocolo.
2. **Niceness o expresividad del engine**: no mide fluidez gráfica, físicas, animaciones ni renderizado.
3. **Costo en dólares o tokens de proveedores cloud**: se diseñó para medir modelos locales en hardware acotado (4 GB VRAM) bajo llama.cpp/Ollama.
4. **Comportamiento multi-jugador en producción**: el entorno simula hazards simples y npcs fijos para evaluar la frontera arquitectónica.
