# Newsletter: como ligar (uma vez, uns 5 minutos)

Tudo grátis, na conta Google de quem cuida do site. Os e-mails dos inscritos ficam numa planilha **privada** dessa conta;
nada vai para o repositório.

1. Abra <https://script.google.com> logado na conta certa → **Novo projeto**. Dê o nome `Trampo com IA - newsletter`.
2. Apague o conteúdo do `Código.gs` e cole o arquivo [`Codigo.gs`](Codigo.gs) inteiro. Salve.
3. No topo, escolha a função **configurar** e clique em **Executar**. O Google pede autorização (planilhas e envio de e-mail
   pela sua conta): **Revisar permissões → sua conta → Avançado → Acessar (não seguro) → Permitir**. O aviso aparece porque o
   script é seu e não passou pela verificação do Google; é normal.
4. Em **Registro de execução** aparecem o link da planilha e a **Chave para o PC**. Copie a chave.
5. **Implantar → Nova implantação → tipo App da Web**. Executar como: **Eu**. Quem pode acessar: **Qualquer pessoa**. Implantar e
   copie a **URL do app da Web** (termina em `/exec`).
6. No site, em `site/newsletter.json`, coloque a URL em `endpoint`. Ao publicar, a caixa de inscrição aparece no site.
7. No PC, crie `dados/newsletter.local.json` (fica fora do git):

   ```json
   {"endpoint": "https://script.google.com/macros/s/.../exec", "chave": "CHAVE_DO_PASSO_4"}
   ```

8. Teste: `python -m hub newsletter --simular` e depois `python -m hub newsletter --teste seu@email.com`.

A rotina diária (`rotina.cmd`) já roda `python -m hub newsletter` depois da coleta. Ela manda um e-mail por dia, só quando
há vagas novas que não são fechadas para o Brasil, pelo Gmail configurado no `cerebro emails --configurar`.

## Limites a acompanhar
- O Apps Script manda até ~100 e-mails de confirmação por dia (conta Google gratuita).
- O Gmail pessoal manda até ~500 e-mails por dia. Passando de uns 300 inscritos, vale mudar o envio para um serviço de
  newsletter (Brevo, MailerLite) ou um Gmail só do site.
- Se mudar o `Codigo.gs`, use **Implantar → Gerenciar implantações → editar → Nova versão** para manter a mesma URL.
