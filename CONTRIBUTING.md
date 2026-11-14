# Contribuir

¡Gracias por echar una mano! _English is welcome too: issues and PRs in either language are fine._

## Antes de empezar

- Mira el [ROADMAP](ROADMAP.md): las tareas sin marcar son las siguientes. Si quieres
  coger una, coméntalo en un issue para no duplicar trabajo.
- Para ideas nuevas o bugs, abre un issue con la plantilla correspondiente.

## Principios del proyecto

- **Gratis y local.** Whisper corre en el equipo del usuario y el razonamiento lo hace
  Claude en la sesión. No añadas APIs de pago ni claves.
- **Cuidado con la cuenta de Instagram.** Nada de peticiones rápidas ni reintentos en
  bucle: cualquier acceso nuevo debe ir espaciado y parar a la primera señal de bloqueo
  (mira `ig.py`). La exportación oficial siempre es la opción recomendada.
- **Sin dependencias en el núcleo.** `common.py`, `db.py`, `doctor.py` y
  `export_digest.py` solo usan la librería estándar. Las dependencias pesadas
  (yt-dlp, instaloader, faster-whisper) van en `requirements.txt` y se importan dentro
  de las funciones que las usan.
- **Python 3.9+ en Windows, macOS y Linux.** Usa `pathlib`, `encoding="utf-8"` al leer y
  escribir, y nada de rutas fijas.
- **Pasos pequeños.** Un PR = una mejora que se pueda revisar de una sentada.

## Preparar el entorno

```bash
git clone https://github.com/ArmasCitoZ/saved-reels-digest
cd saved-reels-digest
python -m pip install pytest ruff==0.16.9
python -m pytest -q      # tests
ruff check .             # linter (mismas reglas que CI)
```

Los tests no necesitan red ni Instagram: usan la exportación anonimizada de
`tests/fixtures/instagram_export/` y una base de datos temporal (`SRD_HOME` apunta a una
carpeta de `tmp_path`). Si añades un comando, añade su test en `tests/`.

## Si tocas los instaladores

`install.sh` (macOS y Linux) e `install.ps1` (Windows) hacen lo mismo y deben seguir
igualados. `install.sh` es sh POSIX (en Ubuntu lo ejecuta `dash`): nada de `[[`, `local`
ni `function`. `install.ps1` tiene que funcionar en Windows PowerShell 5.1, el que trae
Windows: solo ASCII y nada de `??`, `?.`, `&&`/`||` ni ternarios. Si cambia el rango de
versiones de Python, cámbialo también en `MIN_PYTHON`/`MAX_PYTHON` de `doctor.py`.
`tests/test_install_sh.py` y `tests/test_install_ps1.py` comprueban todo esto, y CI hace
una instalación completa con cada uno.

## Si cambias el flujo

`skills/digest/SKILL.md` es lo que lee Claude: si un script gana una opción o un comando
que Claude debería usar, explícalo ahí (en inglés, breve y en imperativo). Si el usuario
también lo puede usar a mano, añádelo a la lista de comandos del README.

## Pull requests

1. Rama desde `main`, commits con mensajes claros en inglés.
2. `python -m pytest -q` y `ruff check .` en verde (CI los corre en los tres sistemas).
3. Si cierras una tarea del roadmap, márcala en `ROADMAP.md` en el mismo PR.
4. Nunca subas datos reales: ni exportaciones de Instagram, ni `reels.json`, ni sesiones.

## Publicar una versión

1. Añade tus cambios a `## [Unreleased]` en `CHANGELOG.md` a medida que los hagas.
2. Para publicar, renombra esa sección a `## [X.Y.Z] - AAAA-MM-DD`, crea otra `Unreleased`
   vacía y sube `version` en `.claude-plugin/plugin.json`.
3. `git tag vX.Y.Z && git push origin vX.Y.Z`. El workflow `release.yml` pasa los tests,
   comprueba que la etiqueta coincide con `plugin.json` y crea la release en GitHub con el
   texto de esa sección del changelog.
