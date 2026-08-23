// Rode esta função UMA VEZ, visitando /.netlify/functions/setup-db no navegador,
// para criar a tabela "pacientes" (se ela ainda não existir). Pode rodar de novo
// sem problema — não apaga dados existentes.
exports.handler = async () => {
  try {
    const { getDatabase } = await import('@netlify/database');
    const db = getDatabase({ connectionString: process.env.NETLIFY_DB_URL });
    await db.sql`
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
    return { statusCode: 500, body: 'Erro ao criar tabela: ' + err.message + (process.env.NETLIFY_DB_URL ? '' : ' [NETLIFY_DB_URL está vazia neste processo]') };
  }
};
