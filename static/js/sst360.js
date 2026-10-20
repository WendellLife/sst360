/* SST360 · comportamento do shell no padrão Razach Tarefas Internas:
   alternar tema (guardado no navegador), recolher a barra lateral e atalho "/" para a busca. */
(function () {
  "use strict";
  var d = document.documentElement;
  function guardar(chave, valor) { try { localStorage.setItem(chave, valor); } catch (e) { /* sem armazenamento */ } }
  function trocar(fn) { if (document.startViewTransition) document.startViewTransition(fn); else fn(); }

  document.addEventListener("click", function (ev) {
    var tema = ev.target.closest("[data-tema-alternar]");
    if (tema) {
      var novo = d.getAttribute("data-theme") === "dark" ? "light" : "dark";
      trocar(function () { d.setAttribute("data-theme", novo); });
      guardar("rz-tema", novo);
      return;
    }
    var menu = ev.target.closest("[data-menu-alternar]");
    if (menu) {
      var abrir = d.getAttribute("data-menu") !== "aberto";
      if (abrir) d.setAttribute("data-menu", "aberto"); else d.removeAttribute("data-menu");
      menu.setAttribute("aria-expanded", abrir ? "true" : "false");
      menu.setAttribute("aria-label", abrir ? "Fechar menu" : "Abrir menu");
      return;
    }
    var barra = ev.target.closest("[data-barra-recolher]");
    if (barra) {
      var recolher = d.getAttribute("data-barra") !== "recolhida";
      trocar(function () { if (recolher) d.setAttribute("data-barra", "recolhida"); else d.removeAttribute("data-barra"); });
      barra.setAttribute("aria-expanded", recolher ? "false" : "true");
      barra.setAttribute("aria-label", recolher ? "Abrir barra lateral" : "Recolher barra lateral");
      guardar("rz-barra", recolher ? "recolhida" : "aberta");
    }
  });

  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "/" || /input|textarea|select/i.test(ev.target.tagName || "") || ev.target.isContentEditable) return;
    var campo = document.querySelector("[data-atalho='/']");
    if (campo) { ev.preventDefault(); campo.focus(); }
  });


  /* Subtítulo da página vira um ícone de informação ao lado do título (dica ao passar o mouse,
     ao focar ou ao tocar). O texto continua no HTML; sem JS ele aparece como parágrafo. */
  var ICONE_INFO = '<svg class="ic" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>';
  var nDica = 0;
  function infoTitulo(raiz) {
    (raiz || document).querySelectorAll(".cabecalho .subtitulo").forEach(function (p) {
      var cab = p.closest(".cabecalho"), h1 = cab && cab.querySelector("h1");
      if (!h1 || h1.querySelector(".info-titulo") || !p.textContent.trim()) return;
      var id = "dica-titulo-" + (++nDica);
      var w = document.createElement("span");
      w.className = "info-titulo";
      w.innerHTML = '<button type="button" class="ib info-titulo__btn" aria-label="Sobre esta página" aria-expanded="false" aria-describedby="' + id + '">' + ICONE_INFO + "</button>" +
        '<span class="info-titulo__dica" role="tooltip" id="' + id + '"></span>';
      var dica = w.querySelector(".info-titulo__dica");
      while (p.firstChild) dica.appendChild(p.firstChild);
      h1.appendChild(w);
      p.remove();
    });
  }
  window.SST360InfoTitulo = infoTitulo;
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest(".info-titulo__btn");
    document.querySelectorAll(".info-titulo.is-open").forEach(function (w) {
      if (!b || w !== b.parentNode) { w.classList.remove("is-open"); w.firstChild.setAttribute("aria-expanded", "false"); }
    });
    if (b) { var w = b.parentNode, aberto = w.classList.toggle("is-open"); b.setAttribute("aria-expanded", aberto ? "true" : "false"); }
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    document.querySelectorAll(".info-titulo.is-open").forEach(function (w) {
      var tinha = w.contains(document.activeElement);
      w.classList.remove("is-open"); w.firstChild.setAttribute("aria-expanded", "false");
      if (tinha) w.firstChild.focus();
    });
  });

  /* Sino de avisos (<details>): fecha com Escape (devolvendo o foco ao botão) e com clique fora. */
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    document.querySelectorAll("details.sino[open]").forEach(function (det) {
      var tinha = det.contains(document.activeElement);
      det.removeAttribute("open");
      if (tinha) { var s = det.querySelector("summary"); if (s) s.focus(); }
    });
  });
  document.addEventListener("click", function (ev) {
    document.querySelectorAll("details.sino[open]").forEach(function (det) { if (!det.contains(ev.target)) det.removeAttribute("open"); });
  });

  /* Formulário com data-autosubmit: o <select> envia ao escolher com o mouse ou toque. Com as setas
     do teclado cada passo dispara "change"; aí não envia, e o botão "Aplicar" (visível sem JS,
     escondido por CSS com JS) aparece para confirmar. */
  var navTeclado = false;
  document.addEventListener("keydown", function (ev) {
    if (/^(Arrow|Home$|End$|Page)/.test(ev.key) && ev.target.closest && ev.target.closest("form[data-autosubmit]")) navTeclado = true;
  });
  document.addEventListener("keyup", function () { navTeclado = false; });
  document.addEventListener("change", function (ev) {
    var form = ev.target.closest && ev.target.closest("form[data-autosubmit]");
    if (!form || ev.target.tagName !== "SELECT") return;
    if (navTeclado) { form.classList.add("is-pendente"); return; }
    if (form.requestSubmit) form.requestSubmit(); else form.submit();
  });
  document.addEventListener("DOMContentLoaded", function () {
    infoTitulo();
    var barra = document.querySelector("[data-barra-recolher]");
    if (barra && !barra.hasAttribute("aria-controls") && document.getElementById("sb-rolagem")) barra.setAttribute("aria-controls", "sb-rolagem");
    if (barra && d.getAttribute("data-barra") === "recolhida") { barra.setAttribute("aria-expanded", "false"); barra.setAttribute("aria-label", "Abrir barra lateral"); }
  });
})();
