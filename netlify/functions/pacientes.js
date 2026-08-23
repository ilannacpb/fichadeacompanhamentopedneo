// API de pacientes. Exige login (Netlify Identity) — o front-end manda o token
// da usuária logada no cabeçalho Authorization, e o Netlify já decodifica isso
// automaticamente em context.clientContext.user.
exports.handler = async (event, context) => {
  const user = context.clientContext && context.clientContext.user;
  if (!user) {
    return { statusCode: 401, body: JSON.stringify({ error: 'Não autenticado. Faça login para continuar.' }) };
  }

  try {
    const { getDatabase } = await import('@netlify/database');
    const db = getDatabase({ connectionString: process.env.NETLIFY_DB_URL });

    if (event.httpMethod === 'GET') {
      const rows = await db.sql`SELECT id, dados, atualizado_em FROM pacientes ORDER BY id ASC`;
      const pacientes = rows.map(r => Object.assign({}, r.dados, { id: r.id }));
      return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pacientes) };
    }

    if (event.httpMethod === 'POST') {
      const dados = JSON.parse(event.body);
      const rows = await db.sql`
        INSERT INTO pacientes (dados, criado_por, atualizado_por)
        VALUES (${JSON.stringify(dados)}::jsonb, ${user.email}, ${user.email})
        RETURNING id
      `;
      return { statusCode: 200, body: JSON.stringify({ id: rows[0].id }) };
    }

    if (event.httpMethod === 'PUT') {
      const { id, dados } = JSON.parse(event.body);
      if (!id) return { statusCode: 400, body: JSON.stringify({ error: 'id é obrigatório para atualizar.' }) };
      await db.sql`
        UPDATE pacientes
        SET dados = ${JSON.stringify(dados)}::jsonb, atualizado_por = ${user.email}, atualizado_em = now()
        WHERE id = ${id}
      `;
      return { statusCode: 200, body: JSON.stringify({ ok: true }) };
    }

    return { statusCode: 405, body: 'Método não suportado.' };
  } catch (err) {
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
  }
};
