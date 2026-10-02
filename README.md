# Ficha de Acompanhamento Farmacêutico — Pediatria & Neonatologia

Aplicativo web para acompanhamento farmacoterapêutico em UTI Neonatal, UTI Pediátrica e UCSIN.

## Estrutura

```
├── index.html                → O APLICATIVO (front-end)
├── netlify.toml               → Configuração do Netlify (funções + rotas /api/*)
├── package.json                → Dependência da função (@netlify/database)
├── netlify/functions/
│   ├── setup-db.js             → Cria a tabela "pacientes" (rodar 1x)
│   └── pacientes.js            → API: listar / criar / atualizar / excluir pacientes
├── planilhas-comparativas/
└── prototipo-python/
```

## Atualização importante: salvamento ao sair da página

O app salva automaticamente a cada 8 segundos enquanto está aberto. Para o momento de SAIR/fechar
a aba, agora usa `navigator.sendBeacon()` em vez de `fetch()` — isso evita que o navegador corte o
salvamento no meio do caminho quando a página está fechando (um problema real que causava perda de
dados antes). Essa mudança exige o `pacientes.js` atualizado — se você já tinha subido uma versão
anterior, suba esse arquivo de novo.

## Configuração do banco de dados

1. Ative o banco na aba **Database** do seu projeto Netlify.
2. Pegue a connection string **"Read and write"** da branch "production".
3. Em **Project configuration → Environment variables**, crie:
   - `PACIENTES_DB_URL` → a connection string
   - `EQUIPE_SENHA` → a senha que a equipe toda vai usar
4. Force um novo deploy (qualquer edição no repositório dispara isso).
5. Acesse uma vez `https://SEU-SITE.netlify.app/.netlify/functions/setup-db` pra criar a tabela.
