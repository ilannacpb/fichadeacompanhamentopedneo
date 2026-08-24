// API de pacientes. Protegida por uma senha única compartilhada da equipe
// (variável de ambiente EQUIPE_SENHA), enviada pelo front-end no cabeçalho
// X-Team-Password a cada chamada. O nome de quem está usando (X-Team-Name)
// é auto-declarado (não autenticado) e usado só para fins de registro.
exports.handler = async (event) => {
  const senhaEnviada = event.headers['x-team-password'] || event.headers['X-Team-Password'];
  const nomeUsuario = event.headers['x-team-name'] || event.headers['X-Team-Name'] || 'Desconhecido';

  if (!senhaEnviada || senhaEnviada !== process.env.EQUIPE_SENHA) {
    return { statusCode: 401, body: JSON.stringify({ error: 'Senha da equipe incorreta.' }) };
  }

  try {
    const { getDatabase } = await import('@netlify/database');
    const db = getDatabase({ connectionString: process.env.PACIENTES_DB_URL });

    if (event.httpMethod === 'GET') {
      const rows = await db.sql`SELECT id, dados, atualizado_em FROM pacientes ORDER BY id ASC`;
      const pacientes = rows.map(r => Object.assign({}, r.dados, { id: r.id }));
      return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pacientes) };
    }

    if (event.httpMethod === 'POST') {
      const dados = JSON.parse(event.body);
      const rows = await db.sql`
        INSERT INTO pacientes (dados, criado_por, atualizado_por)
        VALUES (${JSON.stringify(dados)}::jsonb, ${nomeUsuario}, ${nomeUsuario})
        RETURNING id
      `;
      return { statusCode: 200, body: JSON.stringify({ id: rows[0].id }) };
    }

    if (event.httpMethod === 'PUT') {
      const { id, dados } = JSON.parse(event.body);
      if (!id) return { statusCode: 400, body: JSON.stringify({ error: 'id é obrigatório para atualizar.' }) };
      await db.sql`
        UPDATE pacientes
        SET dados = ${JSON.stringify(dados)}::jsonb, atualizado_por = ${nomeUsuario}, atualizado_em = now()
        WHERE id = ${id}
      `;
      return { statusCode: 200, body: JSON.stringify({ ok: true }) };
    }

    return { statusCode: 405, body: 'Método não suportado.' };
  } catch (err) {
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
  }
};
