# SPEC — Streaming Agentes x Kateto Overlay & Game Harness Architecture

> Fecha: 2026-08-31 — Autor: Kateto (harness)
> Objetivo: 6 juegos + Sims3 con agentes LLM autónomos operando mediante eventos, GameJournals con MemPalace, y VisualOverlay (`ws://host/ws/overlay`) para OBS.

## 1. Visión y Arquitectura de Control
- **Flujo puro de eventos:** Juego -> `POST /api/game/event` -> Kateto Event Bus -> GameBridgePlugin / Executor -> Voces (Jane, Doktor, Conquest, etc.) -> Tool Call -> Juego.
- **Modo Juego (Game Profile):** 
  - Al iniciar un juego, se activa un perfil específico que inyecta un System Prompt acotado ("Estás jugando a [X], tenés herramientas de entorno").
  - **Herramientas Globales disponibles:** `mempalace_query`, `mempalace_append` (acceso a MemPalace) y `web_search` (consulta de wikis/guías). Los harnesses de los juegos ya incluyen estos fields en sus `POST /api/game/event` cuando sea necesario.
- **Coordinación (Single-player vs Multi-player):**
  - *Single-player:* El rol activo (Execution/Turn-ready) emite los tool calls de control del juego. Las demás voces (Planning, Critique) procesan pasivamente el estado y emiten comentarios u opiniones al overlay sin interferir en los comandos.
  - *Multiplayer / Werewolf:* Turnos regulados por cola de prioridad o moderador (Conquest como Juez).

## 2. Memoria Persistente (GameJournal via MemPalace)
- Cada partida/juego cuenta con su propio espacio de memoria de largo plazo en **MemPalace**.
- El agente decide autónomamente cuándo consultar (`mempalace_query`) o actualizar (`mempalace_append`) su journal para registrar objetivos cumplidos, errores, bloqueos y estrategias, permitiendo retomar partidas semanas después sin perder el hilo.

## 3. Manejo de Errores y Feedback Loop (Acciones Rechazadas)
- Si una acción del agente falla en el motor del juego (ej: cinemática bloqueante, movimiento inválido, turno incorrecto):
  - El conector del juego o harness inyecta un evento/error de tipo `game_action_rejected` con la causa.
  - El agente lo procesa en su siguiente iteración, consulta su journal/memoria y adapta su estrategia (ej: esperar, cambiar comando o saltar cinemática).

## 4. API del GameBridgePlugin (Contrato Bidireccional)
- **Entrada (Juego -> Kateto):** `POST /api/game/event` (envía `game`, `event_type`, `voice_id`, `state`, `text`, `rms`). Dispara el evento en el bus interno.
- **Salida (Kateto -> Juego):** El harness del juego intercepta el Tool Call resuelto por el agente (o hace polling a un endpoint de acciones pendientes) para ejecutarlo en el motor.

## 5. Bloqueos actuales y Tareas
- (Ver SPEC original para detalles de Sims3, Kateto 4B local, y arneses de los 6 juegos).
