# PyFlowMap · borrador del sitio GitHub Pages

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

**Sin desplegar.** Esta carpeta `site/` no se publica automáticamente con
GitHub Pages en modo branch source; publicar requerirá una configuración o
workflow de despliegue revisado y activado expresamente después de aprobar
el diseño, fusionar las ramas previstas y validar el commit definitivo.
No se incluye por ahora ninguna acción de publicación automática.

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

Los enlaces del pie apuntan al repositorio y al texto de la licencia MIT,
no a rutas de ramas que podrían desaparecer o a archivos que aún no existen
en `main`. Los comandos UML solo estarán en `main` tras integrar sus PR.
No desplegar Pages antes de esa fase.
