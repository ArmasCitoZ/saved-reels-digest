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
- [ ] Guía paso a paso para Windows con capturas
- [x] Elegir modelo Whisper automáticamente según la RAM del equipo

## Funciones
- [x] `export_digest.py`: exportar `digest.md` a una bóveda de Obsidian (una nota por idea)
- [ ] Exportar a Notion (vía el conector de Notion de Claude, sin API keys)
- [ ] Soporte para posts carrusel: leer el texto de las imágenes (Claude las mira)
- [ ] Soporte para vídeos guardados de TikTok (exportación oficial de TikTok)
- [ ] Soporte para YouTube "Ver más tarde" / listas
- [x] Filtro por colección de Instagram (`--collection "IA"`)
- [x] Fecha de guardado en el digest y sección "guardado esta semana"
- [x] Marcar ideas como "probado / descartado" y que el digest lo recuerde

## Robustez
- [ ] Reanudar transcripción tras cortes de red sin repetir trabajo
- [x] Detectar posts borrados o privados y listarlos aparte
- [ ] Mejorar `similar` con n-gramas para detectar duplicados en distintos idiomas
- [x] Límite de tamaño en `dump` para no saturar el contexto de Claude con 500+ reels

## Comunidad
- [ ] CONTRIBUTING.md y plantillas de issues
- [ ] CHANGELOG.md y releases versionadas
- [ ] Ejemplo de `digest.md` de muestra (con datos inventados) en `examples/`
- [ ] GIF de demo en el README
