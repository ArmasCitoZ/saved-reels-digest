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
- [x] `setup_env.py`: no volver a llamar a pip si el entorno ya está completo (más rápido y funciona sin conexión al repetir la instalación)
- [x] `install.sh --upgrade` / `install.ps1 -Upgrade`: actualizar los paquetes del entorno (pasa `--upgrade` a `setup_env.py`)
- [x] `doctor.py`: avisar si yt-dlp tiene más de dos meses (Instagram y TikTok cambian a menudo y una versión vieja falla al descargar) y decir cómo actualizarlo
- [x] `install.sh`: instalación en un comando para macOS y Linux, como `install.ps1` en Windows
- [x] `setup_env.py --upgrade`: decir qué versión de yt-dlp había y cuál queda (para saber si la actualización sirvió de algo)

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
- [x] `db.py status`: cuántos reels hay de cada plataforma (Instagram, TikTok, YouTube)
- [x] `db.py status` y `unavailable`: aceptar `--collection`, como `next`, `dump`, `similar` y `recent`
- [x] `--collection` y `db.py collections`: explicar que también valen las listas de YouTube (hoy la ayuda solo habla de Instagram)
- [x] Exportadores: usar las marcas de `reels.json` (`db.py mark`) para el estado de cada idea, como ya hace el visor (hoy `export_digest.py` solo lee el texto del digest, así que una idea marcada como probada sale pendiente en Obsidian y Notion)
- [x] Obsidian: `status` (y la nota de `db.py mark`) en las propiedades de cada nota, e indicar en `INDEX.md` qué ideas están probadas o descartadas, para poder filtrarlas con Bases o Dataview
- [x] `export_digest.py --prune`: borrar las notas que creó el exportador y ya no están en el digest (sin tocar las que tienen algo escrito bajo `## My notes`); hoy solo se listan
- [x] `db.py check --strict`: terminar con código 1 cuando hay algo que arreglar, para poder usarlo en scripts y en CI
- [x] `db.py rename VIEJO NUEVO`: pasar todos los reels de una idea (y su marca de `db.py mark`) a otro slug al renombrarla o fusionarla con otra; hoy hay que repetir `db.py set entry` con cada código y la marca se pierde
- [x] `db.py rename --digest`: cambiar también el `{#viejo}` del título y los enlaces `(#viejo)` en `digest.md`, para que digest y base sigan de acuerdo en un solo paso
- [x] `db.py check`: cuando unos reels apuntan a una idea que ya no está, sugerir el `db.py rename` exacto (con el slug nuevo si solo hay una idea sin reels)
- [x] Skill: usar `db.py rename` al fusionar o renombrar ideas y al arreglar lo que diga `db.py check`
- [x] README: documentar `db.py rename`
- [x] `db.py marks --status tried|discarded`: listar solo las ideas probadas o solo las descartadas
- [x] `db.py set entry`: rechazar slugs inválidos (espacios, `#`, paréntesis...) con la misma regla que `db.py rename`; hoy `set entry "Claude Code"` se guarda y luego ni el `{#slug}` ni los enlaces del digest pueden apuntar a esa idea
- [x] `db.py ideas`: listar cada idea de la base con cuántos reels tiene, cuándo se guardó el último y su marca, para que Claude vea los slugs que ya existen antes de crear uno nuevo al fusionar
- [x] `db.py ideas --status todo|tried|discarded`: listar solo las ideas pendientes, probadas o descartadas
- [x] Skill y README: usar `db.py ideas` en el paso de fusión para reutilizar slugs en vez de inventar uno parecido
- [x] `db.py mark` y `rename`: cuando un slug no existe, sugerir el más parecido ("¿quisiste decir `subagents`?") en vez de solo listar los primeros 15
- [x] `--collection`: si el nombre no existe, sugerir la colección o lista más parecida (erratas como `--collection "Ideas IA"` por "Ideas de IA")
- [ ] `db.py check --fix`: aplicar solo el arreglo que no tiene dudas (un slug perdido y una sola idea sin reels → `db.py rename`), en vez de que Claude copie el comando a mano
- [ ] `db.py ideas --collection`: listar solo las ideas con reels de una colección o lista, como ya aceptan `status`, `next`, `dump`...
- [ ] `db.py ideas SLUG ...`: ver los reels de una idea (código, autor, enlace, fecha) para revisar de dónde sale antes de fusionarla o renombrarla
- [ ] Skill y README: documentar `check --fix`, `ideas --collection` e `ideas SLUG`

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
- [x] `collect.py urls`: aceptar también enlaces de TikTok y YouTube (hoy ignora todo lo que no sea de Instagram sin avisar)
- [x] `transcribe.py` y `fetch_meta.py`: cuando paran por fallos seguidos con errores típicos de un yt-dlp viejo ("Unable to extract", "Unsupported URL"...), sugerir `setup_env.py --upgrade` en vez de dejar solo el error

## Comunidad
- [x] CONTRIBUTING.md y plantillas de issues
- [x] CHANGELOG.md y releases versionadas por etiqueta (`release.yml`)
- [ ] Publicar la primera versión con novedades (v0.2.0). Aún no hay ninguna etiqueta en el repositorio: o se etiqueta v0.2.0 en el commit de esa fecha, o se saca v0.3.0 con todo lo de "Unreleased" del CHANGELOG (subir `version` en `.claude-plugin/plugin.json` y `git tag v0.3.0 && git push --tags`; `release.yml` hace el resto)
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
- [x] Visor: filtrar también por plataforma (Instagram, TikTok, YouTube), como ya hace `db.py status`
- [x] Visor: guardar la búsqueda y los filtros en la URL (`#q=...&plataforma=tiktok`) para que recargar no los pierda y se pueda guardar un enlace a una vista
- [x] Visor: ordenar las ideas (orden del digest, guardadas hace menos, con más reels) y guardar el orden en la URL como los filtros
- [ ] Publicar el visor en GitHub Pages con los datos de `examples/` (el workflow `pages.yml` ya está; falta activar Pages → "GitHub Actions" en Settings y lanzarlo)

### PowerShell: instalación en Windows
- [x] `install.ps1`: instalación en un comando (comprueba Python, crea el entorno y explica cómo añadir el plugin)
