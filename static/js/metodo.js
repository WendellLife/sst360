/* Percorre as 12 etapas do metodo em sequencia.
   Sem JavaScript a pagina continua legivel: todas as etapas aparecem de uma vez. */
(function () {
  "use strict";
  var raiz = document.querySelector("[data-metodo]");
  if (!raiz) return;

  var etapas = Array.prototype.slice.call(raiz.querySelectorAll(".etapa-metodo"));
  var botao = document.querySelector("[data-metodo-botao]");
  var resumo = document.querySelector("[data-metodo-resumo]");
  var barra = document.querySelector("[data-metodo-barra]");
  var luz = document.querySelector("[data-metodo-luz]");
  if (!etapas.length || !botao) return;

  var reduzido = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var intervalo = reduzido ? 300 : 1400;
  var textoInicial = resumo ? resumo.textContent : "";
  var atual = 0, rodando = false, pausado = false, temporizador = null;

  function pintar() {
    etapas.forEach(function (etapa, indice) {
      etapa.classList.toggle("apagada", (rodando || pausado) && indice >= atual);
      etapa.classList.toggle("acesa", indice < atual);
    });
    var total = etapas.length;
    var feito = Math.min(atual, total);
    if (barra) barra.style.width = Math.round((feito / total) * 100) + "%";
    if (resumo) {
      resumo.textContent = feito === 0
        ? textoInicial
        : "Etapa " + String(feito).padStart(2, "0") + " de " + total + " · " +
          etapas[feito - 1].getAttribute("data-titulo");
    }
    if (luz) luz.classList.toggle("acesa", atual >= total);
  }

  function rotulo() {
    if (atual >= etapas.length && !rodando) return "Percorrer de novo";
    if (pausado) return "Continuar";
    if (rodando) return "Pausar";
    return "Percorrer o método";
  }

  function passo() {
    clearTimeout(temporizador);
    temporizador = setTimeout(function () {
      if (!rodando || pausado) return;
      atual += 1;
      pintar();
      if (atual >= etapas.length) {
        rodando = false;
        botao.textContent = rotulo();
        return;
      }
      passo();
    }, intervalo);
  }

  botao.addEventListener("click", function () {
    if (rodando && !pausado) {
      pausado = true;
      rodando = false;
      clearTimeout(temporizador);
    } else if (pausado) {
      pausado = false;
      rodando = true;
      passo();
    } else {
      atual = 0;
      rodando = true;
      pintar();
      passo();
    }
    botao.textContent = rotulo();
  });

  botao.hidden = false;
  pintar();
})();
