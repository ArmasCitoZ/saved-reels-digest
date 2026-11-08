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
- [ ] Exportadores: reconocer la lista principal y el estado aunque el digest esté en otro idioma

## Robustez
- [x] Reanudar transcripción tras cortes de red sin repetir trabajo
- [x] Detectar posts borrados o privados y listarlos aparte
- [x] Mejorar `similar` con n-gramas para detectar duplicados en distintos idiomas
- [x] Límite de tamaño en `dump` para no saturar el contexto de Claude con 500+ reels
- [x] `dump`: que la línea "Continue with" conserve los filtros (`--collection`, `--all`...)
- [x] `db.py set`: rechazar campos desconocidos y valores de triaje inválidos
- [x] Salida UTF-8 en Windows para que los emojis de los captions no rompan los scripts
- [x] Copia de seguridad diaria de `reels.json`
- [ ] Mensaje claro si `reels.json` está dañado, en vez de un traceback
- [ ] Que los posts borrados sin texto no queden pendientes para siempre

## Comunidad
- [x] CONTRIBUTING.md y plantillas de issues
- [x] CHANGELOG.md y releases versionadas por etiqueta (`release.yml`)
- [ ] Publicar la primera versión con novedades (v0.2.0)
- [x] Ejemplo de `digest.md` de muestra (con datos inventados) en `examples/`
- [ ] GIF de demo en el README
