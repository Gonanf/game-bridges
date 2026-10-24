# Reporte de Documentación de Mediciones del Bench

## Secciones modificadas por archivo

### `docs/FRONTERA.md`
- **§4 (Reglas duras de la arquitectura - ítem 5)**: Se calificó la medición de 125 ms como correspondiente a GPU libre (sin contención) y se incorporaron los resultados bajo contención de GPU compartida (p50 458 ms, p95 999,4 ms, 0,0 % acciones ilegales, 999 ms > 500 ms tick).
- **§5 (Frontera de latencia por juego)**: Se añadió un párrafo debajo de la tabla aclarando que los presupuestos temporales aplican únicamente con GPU exclusiva, contrastándolo con el p95 medido de 999 ms bajo GPU compartida y la necesidad de GPU exclusiva o ampliación del presupuesto a ~1 s.
- **§6 (Anti-hack y calidad de juego - Detección en el benchmark)**: Se agregó la métrica `unparseable` al listado monitoreado por el benchmark, separándola de `hallucinated`.
- **§6.1 (Nueva subsección: "El riesgo del grande no es alucinar, es no devolver JSON")**: Se documentaron los resultados de replay (0/24 alucinaciones [0,0 %], 4/24 unparseable [16,7 %], latencia p50 25,2 s y p95 32,0 s), las conclusiones de diseño sobre validación, reintentos/gramática de forma, caminos de degradación y la separación conceptual entre `unparseable` y `hallucinated`.

### `bench/decision_split/README.md`
- **`## Mediciones de referencia del runner` (`### Resultados reales del bench (medidos)`)**: Se agregó la subsección con la tabla comparativa de resultados reales (chico en tiempo real: p50 458 ms, p95 999,4 ms, cold 15,8 s, invalid_rate 0,0 %, `tick_compliance=false`, action_diversity 0,028; grande en replay: 0/24 alucinados [0,0 %], 4/24 unparseable [16,7 %], p50 25,2 s, p95 32,0 s) y la condición explícita de medición bajo GPU compartida (GPU use 93 %, otro `llama-server` en Vulkan0, VRAM 3,35/4,28 GB).
- **`### Conclusiones de ingeniería` (ítem 4)**: Se agregó el ítem sobre fallo por forma vs. contenido en el modelo grande (16,7 % unparseable vs 0 % alucinado), fundamentando la necesidad de reintento/gramática de forma y la separación contable de `unparseable` respecto de `hallucinated`.

## Pendientes o elementos no realizados
- Ninguno. Todas las modificaciones solicitadas fueron implementadas sin tocar archivos de código (`.py`), manteniendo el conjunto de pruebas intacto (14 passed).
