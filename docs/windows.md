# Guía paso a paso para Windows

Para Windows 10 y 11. No necesitas saber programar: el trabajo lo hace Claude y tú solo
tienes que dejar instaladas dos cosas. _(Las capturas de pantalla están pendientes: mira el
[ROADMAP](../ROADMAP.md).)_

## 1. Instala Python

1. Entra en [python.org/downloads](https://www.python.org/downloads/) y descarga la última
   versión para Windows.
2. Abre el instalador y, **antes de pulsar "Install Now"**, marca la casilla
   **"Add python.exe to PATH"**. Es el paso que más se olvida.
3. Comprueba que ha ido bien. Abre **PowerShell** (menú Inicio → escribe `PowerShell`) y
   ejecuta:

   ```powershell
   py --version
   ```

   Debe responder `Python 3.9` o superior.

> Si al escribir `python` se te abre la Microsoft Store, es un acceso directo de Windows, no
> Python. Usa `py`, o desactívalo en Configuración → Aplicaciones → Configuración avanzada de
> aplicaciones → Alias de ejecución de aplicaciones.

## 2. Instala Claude Code

Sigue las [instrucciones oficiales para Windows](https://code.claude.com/docs/en/setup) y
entra con tu cuenta. Cuando termines, cierra y vuelve a abrir PowerShell.

## 3. Instala el plugin

Escribe `claude` en PowerShell para abrir Claude Code y, dentro, ejecuta:

```
/plugin marketplace add ArmasCitoZ/saved-reels-digest
/plugin install saved-reels@saved-reels-digest
```

Cierra Claude Code y vuelve a abrirlo.

## 4. Pide tu exportación de Instagram

En Windows es la mejor opción, porque Chrome y Edge cifran sus cookies y a menudo no se
pueden reutilizar (más abajo tienes la alternativa).

1. En la app de Instagram: Configuración → Centro de cuentas → Tu información y permisos →
   Descargar tu información → Descargar o transferir información.
2. Elige *Parte de tu información* → **Guardado**.
3. Elige **Descargar en el dispositivo**, formato **JSON** e intervalo **Desde el principio**.
4. Instagram te avisará por correo cuando esté (de minutos a unas horas). Descarga el zip,
   por ejemplo en `Descargas`. **No hace falta descomprimirlo.**

## 5. Lanza el resumen

Dentro de Claude Code:

```
/saved-reels:digest
```

Cuando te pregunte cómo conectar Instagram, di que tienes la exportación y dale la ruta del
zip. El truco más rápido: en el Explorador, mantén pulsado **Mayús**, haz clic derecho en el
zip y elige **Copiar como ruta**.

La primera vez Claude crea su propio entorno de Python (lo ves como `setup_env.py`) y
descarga el modelo Whisper: cuenta con aproximadamente 1 GB y unos minutos.

## Si algo falla

| Lo que ves | Qué hacer |
|---|---|
| `'py' no se reconoce como...` | Python no quedó en el PATH: vuelve a abrir el instalador, elige *Modify* → siguiente → marca *Add Python to environment variables*, y reabre PowerShell. |
| Claude no encuentra `python3` | Es normal en Windows: dile que use `py`. |
| `doctor.py` muestra una línea `FAIL` | Explica el problema concreto (versión, disco o carpeta). Arréglalo y vuelve a lanzar `/saved-reels:digest`. |
| Error con las cookies del navegador | Cierra Chrome **del todo** (también en la bandeja junto al reloj) y reintenta, prueba con `--browser firefox` o usa la exportación oficial. |
| El antivirus bloquea `python.exe` o `yt-dlp` | Permite la carpeta `C:\Users\TU_USUARIO\saved-reels-digest` y repite el comando. |
| El disco C: está justo de espacio | Define otra carpeta antes de abrir Claude Code: `setx SRD_HOME "D:\saved-reels-digest"`, y reabre PowerShell. |
| Letras raras en la terminal (`Ã³`) | Solo afecta a cómo se ve en PowerShell; `digest.md` se guarda bien en UTF-8. |

## Dónde quedan tus archivos

En `C:\Users\TU_USUARIO\saved-reels-digest\`. Tu resumen es `digest.md` y puedes abrirlo con
cualquier editor de texto. La carpeta `.session` contiene tu sesión de Instagram si usaste
el navegador: trátala como una contraseña. Para borrarlo todo, elimina la carpeta entera.

Para usar los scripts a mano, el Python del entorno está en
`%USERPROFILE%\saved-reels-digest\.venv\Scripts\python.exe`.
