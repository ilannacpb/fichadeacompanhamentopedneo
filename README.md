# Ficha de Acompanhamento Farmacêutico — Pediatria & Neonatologia

Aplicativo web para acompanhamento farmacoterapêutico em UTI Neonatal, UTI Pediátrica e UCSIN, com geração automática de evolução clínica e reconciliação medicamentosa por template, registro de intervenções farmacêuticas, e indicadores de farmácia clínica.

## Estrutura do repositório

```
├── index.html                → O APLICATIVO (front-end)
├── netlify.toml               → Configuração do Netlify (funções + rotas /api/*)
├── package.json                → Dependência da função (@netlify/neon)
├── netlify/functions/
│   ├── setup-db.js             → Cria a tabela "pacientes" (rodar 1x)
│   └── pacientes.js            → API: listar / criar / atualizar pacientes
├── planilhas-comparativas/     → Versões em planilha, feitas como comparação ao app
└── prototipo-python/           → Protótipo inicial em Python/Streamlit
```

## Configuração do banco de dados (equipe compartilhada)

Passo a passo, direto no painel do Netlify:

1. **Ative o banco**: no seu site → aba **Database** → siga o fluxo de criação (é o Postgres gerenciado pelo Netlify/Neon). Isso já configura sozinho a variável de conexão que as funções usam.
2. **Ative o login da equipe**: no seu site → **Site configuration → Identity → Enable Identity**. Em "Registration preferences", escolha **Invite only** (assim só quem você convidar consegue entrar). Depois, na aba Identity, convide cada farmacêutica pelo e-mail dela.
3. **Crie a tabela**: depois do deploy, acesse uma vez no navegador:
   `https://SEU-SITE.netlify.app/.netlify/functions/setup-db`
   Deve aparecer uma mensagem confirmando que a tabela foi criada. Só precisa fazer isso uma vez.
4. **Pronto**: ao abrir o app, vai aparecer uma tela de login. Cada pessoa da equipe entra com o e-mail que você convidou, e todos veem os mesmos pacientes.

### Migrando dados que já existiam no seu navegador

Se você já usava o app antes (dados salvos localmente), use o botão **"Restaurar Backup"** depois de logada — ele agora envia esses pacientes para o banco compartilhado automaticamente, em vez de só recarregar localmente.

## Sobre o acesso aos dados

Como a partir de agora o app guarda dados clínicos reais num banco compartilhado (não mais só no seu navegador), veja com o setor de TI/compliance do hospital se essa forma de hospedagem (conta pessoal no Netlify) está de acordo com a política de dados da instituição antes de colocar a equipe toda usando.

## Sobre as planilhas comparativas e o protótipo Python

Ficaram no repositório como registro do processo de comparação de abordagens — o app (`index.html` + backend) é a versão recomendada para uso contínuo
