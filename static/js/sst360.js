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

  document.addEventListener("DOMContentLoaded", function () {
    var barra = document.querySelector("[data-barra-recolher]");
    if (barra && d.getAttribute("data-barra") === "recolhida") { barra.setAttribute("aria-expanded", "false"); barra.setAttribute("aria-label", "Abrir barra lateral"); }
  });
})();
