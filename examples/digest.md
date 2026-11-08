# IA y Claude: resumen de mis reels guardados
_Actualizado 2026-11-01 · 214 guardados · 38 del tema · 6 ideas únicas tras fusionar_

> Ejemplo con datos inventados: las cuentas y los enlaces no existen. Así es el `digest.md` que te deja el plugin.

## Haz esto primero
1. **Escribe un CLAUDE.md corto en cada proyecto**: diez minutos y deja de repetirle lo mismo en cada sesión → [entrada](#claude-md-corto)
2. **Pide un plan antes de que toque el código**: evita los cambios grandes que luego hay que deshacer → [entrada](#plan-antes-de-codigo)
3. **Dale ejemplos en vez de adjetivos**: el cambio de prompt que más se nota con menos esfuerzo → [entrada](#ejemplos-no-adjetivos)
4. **Transcribe tus reuniones en local**: gratis y sin subir audio a ningún sitio → [entrada](#transcribir-en-local)

## Guardado esta semana
- **Pide un plan antes de que toque el código** → [entrada](#plan-antes-de-codigo) · 1 reel más
- **Transcribe tus reuniones en local** → [entrada](#transcribir-en-local) · nueva

## Claude Code
### Un CLAUDE.md corto en cada proyecto {#claude-md-corto}
Un archivo breve en la raíz con cómo se prueba el proyecto, qué convenciones sigue y qué no debe tocar ahorra repetirlo en cada sesión. Los tres creadores coinciden en que más corto funciona mejor: lo que no cambia el comportamiento sobra.
**Cómo aplicarlo:** ejecuta `/init`, recorta el resultado a unas 30 líneas y añade una línea cada vez que tengas que corregir lo mismo dos veces.
**Visto en 3 reels** (guardados 2026-09-12 → 2026-10-28): [@demo_devcorner](https://www.instagram.com/reel/DEMOclaude01/) · [@demo_ana.codes](https://www.instagram.com/reel/DEMOclaude02/) · [@demo_shipfast](https://www.tiktok.com/@demo_shipfast/video/7400000000000000011)

### Pedir un plan antes de tocar el código {#plan-antes-de-codigo}
Antes de una tarea grande, pide primero un plan y corrígelo. Equivocarse en el plan cuesta una frase; equivocarse en el código cuesta deshacer veinte archivos.
**Cómo aplicarlo:** usa el modo plan, revisa qué archivos va a tocar y aprueba solo cuando el enfoque te convenza.
**Visto en 2 reels** (guardados 2026-10-03 → 2026-10-30): [@demo_devcorner](https://www.instagram.com/reel/DEMOclaude03/) · [@demo_laura.ai](https://www.instagram.com/reel/DEMOclaude04/)
**Notas:** para cambios de una línea no compensa.

### Subagentes para revisar tu propio código {#subagentes-revision}
**Status:** ✅ Tried: útil en refactors grandes, excesivo para lo demás
Lanzar un subagente que revise el cambio sin haber visto cómo se hizo encuentra errores que quien lo escribió ya no ve.
**Cómo aplicarlo:** al terminar, pide una revisión con un subagente y pásale solo el diff y el objetivo.
**Visto en 1 reel** (guardado 2026-08-21): [@demo_ana.codes](https://www.instagram.com/reel/DEMOclaude05/)

## Prompting
### Ejemplos en vez de adjetivos {#ejemplos-no-adjetivos}
"Hazlo profesional" no dice nada; dos ejemplos de lo que te gusta y uno de lo que no lo dicen todo. Es la idea que más se repite entre los guardados, aunque con distintos nombres.
**Cómo aplicarlo:** añade al prompt dos o tres ejemplos reales del resultado que quieres, y uno de lo que quieres evitar.
**Visto en 2 reels** (guardados 2026-09-30 → 2026-10-11): [@demo_promptlab](https://www.instagram.com/reel/DEMOprompt01/) · [@demo_laura.ai](https://www.tiktok.com/@demo_laura.ai/video/7400000000000000012)

### El prompt secreto de 40 líneas {#prompt-secreto}
**Status:** 🚫 Discarded: no noté diferencia con un prompt normal
Promete resultados mejores pegando una plantilla enorme al principio de cada conversación.
**Cómo aplicarlo:** no compensa; quédate con instrucciones cortas y específicas de tu tarea.
**Visto en 1 reel** (guardado 2026-07-14): [@demo_growthguru](https://www.instagram.com/reel/DEMOprompt02/)
**Notas:** suena a hype: no enseña ninguna comparación y remite a un enlace de pago.

## Herramientas de IA
### Transcribir reuniones en local con Whisper {#transcribir-en-local}
Whisper funciona en un portátil normal sin GPU y sin subir el audio a ningún servicio. El modelo `small` va bien en español e inglés.
**Cómo aplicarlo:** instala `faster-whisper`, empieza con el modelo `small` y pasa a uno mayor solo si fallan los nombres propios.
**Visto en 1 reel** (guardado 2026-10-29): [@demo_shipfast](https://www.instagram.com/reel/DEMOtools01/)
