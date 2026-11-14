# Roadmap

Small, shippable steps. Each one is a real improvement that gets tested before it is merged.
Tick the box when done and link the commit. Ideas welcome via issues.

## Calidad y confianza
- [x] Tests con pytest para `collect.py` (export JSON, HTML, zip, colecciones)
- [x] Tests para `db.py` (next / set / similar / dump)
- [x] GitHub Actions: lint (ruff) + tests en Linux, macOS y Windows
- [x] Fixture de exportación de Instagram anonimizada para los tests
- [x] Badge de CI y versión en el README

## Instalación
- [x] Comprobar dependencias al inicio (`doctor.py`): Python, espacio en disco, ffmpeg opcional
- [x] Guía paso a paso para Windows (`docs/windows.md`)
- [ ] Añadir capturas reales a la guía de Windows
- [x] Elegir modelo Whisper automáticamente según la RAM del equipo

## Funciones
- [x] `export_digest.py`: exportar `digest.md` a una bóveda de Obsidian (una nota por idea)
- [x] Exportar a Notion (vía el conector de Notion de Claude, sin API keys)
- [x] Soporte para posts carrusel: leer el texto de las imágenes (Claude las mira)
- [x] Soporte para vídeos guardados de TikTok (exportación oficial de TikTok)
- [x] Soporte para YouTube "Ver más tarde" / listas
- [x] Filtro por colección de Instagram (`--collection "IA"`)
- [x] Fecha de guardado en el digest y sección "guardado esta semana"
- [x] Marcar ideas como "probado / descartado" y que el digest lo recuerde
- [x] Exportadores: reconocer la lista principal y el estado aunque el digest esté en otro idioma
- [x] Reconocer las colecciones de Instagram aunque la exportación esté en otro idioma
- [x] Exportador: que una idea llamada "Index" no pise `INDEX.md`, y evitar nombres reservados de Windows
- [x] Exportador: aceptar slugs con acentos (`{#automatización}`)
- [x] Exportador: ignorar los `##` y `###` que haya dentro de bloques de código
- [x] `db.py similar`: que funcione con cualquier alfabeto (portugués, francés, cirílico...)
- [x] `db.py recent`: no listar los posts borrados sin texto
- [x] `db.py set`/`show` y `transcribe.py --shortcodes`: aceptar enlaces de YouTube pegados (`watch?v=`, `youtu.be`, Shorts)
- [x] `db.py check`: comparar `digest.md` con la base de datos (ideas sin reels, reels que apuntan a ideas que ya no están)
- [x] Usar `db.py check` en el paso 5 de la skill y documentarlo en el README

## Robustez
- [x] Reanudar transcripción tras cortes de red sin repetir trabajo
- [x] Detectar posts borrados o privados y listarlos aparte
- [x] Mejorar `similar` con n-gramas para detectar duplicados en distintos idiomas
- [x] Límite de tamaño en `dump` para no saturar el contexto de Claude con 500+ reels
- [x] `dump`: que la línea "Continue with" conserve los filtros (`--collection`, `--all`...)
- [x] `db.py set`: rechazar campos desconocidos y valores de triaje inválidos
- [x] Salida UTF-8 en Windows para que los emojis de los captions no rompan los scripts
- [x] Copia de seguridad diaria de `reels.json`
- [x] Mensaje claro si `reels.json` está dañado, en vez de un traceback
- [x] Que los posts borrados sin texto no queden pendientes para siempre
- [x] `fetch_meta.py`: parar si muchos posts seguidos parecen borrados (puede ser un bloqueo disfrazado)
- [x] `collect.py live`: guardar el progreso y explicar el error si Instagram corta la lectura
- [x] Mensaje claro si el zip de la exportación está dañado o a medio descargar
- [x] `save_db`: no dejar ficheros temporales si el disco se llena
- [x] `transcribe.py --shortcodes`: avisar de los códigos que no existen
- [x] `slides.py save`: no borrar las imágenes descargadas si el texto llega vacío
- [x] `fetch_meta.py`: guardar lo ya leído al pulsar Ctrl+C (ahora se pierden hasta 9 posts)
- [x] `db.py set` y `show`: aceptar enlaces pegados y terminar con error si ningún código existe
- [x] `slides.py save`: aceptar enlaces pegados, como `db.py set`/`show` y `transcribe.py`
- [x] `db.py mark`: no guardar marcas cuando ningún slug existe (casi siempre es una errata)

## Comunidad
- [x] CONTRIBUTING.md y plantillas de issues
- [x] CHANGELOG.md y releases versionadas por etiqueta (`release.yml`)
- [ ] Publicar la primera versión con novedades (v0.2.0)
- [x] Ejemplo de `digest.md` de muestra (con datos inventados) en `examples/`
- [x] GIF de demo en el README

## Fase 2: más allá de Python

Cada lenguaje entra donde aporta algo concreto; Python sigue siendo la base.

### Rust: motor de duplicados rápido
`db.py similar` compara cada reel con todos los demás (n²). Con 2.000+ reels eso tarda; en Rust es casi instantáneo.
- [x] Crate `reels-core` en `rust/` que calcula los grupos de duplicados (misma lógica TF-IDF que `db.py similar`), con tests en Rust
- [x] Binario `reels-similar` que lee `reels.json` y devuelve los grupos en JSON
- [x] `db.py similar` usa el binario de Rust si está instalado y si no, el Python actual; un test comprueba que ambos dan el mismo resultado
- [x] Benchmark Python vs Rust con 2.000 reels sintéticos en `docs/benchmarks.md`
- [x] CI: compilar y testear el crate en Linux, macOS y Windows, y adjuntar los binarios a cada release

### TypeScript: visor del digest
Leer un `digest.md` largo en un editor es incómodo; un visor local lo hace usable.
- [x] `viewer/`: página estática en TypeScript (sin servidor) que abre `reels.json` + `digest.md` y permite buscar y filtrar por categoría
- [x] Marcar ideas como probadas / descartadas desde el visor y exportar los cambios para `db.py`
- [x] Tests con Vitest y build del visor en CI
- [ ] Publicar el visor en GitHub Pages con los datos de `examples/` (el workflow `pages.yml` ya está; falta activar Pages → "GitHub Actions" en Settings y lanzarlo)

### PowerShell: instalación en Windows
- [x] `install.ps1`: instalación en un comando (comprueba Python, crea el entorno y explica cómo añadir el plugin)
