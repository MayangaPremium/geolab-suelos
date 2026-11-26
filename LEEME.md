# GeoLab – Guardar cada informe en la base de datos (suelos_db)

Con esto, **cada vez que exportes un informe a PDF** (en `Suelos_1.py` o en la página web) se guarda
automáticamente en la base de datos, con tu usuario y sin duplicados.
Si no hay conexión, el informe queda en cola y se envía solo después.

## Contenido

| Carpeta | Va dentro de | Qué hace |
|---|---|---|
| `1_PROYECTO_SUELOS/` | tu carpeta del proyecto (donde está `Suelos_1.py`) | Escritorio + web |
| `2_LARAVEL_Suelos-api/` | `C:\laragon\www\Suelos-api\` | API y base de datos |

## ANTES DE EMPEZAR (1 minuto)
En la terminal de Antigravity, dentro del proyecto, guarda una copia por si acaso:
```
git add -A
git commit -m "Antes de conectar la base de datos"
```
Si tenías código propio en `routes/api.php` o en los controladores de Laravel, haz copia de esos archivos.

---

## PASO 1 – Laravel (la API)

1. Copia el contenido de `2_LARAVEL_Suelos-api\` dentro de `C:\laragon\www\Suelos-api\`
   y acepta **reemplazar** (`routes\api.php`, `Informe.php`, los dos controladores).
   Se agrega también una migración nueva en `database\migrations\`.
2. Abre la **Terminal de Laragon** y escribe, uno por uno:
```
cd C:\laragon\www\Suelos-api
php artisan migrate
php artisan route:list --path=api
php artisan serve
```
   - `migrate`: agrega a la tabla `informes` las columnas que faltan. **No borra** tus datos.
   - `route:list`: debes ver `register`, `login`, `informes`, etc.
   - `serve`: deja esa ventana **abierta** mientras uses el sistema (la API corre en `http://127.0.0.1:8000`).

> Verifica en HeidiSQL (F5): la tabla `informes` ahora tiene `uid, proyecto, muestra, ensayo, tipo, origen, archivo_pdf, datos, resultados, clasificacion`.

### Recomendado: controlar quién se registra
En `.env` de Laravel agrega una línea con una clave del grupo:
```
REGISTRO_CODIGO=ClaveDelGrupo2026
```
y en `config\app.php`, dentro del arreglo `return [ ... ]`, agrega:
```
'registro_codigo' => env('REGISTRO_CODIGO'),
```
Sin esto, cualquiera que conozca la dirección del servidor podría crear una cuenta.
(La clave se la das solo a tus compañeros; se escribe en el campo "Código de registro".)

---

## PASO 2 – Proyecto (escritorio y web)

1. Copia el contenido de `1_PROYECTO_SUELOS\` a tu carpeta del proyecto, reemplazando:
   - `Suelos_1.py` (modificado), `index.html` (solo se agregó 1 línea), `requirements.txt`, `probar_api.py`
   - nuevos: `api_client.py`, `lector_formatos.py` y `js\servidor.js`; y `js\lector-datos.js` (reemplaza al anterior)
2. En la terminal de Antigravity (la de tu proyecto):
```
pip install requests
python probar_api.py
```
   Debe mostrar `Login: 200`, `Informe: 201` y la lista de informes.
   (Edita al inicio de `probar_api.py` tu correo y contraseña. La contraseña de prueba `123456` es débil: cámbiala.)

### Escritorio (`Suelos_1.py`)
1. Abre el programa. Arriba a la derecha, botón **☁ Servidor**.
2. Escribe tu correo y contraseña → **Iniciar sesión** (o **Registrarme** si es tu primera vez; contraseña de 8+ caracteres).
3. Calcula un ensayo → **Exportar a PDF**. Arriba aparece "Informe guardado en la base de datos".
4. El **informe consolidado** también se guarda.

### Web (`index.html`)
1. Ábrela con `Iniciar_GeoLab_Web.bat` (o doble clic en `index.html`).
2. Botón **☁ Servidor** (cabecera) → iniciar sesión. Cada PDF exportado se guarda igual.

> **Importante:** la web publicada en Vercel (https) no podrá guardar en un Laravel que corre en tu PC.
> Funciona abriendo la web desde tu PC. Para que tus compañeros guarden desde cualquier lugar, el servidor
> tendrá que publicarse en un hosting con https (el siguiente paso, cuando decidas la compra).

---

## Ver los informes guardados (HeidiSQL → pestaña Consulta)
```sql
SELECT id, proyecto, muestra, ensayo, tipo, origen, archivo_pdf, clasificacion, created_at
FROM informes ORDER BY id DESC;
```

## Qué se guarda de cada informe
- Proyecto, muestra, tipo de ensayo (humedad, volumetrico, gravedad, granulometria, atterberg, clasificacion, proctor o consolidado)
- Nombre del PDF, origen (escritorio o web), usuario, fecha y hora
- `datos`: todo lo ingresado y calculado (para poder reconstruir el informe)
- `resultados`: valores clave (w, Gs, LL/LP/IP, MDS/OCH, etc.) y `clasificacion` (SUCS | AASHTO)

## Si algo falla
| Mensaje | Causa probable |
|---|---|
| "No se pudo conectar con el servidor" | `php artisan serve` cerrado o MySQL apagado en Laragon |
| "Correo o contraseña incorrectos" | Revisa el correo; si no tienes cuenta, usa Registrarme |
| "Código de registro incorrecto" | Falta o está mal `REGISTRO_CODIGO` |
| "quedó en cola" | Sin conexión o sin sesión: inicia sesión en ☁ Servidor y pulsa **Enviar pendientes** |
| Error al hacer `migrate` | Copia el mensaje completo y envíamelo |

---

## PASO 3 – Lector de hojas escaneadas (foto o PDF → formulario)

Sube la hoja escaneada (aunque esté escrita a mano) y el programa rellena el formulario de **Granulometría**.
Tras leerla, **verifica las sumas de la propia hoja** (la suma de masas retenidas debe cuadrar con la masa lavada y seca)
y te avisa con un ⚠ si algún número pudo leerse mal. Con tu hoja de ejemplo (REPORTE-1) las tres comprobaciones cuadran exactamente.

### Qué necesitas (una sola vez)
1. Una **clave de API de Anthropic** (console.anthropic.com → API keys). Cada lectura tiene un costo pequeño; revisa los precios vigentes en la consola.
   Si ya la configuraste en Vercel (`ANTHROPIC_API_KEY`), puedes usar la misma.
2. En el `.env` de **Laravel** agrega (la clave queda SOLO en el servidor; ni el escritorio ni la web la ven):
```
ANTHROPIC_API_KEY=sk-ant-...tu-clave...
```
   (Opcional: `ANTHROPIC_MODEL=` para elegir otro modelo. Por defecto usa `claude-sonnet-5-5`.)
3. Copia los archivos de `2_LARAVEL_Suelos-api\` (nuevos: `LectorController.php` y `routes\api.php` actualizado) y reinicia `php artisan serve`.
4. En el proyecto: `pip install requests pillow` (pillow reduce las fotos grandes antes de enviarlas).

### Cómo se usa
- **Escritorio:** ensayo 04 Granulometría → tarjeta **"Leer datos desde foto o PDF"** → *Subir foto / PDF*.
- **Web:** ensayo de Granulometría → *Subir foto / PDF* (inicia sesión antes en **☁ Servidor** para que use tu servidor).
- Los campos leídos quedan con **borde naranja**. Si aparece un ⚠, compara ese dato con la hoja original.
- Marca/desmarca **"Calcular al terminar"** según prefieras.
- Formatos: PDF (hasta ~4.5 MB), JPG, PNG. Fotos de celular: de frente, bien iluminadas y sin cortar la tabla.

### Límites y cuidados
- Es lectura por IA de letra manuscrita: **puede equivocarse**. La verificación de sumas ayuda, pero un error pequeño (1–2 g en la parte gruesa)
  puede no detectarse: revisa siempre los valores contra la hoja antes de emitir un informe.
- Máximo 20 lecturas por hora por usuario.
- La hoja se envía al servicio de IA para leerla. Si trae nombres de técnicos u otros datos personales, tápalos antes de escanear (como en tu ejemplo).
- La función de Vercel `api/leer-datos.js` **no pide login**: cualquiera que conozca su dirección podría gastar tu clave. Cuando la web migre al hosting con Laravel, elimínala.

### Otros ensayos (humedad, peso volumétrico, gravedad específica, Atterberg, Proctor)
El lector está preparado para agregarlos, pero cada formato de hoja es distinto y hay que calibrarlo con una hoja real de cada uno.
Envíame un escaneo de ejemplo de cada ensayo y los incorporo. (La Clasificación SUCS/AASHTO no necesita hoja: se calcula sola con la granulometría y Atterberg.)
