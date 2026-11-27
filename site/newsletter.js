"use strict";
// Caixa "Receba as vagas novas no seu e-mail". O endereço do serviço de inscrição fica em newsletter.json;
// sem ele a caixa continua escondida, então o site nunca mostra um formulário que não funciona.
(() => {
  const AREAS = ["Programação", "Negócios e atendimento", "Idiomas e tradução", "Design e mídia", "Saúde", "Direito",
    "Exatas", "Finanças", "Segurança e TI", "Escrita e conteúdo", "Educação", "Outras áreas"];
  const base = new URL(".", document.currentScript.src);
  const caixas = document.querySelectorAll(".news");
  if (!caixas.length) return;

  fetch(new URL("newsletter.json", base), { cache: "no-cache" })
    .then((r) => r.json())
    .then((cfg) => { if (/^https:\/\/script\.google\.com\//.test(cfg.endpoint || "")) caixas.forEach((c) => preparar(c, cfg.endpoint)); })
    .catch(() => {});

  function preparar(caixa, endpoint) {
    const form = caixa.querySelector("form");
    const msg = form.querySelector(".news-msg");
    form.querySelector(".news-chips").innerHTML = AREAS.map((a) =>
      `<label class="chip"><input type="checkbox" name="area" value="${a}"> ${a}</label>`).join("");
    caixa.hidden = false;
    document.querySelectorAll(".news-link").forEach((l) => (l.hidden = false));

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const email = form.email.value.trim();
      msg.className = "news-msg";
      if (!/^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i.test(email)) { msg.textContent = "Confira o e-mail digitado."; msg.classList.add("erro"); return; }
      if (!form.consentimento.checked) { msg.textContent = "Marque a caixa de aceite para continuar."; msg.classList.add("erro"); return; }
      const corpo = new URLSearchParams({
        acao: "inscrever", email, consentimento: "sim", site: form.site.value,
        areas: [...form.querySelectorAll("input[name=area]:checked")].map((i) => i.value).join("|"),
        origem: form.dataset.origem || "",
      });
      const botao = form.querySelector("button");
      botao.disabled = true; msg.textContent = "Enviando…";
      try {
        // o Google Apps Script não libera a leitura da resposta para outros sites; o envio chega mesmo assim
        await fetch(endpoint, { method: "POST", mode: "no-cors", body: corpo });
        form.reset();
        msg.textContent = "Quase lá! Enviamos um e-mail de confirmação. Clique no link dele para começar a receber (olhe também o spam e a aba Promoções).";
        msg.classList.add("ok");
      } catch (_) {
        msg.textContent = "Não consegui enviar agora. Tente de novo em instantes."; msg.classList.add("erro");
      } finally { botao.disabled = false; }
    });
  }
})();
