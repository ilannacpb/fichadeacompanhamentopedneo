# Ficha de Acompanhamento Farmacêutico — Pediatria & Neonatologia

Aplicativo web para acompanhamento farmacoterapêutico em UTI Neonatal, UTI Pediátrica e UCSIN, com geração automática de evolução clínica e reconciliação medicamentosa por template, registro de intervenções farmacêuticas, e indicadores de farmácia clínica.

## Estrutura do repositório

```
├── index.html                → O APLICATIVO (front-end)
├── netlify.toml               → Configuração do Netlify (funções + rotas /api/*)
├── package.json                → Dependência da função (@netlify/database)
├── netlify/functions/
│   ├── setup-db.js             → Cria a tabela "pacientes" (rodar 1x)
│   └── pacientes.js            → API: listar / criar / atualizar / excluir pacientes
├── planilhas-comparativas/     → Versões em planilha, feitas como comparação ao app
└── prototipo-python/           → Protótipo inicial em Python/Streamlit
```

## Configuração do banco de dados (equipe compartilhada)

1. **Ative o banco**: no seu site → aba **Database** → siga o fluxo de criação (Postgres gerenciado, powered by Neon).
2. **Pegue a connection string**: na tela do banco, clique na branch **"production"** → copie a string **"Read and write"**.
3. **Configure as variáveis de ambiente**: em **Project configuration → Environment variables**, crie:
   - `PACIENTES_DB_URL` → a connection string que você copiou
   - `EQUIPE_SENHA` → a senha que toda a equipe vai usar para entrar no app
4. **Force um novo deploy** (qualquer edição no repositório, ex: no README, dispara isso automaticamente).
5. **Crie a tabela**: acesse uma vez no navegador `https://SEU-SITE.netlify.app/.netlify/functions/setup-db`.
6. **Pronto**: ao abrir o app, aparece uma tela pedindo nome + a senha da equipe. Todo mundo usa a mesma senha; o nome é só pra identificar quem criou/alterou cada registro.

### Migrando dados que já existiam no seu navegador

Use o botão **"Restaurar Backup"** depois de logada — ele envia esses pacientes para o banco compartilhado automaticamente.

## Sobre o acesso aos dados

Como o app guarda dados clínicos reais num banco compartilhado (não mais só no seu navegador), veja com o setor de TI/compliance do hospital se essa forma de hospedagem está de acordo com a política de dados da instituição.

## Sobre as planilhas comparativas e o protótipo Python

Ficaram no repositório como registro do processo de comparação de abordagens — o app (`index.html` + backend) é a versão recomendada para uso contínuo.
