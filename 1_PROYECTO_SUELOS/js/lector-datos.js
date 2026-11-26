// Lector de foto/PDF para Granulometría: envía el archivo al servidor y rellena el formulario.
//  - Con sesión iniciada (☁ Servidor): usa el servidor Laravel (/leer-formato). Funciona también abriendo la web desde tu PC.
//  - Sin sesión: usa el lector de Vercel (/api/leer-datos), que solo existe cuando la web está publicada en Vercel.
// Además verifica las sumas de la propia hoja para avisar si algún número manuscrito pudo leerse mal.
(function () {
  const $ = id => document.getElementById(id);
  const COLOR_LEIDO = "#f0a500";

  const estado = (msg, error) => {
    const el = $("granu-lector-estado");
    if (!el) return;
    el.textContent = msg;
    el.style.whiteSpace = "pre-line";
    el.style.color = error ? "#c0392b" : "";
  };

  function setVal(id, v) {
    const el = $(id);
    if (!el || v === null || v === undefined || v === "") return false;
    el.value = v;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.style.outline = "2px solid " + COLOR_LEIDO; // marca lo leído automáticamente
    return true;
  }

  function setRadio(name, value) {
    const r = document.querySelector(`input[name="${name}"][value="${value}"]`);
    if (!r) return;
    r.checked = true;
    r.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function aBase64(blob) {
    return new Promise((ok, fail) => {
      const fr = new FileReader();
      fr.onload = () => ok(String(fr.result).split(",")[1]);
      fr.onerror = fail;
      fr.readAsDataURL(blob);
    });
  }

  // Reduce la foto (máx. 2000 px) para que viaje rápido
  async function prepararImagen(file) {
    const url = URL.createObjectURL(file);
    const img = await new Promise((ok, fail) => { const i = new Image(); i.onload = () => ok(i); i.onerror = fail; i.src = url; });
    const esc = Math.min(1, 2000 / Math.max(img.width, img.height));
    const c = document.createElement("canvas");
    c.width = Math.round(img.width * esc);
    c.height = Math.round(img.height * esc);
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    URL.revokeObjectURL(url);
    const blob = await new Promise(r => c.toBlob(r, "image/jpeg", 0.85));
    return { data: await aBase64(blob), mediaType: "image/jpeg" };
  }

  // ---------- adónde se envía ----------
  function destino() {
    let token = "", base = "";
    try { token = localStorage.getItem("geolab_api_token") || ""; base = localStorage.getItem("geolab_api_url") || ""; } catch (e) { /* sin almacenamiento */ }
    if (token && base) {
      return {
        laravel: true,
        url: base.replace(/\/+$/, "") + "/leer-formato",
        headers: { "content-type": "application/json", "Accept": "application/json", "Authorization": "Bearer " + token },
        limitePdf: 4.5 * 1024 * 1024
      };
    }
    return { laravel: false, url: "/api/leer-datos", headers: { "content-type": "application/json" }, limitePdf: 3.2 * 1024 * 1024 };
  }

  // ---------- verificación de las sumas de la hoja ----------
  function num(v) {
    if (v === null || v === undefined || v === "") return null;
    const n = parseFloat(String(v).replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }
  function suma(tamices, col) {
    const vals = Object.values(tamices || {}).map(t => (t && typeof t === "object" ? num(t[col]) : null)).filter(v => v !== null);
    return vals.length ? { s: vals.reduce((a, b) => a + b, 0), n: vals.length } : { s: null, n: 0 };
  }
  const f1 = x => x.toFixed(1);

  // Devuelve [{nivel: "ok"|"aviso", texto}]. Un aviso no bloquea nada: indica qué comparar con la hoja original.
  function validar(d) {
    const out = [];
    const tam = d.tamices || {}, sec = d.secado || {}, enc = d.encabezado || {};
    const a = suma(tam, "m1"), b = suma(tam, "m2");
    if (a.n + b.n === 0) return [{ nivel: "aviso", texto: "No se leyó ningún valor de masa retenida. Revise que la foto sea nítida y esté completa." }];

    if (d.metodo === "a-compuesto") {
      const [g1, g2, g3] = ["g1", "g2", "g3"].map(k => num(sec[k]));
      const [h1, h2, h3] = ["f1", "f2", "f3"].map(k => num(sec[k]));
      [["gruesa", g1, g2, "g1 (húmeda) < g2 (seca)"], ["gruesa", g2, g3, "g2 (seca) < g3 (lavada)"],
       ["fina", h1, h2, "f1 (húmeda) < f2 (seca)"], ["fina", h2, h3, "f2 (seca) < f3 (lavada)"]].forEach(([p, x, y, t]) => {
        if (x !== null && y !== null && x < y) out.push({ nivel: "aviso", texto: `Parte ${p}: ${t}. La masa debería disminuir al secar y lavar; revise esos números.` });
      });
      if (a.s !== null && g3 !== null) {
        const tol = Math.max(1.5, 0.0002 * g3), dif = Math.abs(a.s - g3);
        out.push(dif <= tol
          ? { nivel: "ok", texto: `Parte gruesa: la suma de retenidos (${f1(a.s)} g) coincide con la masa lavada y seca (${f1(g3)} g).` }
          : { nivel: "aviso", texto: `Parte gruesa: la suma de retenidos (${f1(a.s)} g) NO coincide con la masa lavada y seca (${f1(g3)} g); diferencia ${f1(dif)} g. Revise la columna M-1 (o g3).` });
      }
      if (b.s !== null && h3 !== null) {
        const tol = Math.max(0.3, 0.0005 * h3), dif = Math.abs(b.s - h3);
        out.push(dif <= tol
          ? { nivel: "ok", texto: `Parte fina: la suma de retenidos (${f1(b.s)} g) coincide con la masa lavada y seca (${f1(h3)} g).` }
          : { nivel: "aviso", texto: `Parte fina: la suma de retenidos (${f1(b.s)} g) NO coincide con la masa lavada y seca (${f1(h3)} g); diferencia ${f1(dif)} g. Revise la columna M-2 (o f3).` });
      }
      const mt = num(enc["masa-total"]), mg = num(enc["masa-gruesa"]), mf = num(enc["masa-fina"]);
      if (mt !== null && mg !== null && mf !== null) {
        out.push(Math.abs(mt - (mg + mf)) <= Math.max(1.5, 0.0005 * mt)
          ? { nivel: "ok", texto: `Masa total (${f1(mt)} g) = parte gruesa + parte fina.` }
          : { nivel: "aviso", texto: `La masa total (${f1(mt)} g) no es igual a parte gruesa + parte fina (${f1(mg + mf)} g). Revise el encabezado.` });
      }
      if (mg !== null && g1 !== null && Math.abs(mg - g1) > 1.0) {
        out.push({ nivel: "aviso", texto: `La masa de la parte gruesa del encabezado (${f1(mg)} g) difiere de g1 (${f1(g1)} g).` });
      }
    } else {
      const w0 = num(d.masa_lavada), w1 = num(d.masa_total);
      if (w1 !== null && w0 !== null && w0 > w1) out.push({ nivel: "aviso", texto: "La masa lavada es mayor que la masa seca total; revise esos dos valores." });
      if (a.s !== null && w0 !== null) {
        const tol = Math.max(2.0, 0.002 * w0), dif = Math.abs(a.s - w0);
        out.push(dif <= tol
          ? { nivel: "ok", texto: `La suma de retenidos (${f1(a.s)} g) coincide con la masa seca lavada (${f1(w0)} g).` }
          : { nivel: "aviso", texto: `La suma de retenidos (${f1(a.s)} g) difiere de la masa seca lavada (${f1(w0)} g) en ${f1(dif)} g. Puede deberse a finos perdidos por lavado o a un número mal leído; compárelo con la hoja.` });
      }
    }
    return out;
  }

  // ---------- rellenar el formulario ----------
  function limpiarCampos() {
    const sel = '[id^="granu-ret-"],[id^="granu-ret2-"],[id^="sec-"][id$="-masa"],[id^="granu-hdr-"],#granu-masa-total,#granu-masa-lavada';
    document.querySelectorAll(sel).forEach(el => {
      if (el.tagName === "INPUT") { el.value = ""; el.style.outline = ""; }
    });
  }

  function hayDatos() {
    return Array.from(document.querySelectorAll('[id^="granu-ret-"],[id^="granu-ret2-"]')).some(el => el.value && el.value.trim() !== "");
  }

  function aplicar(d) {
    limpiarCampos();                     // no mezclar con datos anteriores o de ejemplo
    let n = 0;
    const cuenta = ok => { if (ok) n++; };
    if (d.metodo) setRadio("granu-metodo", d.metodo);
    if (d.metodo === "a-compuesto" && d.columnas) setRadio("granu-comp-cols", d.columnas);
    const e = d.encabezado || {};
    ["informe", "calicata", "muestra", "profundidad", "fecha", "tecnico", "horno", "balanza", "masa-total", "masa-gruesa", "masa-fina", "recipiente"]
      .forEach(k => cuenta(setVal("granu-hdr-" + k, e[k])));
    const s = d.secado || {};
    ["g1", "g2", "g3", "f1", "f2", "f3"].forEach(k => cuenta(setVal(`sec-${k}-masa`, s[k])));
    cuenta(setVal("granu-masa-total", d.masa_total));
    cuenta(setVal("granu-masa-lavada", d.masa_lavada));
    const t = d.tamices || {};
    Object.keys(t).forEach(id => {
      cuenta(setVal("granu-ret-" + id, t[id] && t[id].m1));
      cuenta(setVal("granu-ret2-" + id, t[id] && t[id].m2));
    });
    return n;
  }

  async function procesar(file) {
    try {
      const dest = destino();
      if (hayDatos() && !window.confirm("El formulario ya tiene valores de tamices.\nSe reemplazarán con los de la hoja. ¿Continuar?")) return;
      estado("Leyendo el archivo… (puede tardar unos segundos)");
      let payload;
      if (file.type === "application/pdf") {
        if (file.size > dest.limitePdf) throw new Error(`El PDF pesa demasiado (máx. ~${Math.round(dest.limitePdf / 1048576 * 10) / 10} MB). Escanee en menor resolución o suba una foto.`);
        payload = { data: await aBase64(file), mediaType: "application/pdf" };
      } else {
        payload = await prepararImagen(file);
      }
      if (dest.laravel) payload.ensayo = "granulometria";

      let r;
      try {
        r = await fetch(dest.url, { method: "POST", headers: dest.headers, body: JSON.stringify(payload) });
      } catch (netErr) {
        throw new Error(dest.laravel
          ? "No se pudo conectar con el servidor. ¿Está encendido Laragon y 'php artisan serve'?"
          : "No hay lector disponible: inicie sesión en ☁ Servidor (la web de Vercel usa su propio lector).");
      }
      let d = null;
      try { d = await r.json(); } catch (e) { /* respuesta no JSON */ }
      if (!r.ok) {
        if (r.status === 401 && dest.laravel) { try { localStorage.setItem("geolab_api_token", ""); } catch (e) { /* nada */ } throw new Error("La sesión expiró. Inicie sesión de nuevo en ☁ Servidor."); }
        if (r.status === 429) throw new Error("Se alcanzó el límite de lecturas por hora. Espere un momento e intente de nuevo.");
        throw new Error((d && (d.message || d.error)) || "No se pudo leer el archivo.");
      }
      const n = aplicar(d);
      if (!n) throw new Error("No se encontraron datos legibles en el archivo. Pruebe con una foto más nítida y completa.");

      const avisos = validar(d).filter(x => x.nivel === "aviso");
      let msg = `Se rellenaron ${n} campos (resaltados en naranja). `;
      msg += avisos.length ? "Revise estos avisos con la hoja original:\n" + avisos.map(x => "⚠ " + x.texto).join("\n")
                           : "✔ Las sumas de la hoja cuadran. Revise igualmente los valores antes de confiar en los resultados.";
      estado(msg, avisos.length > 0);
      if ($("granu-lector-autocalc").checked && typeof calcularGranulometria === "function") calcularGranulometria();
    } catch (err) {
      estado(err.message || String(err), true);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const btn = $("btn-granu-lector"), inp = $("granu-lector-file");
    if (!btn || !inp) return;
    btn.addEventListener("click", () => inp.click());
    inp.addEventListener("change", () => {
      if (inp.files[0]) procesar(inp.files[0]);
      inp.value = "";
    });
  });

  window.GeoLector = { _interno: { validar, aplicar } };
})();
