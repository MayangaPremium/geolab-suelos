/* ===================================================================
   GeoLab Web - Conexión con la base de datos (API Laravel + MySQL)

   - Agrega el botón "☁ Servidor" (inicio de sesión / registro).
   - Cada vez que se exporta un informe a PDF, también se guarda en la base de datos.
   - Si no hay sesión o conexión, el informe queda en una cola del navegador
     y se reenvía solo cuando haya conexión.
   - Solo se guarda el token de sesión (NUNCA la contraseña).
   =================================================================== */
(function () {
  "use strict";

  var LS = { url: "geolab_api_url", token: "geolab_api_token", email: "geolab_api_email", cola: "geolab_api_cola" };
  var URL_DEFECTO = "http://127.0.0.1:8000/api";
  var MAX_COLA = 100;
  var TIMEOUT_MS = 15000;

  // ---------- almacenamiento local (tolerante a navegadores que lo bloquean) ----------
  function lsGet(k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* sin almacenamiento */ } }

  function normalizarUrl(u) {
    u = (u || "").trim().replace(/\/+$/, "");
    if (!u) return URL_DEFECTO;
    if (!/^https?:\/\//i.test(u)) u = "http://" + u;
    if (!/\/api$/i.test(u)) u += "/api";
    return u;
  }
  function getUrl() { return normalizarUrl(lsGet(LS.url, URL_DEFECTO)); }
  function getToken() { return lsGet(LS.token, ""); }
  function getCola() { try { return JSON.parse(lsGet(LS.cola, "[]")) || []; } catch (e) { return []; } }
  function setCola(c) { lsSet(LS.cola, JSON.stringify(c.slice(-MAX_COLA))); }

  function uid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID().replace(/-/g, "");
    return (Date.now().toString(16) + Math.random().toString(16).slice(2) + Math.random().toString(16).slice(2)).slice(0, 32);
  }

  function avisar(msg) {
    if (typeof window.showToast === "function") window.showToast(msg);
    else console.log("[GeoLab]", msg);
  }

  // ---------- red ----------
  function llamar(metodo, ruta, cuerpo, token, urlBase) {
    var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var t = ctrl ? setTimeout(function () { ctrl.abort(); }, TIMEOUT_MS) : null;
    var headers = { "Accept": "application/json", "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;
    return fetch((urlBase || getUrl()) + ruta, {
      method: metodo, headers: headers, body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      signal: ctrl ? ctrl.signal : undefined
    }).then(function (r) {
      if (t) clearTimeout(t);
      return r.text().then(function (txt) {
        var data = null; try { data = txt ? JSON.parse(txt) : null; } catch (e) { /* respuesta no JSON */ }
        return { status: r.status, data: data };
      });
    }, function (e) { if (t) clearTimeout(t); throw e; });
  }

  function mensajeError(r) {
    var d = r.data;
    if (d && d.errors) { var k = Object.keys(d.errors)[0]; var v = d.errors[k]; return Array.isArray(v) ? v[0] : String(v); }
    if (d && d.message) return String(d.message);
    return "Error " + r.status + " del servidor.";
  }

  var ERR_RED = "No se pudo conectar con el servidor. ¿Está encendido Laragon y 'php artisan serve'? " +
                "(Si esta página está en https, el servidor también debe usar https.)";

  // ---------- sesión ----------
  function guardarSesion(r, email, urlBase) {
    lsSet(LS.url, urlBase); lsSet(LS.token, (r.data && r.data.token) || ""); lsSet(LS.email, email);
  }
  function iniciarSesion(email, password, url) {
    var base = normalizarUrl(url);
    return llamar("POST", "/login", { email: email, password: password, dispositivo: "web" }, null, base)
      .then(function (r) {
        if (r.status !== 200) throw new Error(mensajeError(r));
        guardarSesion(r, email, base); return enviarPendientes();
      }, function () { throw new Error(ERR_RED); });
  }
  function registrar(nombre, email, password, codigo, url) {
    var base = normalizarUrl(url);
    var cuerpo = { name: nombre, email: email, password: password, dispositivo: "web" };
    if (codigo) cuerpo.codigo = codigo;
    return llamar("POST", "/register", cuerpo, null, base)
      .then(function (r) {
        if (r.status !== 200 && r.status !== 201) throw new Error(mensajeError(r));
        guardarSesion(r, email, base);
      }, function () { throw new Error(ERR_RED); });
  }
  function cerrarSesion() {
    var tk = getToken();
    var p = tk ? llamar("POST", "/logout", {}, tk).catch(function () { }) : Promise.resolve();
    return p.then(function () { lsSet(LS.token, ""); });
  }

  // ---------- informes ----------
  function limpiar(obj) {
    try { return JSON.parse(JSON.stringify(obj)); } catch (e) { return null; }   // NaN/Infinity -> null
  }

  function tipoDesdeArchivo(nombre) {
    var n = (nombre || "").toLowerCase();
    if (/general|consolidado/.test(n)) return "consolidado";
    if (/peso_volum/.test(n)) return "volumetrico";
    if (/gravedad/.test(n)) return "gravedad";
    if (/granulometr/.test(n)) return "granulometria";
    if (/clasificacion/.test(n)) return "clasificacion";
    if (/atterberg/.test(n)) return "atterberg";
    if (/proctor/.test(n)) return "proctor";
    if (/humedad/.test(n)) return "humedad";
    return "otro";
  }

  function pick(o, claves) {
    var r = {}; o = o || {};
    claves.forEach(function (k) { if (o[k] !== null && o[k] !== undefined && o[k] !== "") r[k] = o[k]; });
    return r;
  }

  function resumen(clave, e) {
    e = e || {};
    switch (clave) {
      case "humedad": return pick(e, ["promedio"]);
      case "volumetrico": return pick(e, ["rho_humeda", "gamma_kn_m3", "rho_seca", "gamma_seca"]);
      case "gravedad": return pick(e, ["gs", "gt", "temp"]);
      case "granulometria": return pick(e, ["grava", "arena", "finos", "d10", "d30", "d60", "cu", "cc"]);
      case "atterberg": { var r = pick(e, ["ll", "lp", "ip"]); r.np = !!e.np; return r; }
      case "clasificacion": {
        var c = {};
        if (e.sucs && e.sucs.simbolo) c.sucs = e.sucs.simbolo;
        if (e.aashto && e.aashto.texto) c.aashto = e.aashto.texto;
        return c;
      }
      case "proctor": return pick(e, ["mds", "och", "mds95", "gamma_kn_m3"]);
      default: return {};
    }
  }

  function textoClasificacion(cls) {
    var partes = [];
    if (cls && cls.sucs && cls.sucs.simbolo) partes.push("SUCS " + cls.sucs.simbolo);
    if (cls && cls.aashto && cls.aashto.texto) partes.push("AASHTO " + cls.aashto.texto);
    return partes.length ? partes.join(" | ") : null;
  }

  function construirInforme(nombreArchivo, estado) {
    var clave = tipoDesdeArchivo(nombreArchivo);
    var esCons = clave === "consolidado";
    var proy = estado.proyecto || {};
    var ens = estado.ensayos || {};
    var datosEns = {}, resultados = {}, cls = null;

    if (esCons) {
      Object.keys(ens).forEach(function (k) {
        if (ens[k] && ens[k].calculado) { datosEns[k] = ens[k]; resultados[k] = resumen(k, ens[k]); }
      });
      cls = ens.clasificacion;
    } else {
      datosEns[clave] = ens[clave] || {};
      resultados = resumen(clave, ens[clave]);
      if (clave === "clasificacion") cls = ens.clasificacion;
    }

    return {
      uid: uid(),
      proyecto: proy.nombre || "Proyecto sin título",
      muestra: proy.muestra || "",
      ensayo: clave,
      tipo: esCons ? "consolidado" : "individual",
      origen: "web",
      archivo_pdf: nombreArchivo || "",
      datos: limpiar({ proyecto: proy, ensayos: datosEns }) || {},
      resultados: limpiar(resultados) || {},
      clasificacion: textoClasificacion(cls)
    };
  }

  // Devuelve una promesa con { estado: ok|pendiente|sin_sesion|error, mensaje }
  function enviar(payload) {
    var tk = getToken();
    if (!tk) { encolar(payload); return Promise.resolve({ estado: "sin_sesion", mensaje: "Informe guardado en este navegador. Inicie sesión en ☁ Servidor para subirlo a la base de datos." }); }
    return llamar("POST", "/informes", payload, tk).then(function (r) {
      if (r.status === 200 || r.status === 201) { enviarPendientes(); return { estado: "ok", mensaje: "Informe guardado en la base de datos." }; }
      if (r.status === 401) { lsSet(LS.token, ""); encolar(payload); return { estado: "sin_sesion", mensaje: "La sesión expiró. Inicie sesión de nuevo en ☁ Servidor; el informe quedó en cola." }; }
      if (r.status >= 500) { encolar(payload); return { estado: "pendiente", mensaje: "El servidor tuvo un error. El informe quedó en cola." }; }
      return { estado: "error", mensaje: mensajeError(r) };
    }, function () {
      encolar(payload);
      return { estado: "pendiente", mensaje: "Sin conexión con el servidor. El informe quedó en cola y se enviará después." };
    });
  }

  function encolar(payload) {
    var c = getCola();
    if (!c.some(function (p) { return p.uid === payload.uid; })) c.push(payload);
    setCola(c); pintarBoton();
  }

  function enviarPendientes() {
    var tk = getToken(), cola = getCola();
    if (!tk || !cola.length) return Promise.resolve({ enviados: 0, quedan: cola.length });
    var enviados = 0, quedan = [];
    return cola.reduce(function (cadena, p, i) {
      return cadena.then(function (cortado) {
        if (cortado) { quedan.push(p); return true; }
        return llamar("POST", "/informes", p, tk).then(function (r) {
          if (r.status === 200 || r.status === 201) { enviados++; return false; }
          if (r.status === 401) { quedan.push(p); return true; }
          if (r.status >= 500) { quedan.push(p); return false; }
          return false;                                   // dato inválido: se descarta
        }, function () { quedan.push(p); return true; });
      });
    }, Promise.resolve(false)).then(function () {
      setCola(quedan); pintarBoton(); return { enviados: enviados, quedan: quedan.length };
    });
  }

  // Punto de entrada: se llama cada vez que se exporta un PDF
  function guardarDesdePDF(nombreArchivo) {
    var estado = window.GeoState || (typeof GeoState !== "undefined" ? GeoState : null);
    if (!estado) return;
    var payload = construirInforme(nombreArchivo, estado);
    enviar(payload).then(function (res) {
      avisar("☁ " + res.mensaje); pintarBoton();
    });
  }

  // ---------- interfaz ----------
  function textoEstado() {
    var n = getCola().length, tk = getToken(), email = lsGet(LS.email, "");
    var base = tk ? "☁ " + (email || "Sesión activa") : "☁ Sin sesión";
    return n ? base + " (" + n + " pend.)" : base;
  }

  function pintarBoton() {
    try {                                   // un fallo de pantalla nunca debe impedir guardar el informe
      var b = document.getElementById("btn-servidor");
      if (b) b.textContent = textoEstado();
      var e = document.getElementById("gs-estado");
      if (e) e.textContent = textoEstado();
    } catch (err) { /* sin interfaz */ }
  }

  function inyectarEstilos() {
    var css = "" +
      "#gs-overlay{position:fixed;inset:0;background:rgba(17,24,39,.6);z-index:9999;display:none;align-items:center;justify-content:center;padding:16px}" +
      "#gs-overlay.gs-abierto{display:flex}" +
      ".gs-modal{background:var(--bg-card,#fff);color:var(--neutral-body,#374151);border:1px solid var(--border-color,#cfd4dc);border-radius:6px;" +
      "box-shadow:0 8px 24px -4px rgba(17,24,39,.35);width:100%;max-width:470px;max-height:92vh;overflow:auto;padding:20px;font-family:var(--font-main,'Segoe UI',Arial,sans-serif)}" +
      ".gs-modal h3{margin:0 0 4px;color:var(--primary,#1f3a5f);font-size:1.15rem}" +
      ".gs-modal p.gs-ayuda{margin:0 0 12px;font-size:.85rem;color:var(--neutral-muted,#6b7280)}" +
      ".gs-modal label{display:block;font-size:.8rem;font-weight:700;margin:10px 0 3px;color:var(--neutral-heading,#1b2230)}" +
      ".gs-modal input{width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid var(--border-color,#cfd4dc);border-radius:4px;" +
      "background:var(--bg-card-alt,#f7f8fa);color:var(--neutral-dark,#111827);font-size:.9rem}" +
      "#gs-estado{margin:14px 0 4px;font-weight:700;font-size:.9rem;color:var(--primary,#1f3a5f)}" +
      "#gs-msg{min-height:1.2em;font-size:.85rem;margin-bottom:8px}" +
      "#gs-msg.gs-ok{color:var(--accent-green,#2f5d46)}#gs-msg.gs-err{color:var(--accent-red,#7f1d1d)}" +
      ".gs-botones{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}" +
      ".gs-botones button{padding:8px 12px;border:0;border-radius:4px;cursor:pointer;font-weight:700;font-size:.85rem;color:#fff;background:var(--primary,#1f3a5f)}" +
      ".gs-botones button:hover{filter:brightness(1.12)}" +
      ".gs-botones button.gs-verde{background:var(--accent-green,#2f5d46)}" +
      ".gs-botones button.gs-rojo{background:var(--accent-red,#7f1d1d)}" +
      ".gs-botones button.gs-gris{background:var(--neutral-muted,#6b7280)}" +
      ".gs-botones button:disabled{opacity:.55;cursor:wait}";
    var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
  }

  function crearModal() {
    var ov = document.createElement("div");
    ov.id = "gs-overlay";
    ov.innerHTML =
      '<div class="gs-modal" role="dialog" aria-modal="true" aria-labelledby="gs-titulo">' +
      '<h3 id="gs-titulo">Servidor y Base de Datos</h3>' +
      '<p class="gs-ayuda">Con la sesión iniciada, cada informe que exporte a PDF se guarda también en la base de datos. ' +
      'Si no hay conexión, queda en cola y se envía después.</p>' +
      '<label for="gs-url">Dirección del servidor</label><input id="gs-url" type="text" autocomplete="off">' +
      '<label for="gs-email">Correo</label><input id="gs-email" type="email" autocomplete="username">' +
      '<label for="gs-pass">Contraseña</label><input id="gs-pass" type="password" autocomplete="current-password">' +
      '<label for="gs-nombre">Nombre (solo al registrarse)</label><input id="gs-nombre" type="text" autocomplete="name">' +
      '<label for="gs-codigo">Código de registro (si lo piden)</label><input id="gs-codigo" type="text" autocomplete="off">' +
      '<div id="gs-estado"></div><div id="gs-msg"></div>' +
      '<div class="gs-botones">' +
      '<button type="button" id="gs-login">Iniciar sesión</button>' +
      '<button type="button" id="gs-registro" class="gs-verde">Registrarme</button>' +
      '<button type="button" id="gs-logout" class="gs-rojo">Cerrar sesión</button>' +
      '<button type="button" id="gs-pend" class="gs-gris">Enviar pendientes</button>' +
      '<button type="button" id="gs-cerrar" class="gs-gris">Cerrar</button>' +
      '</div></div>';
    document.body.appendChild(ov);

    var $ = function (id) { return document.getElementById(id); };
    var botones = ["gs-login", "gs-registro", "gs-logout", "gs-pend"];

    function msg(texto, ok) { var m = $("gs-msg"); m.textContent = texto; m.className = ok ? "gs-ok" : "gs-err"; }
    function ocupado(si) { botones.forEach(function (b) { $(b).disabled = si; }); }
    function correr(promesa, textoOk) {
      ocupado(true); msg("Conectando con el servidor...", true);
      promesa.then(function (r) { msg(typeof textoOk === "function" ? textoOk(r) : textoOk, true); },
                   function (e) { msg(e.message || String(e), false); })
             .then(function () { ocupado(false); pintarBoton(); });
    }

    $("gs-login").onclick = function () {
      var email = $("gs-email").value.trim(), pass = $("gs-pass").value;
      if (!email || !pass) return msg("Escriba su correo y contraseña.", false);
      correr(iniciarSesion(email, pass, $("gs-url").value), "Sesión iniciada correctamente.");
    };
    $("gs-registro").onclick = function () {
      var nombre = $("gs-nombre").value.trim(), email = $("gs-email").value.trim(), pass = $("gs-pass").value;
      if (!nombre || !email || pass.length < 8) return msg("Para registrarse escriba nombre, correo y una contraseña de al menos 8 caracteres.", false);
      correr(registrar(nombre, email, pass, $("gs-codigo").value.trim(), $("gs-url").value), "Cuenta creada y sesión iniciada.");
    };
    $("gs-logout").onclick = function () { correr(cerrarSesion(), "Sesión cerrada."); };
    $("gs-pend").onclick = function () {
      correr(enviarPendientes(), function (r) { return "Enviados: " + r.enviados + ". Pendientes: " + r.quedan + "."; });
    };
    $("gs-cerrar").onclick = cerrarModal;
    ov.addEventListener("click", function (ev) { if (ev.target === ov) cerrarModal(); });
    document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") cerrarModal(); });
  }

  function abrirModal() {
    document.getElementById("gs-url").value = getUrl();
    document.getElementById("gs-email").value = lsGet(LS.email, "");
    document.getElementById("gs-pass").value = "";
    document.getElementById("gs-msg").textContent = "";
    pintarBoton();
    document.getElementById("gs-overlay").classList.add("gs-abierto");
  }
  function cerrarModal() {
    var ov = document.getElementById("gs-overlay"); if (ov) ov.classList.remove("gs-abierto");
  }

  function iniciarUI() {
    inyectarEstilos(); crearModal();
    var contenedor = document.querySelector(".header-actions");
    var btn = document.createElement("button");
    btn.id = "btn-servidor"; btn.type = "button"; btn.className = "btn btn-secondary-sm";
    btn.title = "Iniciar sesión y guardar los informes en la base de datos";
    btn.onclick = abrirModal;
    if (contenedor) contenedor.insertBefore(btn, contenedor.firstChild);
    else { btn.style.cssText = "position:fixed;top:8px;right:8px;z-index:9000"; document.body.appendChild(btn); }
    pintarBoton();
    if (getToken()) enviarPendientes();      // reenviar lo que quedó pendiente la vez anterior
  }

  // ---------- gancho: cada PDF exportado se guarda en la base de datos ----------
  var original = window.ejecutarDescargaPDF;
  if (typeof original === "function") {
    window.ejecutarDescargaPDF = function (nombreArchivo) {
      var resultado = original.apply(this, arguments);
      try { guardarDesdePDF(nombreArchivo); } catch (e) { console.warn("GeoLab: no se pudo guardar en la base de datos:", e); }
      return resultado;
    };
  } else {
    console.warn("GeoLab: no se encontró ejecutarDescargaPDF; los informes no se guardarán en la base de datos.");
  }

  if (typeof document !== "undefined" && document.readyState !== "loading") iniciarUI();
  else if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded", iniciarUI);

  window.GeoServidor = {
    abrir: abrirModal, estado: textoEstado, enviarPendientes: enviarPendientes,
    _interno: { tipoDesdeArchivo: tipoDesdeArchivo, construirInforme: construirInforme, normalizarUrl: normalizarUrl }
  };
})();
