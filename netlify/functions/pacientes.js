// API de pacientes. Protegida por uma senha única compartilhada da equipe
// (variável de ambiente EQUIPE_SENHA).
//
// Tem DOIS jeitos de autenticar, dependendo de como o pedido chega:
// 1) Uso normal do app: a senha vai no cabeçalho X-Team-Password.
// 2) Salvamento ao fechar/sair da página (via navigator.sendBeacon): o navegador
//    não permite cabeçalhos customizados nesse tipo de envio, então a senha vai
//    dentro do corpo do pedido, junto com a lista inteira de pacientes de uma vez
//    (ver "pacientesBatch" abaixo).
// "_novo" (marca só do navegador) e o id temporário nunca devem ser gravados dentro da ficha:
// o id verdadeiro é a coluna "id" da tabela. Fichas antigas que já ficaram com essas marcas
// gravadas também saem limpas na leitura, para não serem recriadas como se fossem novas.
function limparDados(obj){
  const d = Object.assign({}, obj || {});
  delete d._novo;
  delete d.id;
  return d;
}

exports.handler = async (event) => {
  let bodyParsed = null;
  try { bodyParsed = event.body ? JSON.parse(event.body) : null; } catch (e) { bodyParsed = null; }

  // ---------- Salvamento em lote via sendBeacon (ao sair da página) ----------
  if (event.httpMethod === 'POST' && bodyParsed && Array.isArray(bodyParsed.pacientesBatch)) {
    const senha = bodyParsed.senha;
    const nome = bodyParsed.nome || 'Desconhecido';
    if (!senha || senha !== process.env.EQUIPE_SENHA) {
      return { statusCode: 401, body: JSON.stringify({ error: 'Senha da equipe incorreta.' }) };
    }
    try {
      const { getDatabase } = await import('@netlify/database');
      const db = getDatabase({ connectionString: process.env.PACIENTES_DB_URL });
      for (const p of bodyParsed.pacientesBatch) {
        if (typeof p.id === 'number' && p.id < 0) {
          // paciente novo (ainda não existe no banco) -> cria
          await db.sql`
            INSERT INTO pacientes (dados, criado_por, atualizado_por)
            VALUES (${JSON.stringify(limparDados(p))}::jsonb, ${nome}, ${nome})
          `;
        } else {
          // paciente já existente -> atualiza
          await db.sql`
            UPDATE pacientes
            SET dados = ${JSON.stringify(limparDados(p))}::jsonb, atualizado_por = ${nome}, atualizado_em = now()
            WHERE id = ${p.id}
          `;
        }
      }
      return { statusCode: 200, body: JSON.stringify({ ok: true }) };
    } catch (err) {
      return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
    }
  }

  // ---------- Uso normal (com cabeçalho de senha) ----------
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
      const pacientes = rows.map(r => Object.assign({}, limparDados(r.dados), { id: r.id }));
      return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pacientes) };
    }

    if (event.httpMethod === 'POST') {
      const dados = limparDados(bodyParsed);
      const rows = await db.sql`
        INSERT INTO pacientes (dados, criado_por, atualizado_por)
        VALUES (${JSON.stringify(dados)}::jsonb, ${nomeUsuario}, ${nomeUsuario})
        RETURNING id
      `;
      return { statusCode: 200, body: JSON.stringify({ id: rows[0].id }) };
    }

    if (event.httpMethod === 'PUT') {
      const { id, dados } = bodyParsed;
      if (!id) return { statusCode: 400, body: JSON.stringify({ error: 'id é obrigatório para atualizar.' }) };
      await db.sql`
        UPDATE pacientes
        SET dados = ${JSON.stringify(limparDados(dados))}::jsonb, atualizado_por = ${nomeUsuario}, atualizado_em = now()
        WHERE id = ${id}
      `;
      return { statusCode: 200, body: JSON.stringify({ ok: true }) };
    }

    if (event.httpMethod === 'DELETE') {
      const { id } = bodyParsed;
      if (!id) return { statusCode: 400, body: JSON.stringify({ error: 'id é obrigatório para excluir.' }) };
      await db.sql`DELETE FROM pacientes WHERE id = ${id}`;
      return { statusCode: 200, body: JSON.stringify({ ok: true }) };
    }

    return { statusCode: 405, body: 'Método não suportado.' };
  } catch (err) {
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
  }
};
