# Segurança do ARKHER AI

## Garantias de arquitetura
- **Nenhum segredo no frontend** — o bundle não contém chave, token ou endpoint externo.
- O navegador fala só com o backend próprio (`/api`); CORS restrito por `ARKHER_CORS_ORIGINS`.
- Autenticação própria em modo local: token de dispositivo armazenado **somente como hash**.
- SQLite local; nenhum serviço de terceiros para dados, memória ou embeddings.

## Camadas de conteúdo
1. **Entrada** (`security/guard.check_input`): recusa honesta de categorias
   proibidas — ilegal, +18, trapaças/exploits de jogos online, malware.
   Fora disso, sem censura desnecessária.
2. **Saída** (`security/guard.check_output`) — camada extra de correção:
   - verifica contas aritméticas declaradas e corrige resultado errado;
   - aponta alegações de ações não executadas ("acessei a internet" sem ferramenta);
   - impede atribuição da resposta a terceiros.
3. **Ferramentas**: só executam com autorização do usuário; argumentos validados;
   calculadora usa AST (nunca `eval` livre); leitura de arquivos restrita à sandbox
   por usuário com proteção contra path traversal; toda execução vai para auditoria.
4. **Memória**: exige consentimento explícito; rejeita texto com cara de segredo.
5. **Logs**: filtro de redação remove padrões de token/senha antes de registrar.

## Limites operacionais
- Mensagem ≤ 4000 caracteres; entrada/saída do modelo limitadas em tokens.
- Rate limit por usuário (chat e API) com janela de 1 minuto.
- Timeout de geração e de carregamento de modelo; nada fica "carregando" para sempre.
- Nenhum `eval` com entrada do usuário, nenhum shell no navegador, nenhum acesso remoto.

## Postura de liberdade
A ARKHER evita censura além do necessário: as recusas são as quatro categorias acima,
explícitas e auditáveis no código. A política evolui por regra declarada, nunca por
filtro oculto.
