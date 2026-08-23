// Rode esta função UMA VEZ, visitando /.netlify/functions/setup-db no navegador,
// depois de ativar o Netlify Database no seu site. Ela cria a tabela "pacientes"
// se ela ainda não existir. Pode rodar de novo sem problema (não apaga dados).
const { neon } = require('@netlify/neon');

exports.handler = async () => {
  try {
    const sql = neon();
    await sql`
      CREATE TABLE IF NOT EXISTS pacientes (
        id SERIAL PRIMARY KEY,
        dados JSONB NOT NULL,
        criado_por TEXT,
        atualizado_por TEXT,
        criado_em TIMESTAMPTZ DEFAULT now(),
        atualizado_em TIMESTAMPTZ DEFAULT now()
      )
    `;
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      body: 'Tabela "pacientes" criada (ou já existia). Pode fechar esta aba e voltar para o app.'
    };
  } catch (err) {
    return { statusCode: 500, body: 'Erro ao criar tabela: ' + err.message };
  }
};
