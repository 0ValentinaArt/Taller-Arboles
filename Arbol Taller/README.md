# HackTree

Simulador interactivo de árbol de ataque para modelar amenazas de ciberseguridad.
Backend en Python (FastAPI) y frontend en HTML, CSS y JavaScript con D3.js.

## Ejecutar

```bash
pip install -r requirements.txt
python main.py
```

Abre http://127.0.0.1:8000 en el navegador.

## Pruebas

```bash
pip install pytest
pytest
```

## Estructura

- `tree.py`: clases `Node`, `AttackTree`, `Mitigation`, recorridos DFS/BFS y cálculo de riesgo.
- `main.py`: API REST (`/api/tree`, `/api/stats`, `/api/search`, `/api/traversal`, ...).
- `static/`: interfaz web.

El escenario es ficticio y conceptual; no incluye ataques reales.
