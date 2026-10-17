# PyFlowMap · sitio web estático

Sitio **estático y offline** con HTML, CSS y SVG reales producidos desde
`examples/uml_showcase`. No contiene librerías externas, telemetría, CDNs
ni peticiones a servicios de IA.

## Vista previa local

Abre `site/index.html` en el navegador, o desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m http.server 8000 --directory site
```

A continuación visita `http://localhost:8000/`.

## Estado de publicación

**Sin desplegar.** El sitio se mantiene en `site/`, pero Pages no puede
elegir directamente `site/` como origen de una rama: solo admite `/` o
`/docs`. El workflow `.github/workflows/deploy-pages.yml` carga exclusivamente
el contenido de `site/` y **solo se ejecuta manualmente** desde `main`.
Antes de ejecutarlo se debe elegir Settings → Pages → Source: GitHub Actions.
No se publica nada en cada push o PR.

## Procedencia y alcance

Los tres SVG se generaron a partir de `examples/uml_showcase` con
`semantic_provider=disabled`:

- `activity.svg`: diagrama de actividad, sin inferencia.
- `classes.svg`: clases y relaciones UML respaldadas por AST.
- `packages.svg`: dependencias de paquetes con estilo `modern`.

El estilo de paquetes `strict` sigue disponible en la CLI; el estilo
`modern` representa cada paquete como una carpeta vectorial horizontal
completa, con el nombre en su interior, sin tarjeta externa ni icono pequeño.
La forma `modern` es una presentación alternativa, no la notación normativa
UML de pestaña. Los SVG deben regenerarse cuando cambien los ejemplos.

Antes de
desplegar, revisar los tres SVG reales generados por PyFlowMap y no inventar
relaciones gráficas. Consulta la [lista de publicación](../docs/publication.md).
