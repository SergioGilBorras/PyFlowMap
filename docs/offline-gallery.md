# Galería offline: actividad, clases y paquetes

El comando genera tres diagramas desde un proyecto Python, **sin Codex,
LLM ni proveedor mock**, en carpetas separadas. Se requiere Graphviz
(\`dot\`) para SVG/PNG. El código analizado no se importa ni ejecuta.

\`\`\`powershell
.\.venv\Scripts\python.exe scripts\offline_diagram_gallery.py
.\.venv\Scripts\python.exe scripts\offline_diagram_gallery.py --source .\mi-proyecto --entry modulo:main
\`\`\`

Cada ejecución crea una carpeta nueva bajo \`output_graphs/\`:

\`\`\`text
<fecha>-<identificador>/
  index.html                 # índice local y profesional
  README.md
  activity/                  # actividad: .mmd, .json, .svg, .png
  classes/                   # clases UML: .mmd, .json, .svg, .png
  packages/                  # paquetes UML: .dot, .json, .svg, .png
  common/
    manifest.json            # ficheros, avisos y procedencia
    gallery.css              # presentación común
\`\`\`

Los diagramas son diferentes, con modelos y archivos fuente propios. No se
inventan relaciones UML; la información estática no demostrable se omite.
Las relaciones de paquetes son dependencias, **no** \`«import»\` UML.
El diagrama de actividad conserva su representación existente.
No se modifican rutas históricas, datos previos ni el CLI actual.

Abre el \`index.html\` generado tras descomprimir la salida para revisar
las tres imágenes y acceder a fuentes editables. El índice no necesita
JavaScript, CDNs ni conexión a Internet.
