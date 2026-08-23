"""
Acompanhamento Farmacêutico Hospitalar - UTI & Clínica
=======================================================
App Streamlit para evoluções farmacêuticas padronizadas (metodologia PW),
registro de intervenções, cálculo de indicadores por paciente-dia e
geração de texto via API da Anthropic (Claude).

Instalação:
    pip install streamlit anthropic pandas openpyxl

Execução:
    streamlit run app_farmacia_clinica.py

Persistência:
    Os dados são gravados em um banco SQLite local (farmacia_clinica.db),
    na mesma pasta do script. Isso sobrevive a reinícios do app, mas se
    você publicar em um serviço com sistema de arquivos efêmero (ex: alguns
    planos de Streamlit Cloud), o arquivo pode ser apagado a cada novo
    deploy. Use os botões de Backup/Restauração na barra lateral para
    exportar e reimportar o banco quando precisar.
"""

import streamlit as st
import pandas as pd
import sqlite3
import datetime
import io
import anthropic

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Acompanhamento Farmacêutico - UTI & Clínica",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Acompanhamento Farmacêutico Hospitalar")
st.markdown("Plataforma de Gestão Clínica, Evolução Automatizada & Indicadores")

DB_PATH = "farmacia_clinica.db"

# Setores do HPMAF (ajuste livremente conforme sua realidade institucional)
SETORES_HPMAF = [
    "UTIN", "UTIP", "FUT", "FUI", "FPA", "FAMAT",
    "FAPED", "FANEO", "FAONCO", "FARZN", "FCC", "FAOBS", "Outro"
]

# ==============================================================================
# TAXONOMIA INSTITUCIONAL DE INTERVENÇÕES (FONTE ÚNICA DE VERDADE)
# ==============================================================================
# Esta é a ÚNICA definição da taxonomia no app. O prompt enviado à API é
# gerado a partir deste dicionário, então não há risco de o texto do
# system prompt e as opções dos formulários ficarem dessincronizados.
TAXONOMIA_INTERVENCOES = {
    "Dose": {
        "motivos": [
            "Necessidade de dose de ataque", "Subdose (Literatura)",
            "Subdose (Função Renal/PK-PD)", "Sobredose (Literatura)",
            "Sobredose (Função Renal/PK-PD)"
        ],
        "sugestoes": [
            "Fazer dose de ataque", "Ajustar dose/frequência",
            "Ajustar dose e frequência", "Dose complementar pós-diálise",
            "Medicamento pós-diálise"
        ]
    },
    "Dispensação": {
        "motivos": ["Medicamento indisponível", "Medicamento não padronizado"],
        "sugestoes": ["Substituir medicamento"]
    },
    "Frequência de Administração": {
        "motivos": ["Frequência aumentada (menor intervalo)", "Frequência diminuída (maior intervalo)"],
        "sugestoes": ["Ajustar frequência"]
    },
    "Via / Forma Farmacêutica": {
        "motivos": ["Via inadequada para condição clínica", "Critérios para iniciar transição oral", "Forma inadequada para a via"],
        "sugestoes": ["Substituir forma farmacêutica", "Substituir medicamento", "Substituir via de administração", "Realizar transição oral"]
    },
    "Administração por Sonda": {
        "motivos": ["Administração inadequada por sonda enteral"],
        "sugestoes": ["Substituir forma/medicamento/via", "Diluir com volume adequado para sonda"]
    },
    "Tempo de Infusão & Diluição": {
        "motivos": ["Tempo de infusão não adequado/ausente", "Indicação de infusão estendida", "Volume diluição/reconstituição ausente/inadequado", "Necessidade de restrição hídrica"],
        "sugestoes": ["Ajustar/incluir tempo de infusão", "Prescrever infusão estendida", "Inserir/ajustar volume de diluição", "Substituir diluente / Restringir volume"]
    },
    "Indicação & Resposta Terapêutica": {
        "motivos": ["Duplicidade / Sem indicação de uso", "Medicamento inadequado à condição", "Omissão uso habitual / Condição não tratada", "Escolha em desacordo com protocolo", "Paciente com alergia", "Terapia sem resposta efetiva"],
        "sugestoes": ["Suspender/substituir medicamento", "Incluir terapia adicional", "Incluir medida não farmacológica", "Ajustar dose e/ou frequência"]
    },
    "Exames & Dispositivos": {
        "motivos": ["Ausência de monitoramento terapêutico", "Risco de infecção de cateter / Cateter infectado"],
        "sugestoes": ["Solicitar exame lab/imagem/cultura/nível sérico", "Remover/trocar cateter / Lockterapia"]
    },
    "Reação Adversa (RAM)": {
        "motivos": ["Risco de reação adversa a medicamento", "Reação adversa identificada"],
        "sugestoes": ["Ajustar tempo infusão/diluição", "Administrar pré-medicação/hidratação", "Suspender/substituir/incluir terapia"]
    },
    "Incompatibilidade & Interações": {
        "motivos": ["Incompatibilidade físico-química", "Interação Medicamentosa (Efetividade/Toxicidade)", "Interação Fármaco-Nutriente"],
        "sugestoes": ["Alterar aprazamento / vias diferentes", "Pausar, lavar via e administrar", "Administrar em jejum / Pausar dieta"]
    },
    "Gerenciamento de Antimicrobianos (Stewardship)": {
        "motivos": ["Tempo prolongado / Ausência de ficha ATM", "ATM desnecessário / Resistente (Antibiograma)", "Empírico inadequado / Sem cobertura", "Sem penetração no sítio infeccioso", "Espectro estreito ou amplo em cultura", "Ausência de profilaxia cirúrgica/clínica"],
        "sugestoes": ["Escalonar/Descalonar terapia", "Suspender/substituir medicamento", "Ajustar dose/frequência/incluir terapia", "Solicitar/renovar ficha de ATM"]
    },
    "Analgesia Multimodal": {
        "motivos": ["Ausência de manejo da dor / Sem resposta", "Risco de delirium e/ou abstinência", "Uso prolongado de analgosedação"],
        "sugestoes": ["Incluir terapia / medida não farmacológica", "Ajustar dose/frequência / Associar opção", "Iniciar desmame / rodízio / sedativo enteral"]
    }
}


def gerar_bloco_taxonomia_texto():
    """Gera a seção 2 (taxonomia) do prompt mestre a partir do dicionário,
    para que o texto enviado à API nunca fique dessincronizado das opções
    exibidas nos formulários."""
    linhas = []
    for i, (cat, dados) in enumerate(TAXONOMIA_INTERVENCOES.items(), start=1):
        linhas.append(f"{i}. {cat.upper()}")
        linhas.append(f"- Subcategorias: {' | '.join(dados['motivos'])}.")
        linhas.append(f"- Sugestões: {' | '.join(dados['sugestoes'])}.")
        linhas.append("")
    return "\n".join(linhas)


SYSTEM_INSTRUCTIONS = f"""Você é um assistente especializado em Farmácia Clínica Hospitalar, Cuidados Intensivos (UTI) e Acompanhamento Farmacoterapêutico sob a metodologia Pharmacotherapy Workup (PW).

Sua função é processar os dados cadastrados na ficha do paciente (clínicos, laboratoriais, infectológicos, reconciliação e intervenções) e gerar relatórios formais e evoluções clínicas padronizadas.

======================================================================
1. MÓDULOS DE SAÍDA / TIPOS DE EVOLUÇÃO
======================================================================

Conforme a solicitação do usuário, você gerará um dos dois tipos de registro abaixo:

--- TIPO A: EVOLUÇÃO DIÁRIA HOSPITALAR (UTI / INTERNAÇÃO) ---
Estrutura Obrigatória:

1. Evolução Clínica
- DEVE SER OBRIGATORIAMENTE UM TEXTO CORRIDO E COESO (sem bullet points ou listas).
- Integrar fluidamente os seguintes dados:
  * Hemodinâmica (usar estritamente o termo "estabilidade hemodinâmica" ou "instabilidade hemodinâmica" — JAMAIS usar inabilidade), valor da PAM, presença e dosagem de Drogas Vasoativas (DVA).
  * Suporte Respiratório (VM, VNI, CPAP, Cateter Nasal ou Ar Ambiente).
  * Status Neurológico e Sedação (Comatoso, Confortável ou Agitado), nível de sedação e sedativos/analgésicos em uso com dosagem.
  * Dieta (Enteral, Zero, Oral), Aceitação (Boa, Parcial), Náuseas/Vômitos (especificando número de episódios) e Padrão evacuatório.
  * Curva Térmica (Afebril ou Febre, Tmax, episódios nas últimas 24h).
  * Função Renal (Creatinina, Ureia) e perfil da Diurese.
  * Exames laboratoriais de destaque/alterados relevantes da rotina.
  * Antimicrobianos em uso atual (com dose e Dia de Tratamento - DTA).
  * Status das Profilaxias: TEV, LAMG e Úlcera de Córnea (destacando ativas ou ausentes).

2. Infectologia e Microbiologia
- Foco infeccioso e indicação (Uso Empírico ou Guiado por cultura).
- Histórico preciso de antimicrobianos anteriores e resultados microbiológicos/culturas com perfil de sensibilidade.

3. Interações Medicamentosas e Incompatibilidades
- Interações Medicamentosas: Informar se há Relevância Clínica (Sim/Não), descrever o impacto e o manejo.
- Incompatibilidades em Y: Informar se há Relevância Clínica (Sim/Não) e descrever a conduta de aprazamento/vias.

4. Oportunidades de Melhoria / Revisão da Farmacoterapia
- Apresentar e categorizar os problemas farmacoterapêuticos ou pontos de otimização identificados na terapia, correlacionando-os com a taxonomia institucional.

5. Conduta Farmacêutica & Intervenções Realizadas
- Detalhar as intervenções registradas no seguinte formato:
  * [Categoria] — [Descrição da Subcategoria]: [Intervenção Sugerida]
  * Status / Aceitabilidade: [Aceita e implementada | Aceita, porém não implementada | Não aceita com justificativa clínica | Não aceita sem justificativa clínica | Pendente de resposta]
  * Profissional Contatado: [Nome/Cargo] via [Canal: Presencial, Ramal, Sistema Eletrônico].
- Plano Terapêutico Definido: Parâmetros clínicos, laboratoriais e microbiológicos a monitorar nas próximas 24h.

--- TIPO B: EVOLUÇÃO DE RECONCILIAÇÃO MEDICAMENTOSA (ADMISSÃO / TRANSIÇÃO) ---
Estrutura Obrigatória:

1. Identificação e Fonte dos Dados
- Iniciais, idade, leito, data de admissão, número de registro hospitalar e origem da informação (Paciente, Acompanhante/Familiar, Receituário, Unidade Básica, Prontuário).

2. Comparativo da Farmacoterapia (Domiciliar vs. Hospitalar)
- Detalhamento do cruzamento entre os medicamentos prévios e a prescrição de admissão, classificando cada item em:
  * Mantido (mesma dose/posologia).
  * Mantido com Ajuste (alteração de dose, frequência ou via).
  * Suspenso Intencionalmente (com justificativa clínica explícita).
  * Substituído por Padronizado (troca por equivalente terapêutico do hospital).
  * Discrepância Não Justificada (omissão não intencional, divergência de dose/via sem motivo clínico).

3. Análise de Discrepâncias e Riscos
- Destaque claro e objetivo das Discrepâncias Não Justificadas encontradas e os potenciais riscos ao paciente.

4. Conduta Farmacêutica & Desfecho
- Intervenção realizada para correção de discrepâncias (categoria, status de aceitabilidade, profissional contatado e canal).
- Plano de acompanhamento inicial.

======================================================================
2. TAXONOMIA INSTITUCIONAL DE INTERVENÇÕES FARMACÊUTICAS
======================================================================
Sempre que analisar ou categorizar intervenções, utilize rigorosamente a estrutura abaixo:

{gerar_bloco_taxonomia_texto()}

======================================================================
3. REGRAS GERAIS DE LINGUAGEM E CONDUTA
======================================================================
- Mantenha tom estritamente técnico, formal e adequado a prontuários e registros multiprofissionais de saúde.
- NUNCA invente exames, dados clínicos, doses ou condutas que não foram fornecidos no input do usuário.
- Respeite rigorosamente a regra do texto corrido para a Seção 1 ("Evolução Clínica").
"""

# ==============================================================================
# CAMADA DE PERSISTÊNCIA (SQLITE)
# ==============================================================================

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intervencoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT, iniciais TEXT, registro TEXT, leito TEXT, setor TEXT,
            categoria TEXT, motivo TEXT, sugestao TEXT,
            aceitabilidade TEXT, profissional TEXT, canal TEXT, farmaceutico TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS paciente_dia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT, setor TEXT, quantidade INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evolucoes_geradas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT, tipo TEXT, iniciais TEXT, registro TEXT, texto TEXT
        )
    """)
    conn.commit()
    return conn


conn = get_conn()


def inserir_intervencao(row: dict):
    conn.execute(
        """INSERT INTO intervencoes
           (data, iniciais, registro, leito, setor, categoria, motivo, sugestao, aceitabilidade, profissional, canal, farmaceutico)
           VALUES (:data,:iniciais,:registro,:leito,:setor,:categoria,:motivo,:sugestao,:aceitabilidade,:profissional,:canal,:farmaceutico)""",
        row
    )
    conn.commit()


def carregar_intervencoes():
    return pd.read_sql_query("SELECT * FROM intervencoes ORDER BY id DESC", conn)


def atualizar_intervencoes(df: pd.DataFrame):
    df.to_sql("intervencoes", conn, if_exists="replace", index=False)
    conn.commit()


def inserir_paciente_dia(data, setor, quantidade):
    conn.execute(
        "INSERT INTO paciente_dia (data, setor, quantidade) VALUES (?,?,?)",
        (data, setor, quantidade)
    )
    conn.commit()


def carregar_paciente_dia():
    return pd.read_sql_query("SELECT * FROM paciente_dia ORDER BY data DESC", conn)


def salvar_evolucao_gerada(tipo, iniciais, registro, texto):
    conn.execute(
        "INSERT INTO evolucoes_geradas (data, tipo, iniciais, registro, texto) VALUES (?,?,?,?,?)",
        (datetime.date.today().isoformat(), tipo, iniciais, registro, texto)
    )
    conn.commit()


# ==============================================================================
# CHAMADA À API DA ANTHROPIC (CLAUDE)
# ==============================================================================

def gerar_texto_claude(api_key: str, model: str, prompt_usuario: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    resposta = client.messages.create(
        model=model,
        max_tokens=3000,
        system=SYSTEM_INSTRUCTIONS,
        messages=[{"role": "user", "content": prompt_usuario}]
    )
    partes = [bloco.text for bloco in resposta.content if bloco.type == "text"]
    return "\n".join(partes)


# ==============================================================================
# PAINEL LATERAL
# ==============================================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("Cole sua Anthropic API Key:", type="password")
    modelo = st.selectbox(
        "Modelo:",
        ["claude-sonnet-5", "claude-opus-4-8", "claude-haiku-4-5-20251001"],
        index=0
    )

    st.markdown("---")
    st.subheader("👤 Dados do Farmacêutico")
    nome_farm = st.text_input("Nome do Farmacêutico(a):")
    crf_farm = st.text_input("CRF nº:")

    st.markdown("---")
    st.subheader("📊 Central de Indicadores")
    df_interv_sidebar = carregar_intervencoes()
    st.write(f"Total registrado (histórico): **{len(df_interv_sidebar)}**")

    if not df_interv_sidebar.empty:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_interv_sidebar.to_excel(writer, sheet_name="Intervenções", index=False)
            carregar_paciente_dia().to_excel(writer, sheet_name="Paciente-dia", index=False)
        st.download_button(
            "📥 Exportar Excel (Intervenções + Paciente-dia)",
            data=excel_buffer.getvalue(),
            file_name=f"indicadores_farmacia_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Nenhuma intervenção registrada ainda.")

    st.markdown("---")
    st.subheader("💾 Backup do Banco de Dados")
    try:
        with open(DB_PATH, "rb") as f:
            st.download_button(
                "⬇️ Baixar backup (.db)",
                data=f.read(),
                file_name=f"farmacia_clinica_backup_{datetime.date.today()}.db",
                mime="application/octet-stream"
            )
    except FileNotFoundError:
        pass

    restaurar = st.file_uploader("⬆️ Restaurar backup (.db)", type=["db"])
    if restaurar is not None:
        with open(DB_PATH, "wb") as f:
            f.write(restaurar.read())
        st.success("Backup restaurado! Recarregue a página.")
        st.cache_data.clear()

# ==============================================================================
# ABAS DO APLICATIVO
# ==============================================================================
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "🏥 Evolução Diária UTI",
    "🔄 Reconciliação Medicamentosa",
    "🛠️ Registrar / Editar Intervenção",
    "📅 Paciente-dia",
    "📈 Dashboard & Indicadores"
])

# ------------------------------------------------------------------------------
# ABA 1: EVOLUÇÃO DIÁRIA UTI
# ------------------------------------------------------------------------------
with aba1:
    st.header("Ficha de Acompanhamento Diário - UTI / Internação")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        iniciais = st.text_input("Iniciais do Paciente:", value="A.B.C.")
    with col2:
        registro = st.text_input("Nº do Registro / Prontuário:", value="123456")
    with col3:
        leito = st.text_input("Leito:", value="UTI - 05")
    with col4:
        idade = st.text_input("Idade:", value="68 anos")

    setor_evolucao = st.selectbox("Setor:", SETORES_HPMAF, key="setor_ev1")

    st.subheader("1. Estado Clínico & Sinais Vitais")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        hemodinamica = st.radio("Hemodinâmica:", ["Estável", "Instável"])
        pam = st.text_input("PAM (mmHg):", "65")
        dva = st.text_input("DVA / Dose:", "Noradrenalina 0.1 mcg/kg/min")
    with c2:
        neurologico = st.selectbox("Neurológico:", ["Confortável", "Comatoso", "Agitado"])
        sedativo = st.text_input("Sedativo / Analgésico e Dose:", "Fentanil 2 mL/h e Propofol 5 mL/h")
        resp = st.selectbox("Suporte Ventilatório:", ["VM", "VNI", "CPAP", "Cateter Nasal", "Ar Ambiente"])
    with c3:
        curva_term = st.selectbox("Curva Térmica:", ["Afebril", "Febre"])
        tmax = st.text_input("Tmax (°C):", "38.2")
        ep_febre = st.text_input("Nº Episódios de Febre:", "2")
    with c4:
        dieta = st.selectbox("Dieta:", ["Enteral", "Zero", "Oral"])
        aceitacao = st.selectbox("Aceitação:", ["Boa", "Parcial", "N/A"])
        emese = st.text_input("Náuseas/Vômitos (nº episódios):", "0")
        evacuacao = st.text_input("Padrão Evacuatório:", "Ausente há 48h")

    st.subheader("2. Laboratório, Função Renal & Profilaxias")
    l1, l2, l3 = st.columns(3)
    with l1:
        cr = st.text_input("Creatinina (mg/dL):", "1.9")
        ur = st.text_input("Ureia (mg/dL):", "85")
        diurese = st.text_input("Diurese:", "Preservada (1.1 mL/kg/h)")
    with l2:
        exames_destaque = st.text_area("Exames Alterados / Destaques da Rotina:", "Leucócitos: 16.500 | PCR: 145 | Na: 138 | K: 4.2")
    with l3:
        tev = st.text_input("Profilaxia TEV:", "Enoxaparina 40mg SC 1x/dia (Ativa)")
        lamg = st.text_input("Profilaxia LAMG:", "Omeprazol 40mg IV 1x/dia (Ativa)")
        cornea = st.text_input("Profilaxia Úlcera de Córnea:", "Vidisic Gel 12/12h (Ativa)")

    st.subheader("3. Infectologia & Antimicrobianos")
    i1, i2 = st.columns(2)
    with i1:
        foco = st.text_input("Foco Infeccioso:", "Pulmonar (PAV)")
        carater = st.radio("Caráter do Uso:", ["Empírico", "Guiado"])
        atb_atual = st.text_input("ATB Atual / Dose / DTA:", "Meropenem 1g IV 8/8h (DTA 4)")
    with i2:
        hist_atb_culturas = st.text_area("Histórico Preciso de ATB & Culturas:", "Uso prévio de Ceftriaxona por 3 dias. Aspirado traqueal isolou Pseudomonas aeruginosa sensível a Meropenem.")

    st.subheader("4. Interações & Incompatibilidades")
    k1, k2 = st.columns(2)
    with k1:
        interacoes = st.text_area("Interações Medicamentosas (Relevância / Descrição):", "Relevância SIM: Vancomicina + Meropenem (Acompanhar função renal).")
    with k2:
        incompatib = st.text_area("Incompatibilidades em Y (Relevância / Descrição):", "Relevância NÃO: Vias dedicadas e aprazamento ajustado.")

    st.subheader("5. Oportunidades & Conduta")
    o1, o2 = st.columns(2)
    with o1:
        oportunidades = st.text_area("Oportunidades de Melhoria / Revisão:", "Necessidade de ajuste de dose de Vancomicina para função renal atual (Cr 1.9).")
    with o2:
        conduta_plano = st.text_area("Conduta Farmacêutica & Plano Terapêutico:", "Ajustada Vancomicina para 1g 24/24h. Solicitada vancocinemia pré-quarta dose.")

    st.markdown("---")
    if st.button("🚀 Gerar Evolução Diária da UTI", type="primary"):
        if not api_key:
            st.error("Por favor, informe sua Anthropic API Key no painel lateral!")
        else:
            prompt_input = f"""
            POR FAVOR, GERE UMA EVOLUÇÃO DIÁRIA HOSPITALAR (TIPO A) COM OS SEGUINTES DADOS:

            DADOS DO PACIENTE:
            Iniciais: {iniciais} | Registro: {registro} | Leito: {leito} | Setor: {setor_evolucao} | Idade: {idade}

            CLÍNICO E SINAIS VITAIS:
            - Hemodinâmica: {hemodinamica} | PAM: {pam} mmHg | DVA: {dva}
            - Neurológico: {neurologico} | Sedativo: {sedativo} | Suporte: {resp}
            - Térmico: {curva_term} (Tmax: {tmax} °C | Episódios: {ep_febre})
            - Dieta: {dieta} | Aceitação: {aceitacao} | Emese: {emese} episódios | Evacuação: {evacuacao}

            LABORATÓRIO, RENAL E PROFILAXIAS:
            - Renal: Cr {cr} | Ur {ur} | Diurese: {diurese}
            - Exames Destaque: {exames_destaque}
            - Profilaxias: TEV ({tev}) | LAMG ({lamg}) | Córnea ({cornea})

            INFECTOLOGIA:
            - Foco: {foco} ({carater})
            - ATB Atual: {atb_atual}
            - Histórico/Culturas: {hist_atb_culturas}

            INTERAÇÕES E INCOMPATIBILIDADES:
            - Interações: {interacoes}
            - Incompatibilidades Y: {incompatib}

            OPORTUNIDADES E CONDUTA:
            - Oportunidades: {oportunidades}
            - Conduta/Plano: {conduta_plano}
            """
            try:
                with st.spinner("Gerando evolução..."):
                    texto = gerar_texto_claude(api_key, modelo, prompt_input)
                st.success("Evolução Gerada com Sucesso!")
                st.text_area("Texto da Evolução (Copie para o Prontuário):", value=texto, height=400)
                salvar_evolucao_gerada("Tipo A - Evolução Diária", iniciais, registro, texto)
            except Exception as e:
                st.error(f"Erro ao conectar com a API: {e}")

# ------------------------------------------------------------------------------
# ABA 2: RECONCILIAÇÃO MEDICAMENTOSA
# ------------------------------------------------------------------------------
with aba2:
    st.header("Reconciliação Medicamentosa de Admissão / Transição")

    r_c1, r_c2, r_c3 = st.columns(3)
    with r_c1:
        rec_iniciais = st.text_input("Iniciais Paciente (Rec):", "M.J.S.")
        rec_registro = st.text_input("Prontuário (Rec):", "987654")
    with r_c2:
        rec_leito = st.text_input("Leito (Rec):", "Enf 302")
        rec_idade = st.text_input("Idade (Rec):", "72 anos")
    with r_c3:
        rec_fonte = st.selectbox("Fonte dos Dados:", ["Paciente", "Acompanhante/Familiar", "Receituário Médico", "Prontuário Anterior", "Unidade Básica"])

    st.subheader("Comparativo de Medicamentos Domiciliares vs. Hospitalares")
    rec_meds = st.text_area(
        "Liste os Medicamentos Domiciliares e o Status na Prescrição Hospitalar:",
        value="1. Losartana 50mg 12/12h -> Suspenso Intencionalmente (PA baixa na admissão)\n"
              "2. Metformina 850mg 2x/dia -> Suspenso Intencionalmente (Jejum)\n"
              "3. Levotiroxina 88mcg/dia -> Discrepância Não Justificada (Omitido na prescrição)\n"
              "4. Atorvastatina 20mg/dia -> Substituído por Padronizado (Simvastatina 20mg/dia)",
        height=150
    )

    rec_discrepancias = st.text_area("Análise de Discrepâncias & Riscos:", "Omissão involuntária de Levotiroxina para hipotireoidismo de uso contínuo.")
    rec_conduta = st.text_area("Conduta Farmacêutica & Desfecho:", "Solicitada inclusão da Levotiroxina 88mcg VO em jejum ao médico plantonista. Intervenção Aceita.")

    if st.button("🚀 Gerar Evolução de Reconciliação", type="primary"):
        if not api_key:
            st.error("Por favor, informe sua Anthropic API Key no painel lateral!")
        else:
            prompt_rec = f"""
            POR FAVOR, GERE UMA EVOLUÇÃO DE RECONCILIAÇÃO MEDICAMENTOSA (TIPO B) COM OS DADOS:

            DADOS:
            Iniciais: {rec_iniciais} | Registro: {rec_registro} | Leito: {rec_leito} | Idade: {rec_idade}
            Fonte das Informações: {rec_fonte}

            COMPARATIVO:
            {rec_meds}

            DISCREPÂNCIAS:
            {rec_discrepancias}

            CONDUTA E DESFECHO:
            {rec_conduta}
            """
            try:
                with st.spinner("Gerando reconciliação..."):
                    texto = gerar_texto_claude(api_key, modelo, prompt_rec)
                st.success("Reconciliação Gerada com Sucesso!")
                st.text_area("Texto da Reconciliação:", value=texto, height=350)
                salvar_evolucao_gerada("Tipo B - Reconciliação", rec_iniciais, rec_registro, texto)
            except Exception as e:
                st.error(f"Erro ao conectar com a API: {e}")

# ------------------------------------------------------------------------------
# ABA 3: REGISTRO E EDIÇÃO DE INTERVENÇÕES (TAXONOMIA) — PERSISTENTE EM SQLITE
# ------------------------------------------------------------------------------
with aba3:
    st.header("Cadastro e Acompanhamento de Intervenções")
    st.markdown("Cadastre a intervenção no momento do achado e **atualize a aceitabilidade** quando obtiver a resposta da equipe. Os dados ficam salvos no banco local, sobrevivendo a reinícios do app.")

    with st.form("form_intervencao"):
        fi_c1, fi_c2, fi_c3 = st.columns(3)
        with fi_c1:
            int_iniciais = st.text_input("Iniciais Paciente:", "A.B.C.")
            int_registro = st.text_input("Nº Registro:", "123456")
            int_leito = st.text_input("Leito:", "UTI - 05")
            int_setor = st.selectbox("Setor:", SETORES_HPMAF, key="setor_interv")

        with fi_c2:
            categoria_sel = st.selectbox("Categoria Mãe:", list(TAXONOMIA_INTERVENCOES.keys()))
            motivo_sel = st.selectbox("Motivo / Subcategoria:", TAXONOMIA_INTERVENCOES[categoria_sel]["motivos"])
            sugestao_sel = st.selectbox("Intervenção Sugerida:", TAXONOMIA_INTERVENCOES[categoria_sel]["sugestoes"])

        with fi_c3:
            aceitabilidade_sel = st.selectbox("Status / Aceitabilidade:", [
                "Pendente de resposta",
                "Aceita e implementada",
                "Aceita, porém não implementada",
                "Não aceita com justificativa clínica",
                "Não aceita sem justificativa clínica"
            ])
            profissional_sel = st.selectbox("Profissional Contatado:", ["Médico", "Residente", "Enfermeiro", "Técnico de Enfermagem", "Fisioterapeuta", "Outro"])
            canal_sel = st.selectbox("Canal de Comunicação:", ["Presencial / Visita", "Telefone / Ramal", "Sistema Eletrônico"])

        btn_salvar = st.form_submit_button("💾 Salvar Intervenção no Banco de Dados")

        if btn_salvar:
            nova_linha = {
                "data": datetime.date.today().strftime("%d/%m/%Y"),
                "iniciais": int_iniciais,
                "registro": int_registro,
                "leito": int_leito,
                "setor": int_setor,
                "categoria": categoria_sel,
                "motivo": motivo_sel,
                "sugestao": sugestao_sel,
                "aceitabilidade": aceitabilidade_sel,
                "profissional": profissional_sel,
                "canal": canal_sel,
                "farmaceutico": nome_farm if nome_farm else "Não informado"
            }
            inserir_intervencao(nova_linha)
            st.success("Intervenção registrada com sucesso no banco de dados!")

    st.markdown("---")
    st.subheader("📋 Intervenções Registradas (Edição Rápida)")

    df_interv = carregar_intervencoes()
    if not df_interv.empty:
        df_editado = st.data_editor(df_interv, num_rows="dynamic", key="editor_intervencoes")
        if st.button("💾 Salvar alterações da tabela"):
            atualizar_intervencoes(df_editado)
            st.success("Alterações salvas no banco de dados!")
    else:
        st.info("Nenhuma intervenção cadastrada no momento.")

# ------------------------------------------------------------------------------
# ABA 4: PACIENTE-DIA (DENOMINADOR DOS INDICADORES)
# ------------------------------------------------------------------------------
with aba4:
    st.header("📅 Registro de Paciente-dia por Setor")
    st.markdown("Use esta aba para lançar o censo diário (paciente-dia) de cada setor. Esse valor é o **denominador** usado nos indicadores da aba seguinte.")

    with st.form("form_paciente_dia"):
        pd_c1, pd_c2, pd_c3 = st.columns(3)
        with pd_c1:
            pd_data = st.date_input("Data:", datetime.date.today())
        with pd_c2:
            pd_setor = st.selectbox("Setor:", SETORES_HPMAF, key="setor_pd")
        with pd_c3:
            pd_qtd = st.number_input("Nº de pacientes-dia:", min_value=0, step=1, value=0)

        btn_pd = st.form_submit_button("💾 Registrar Paciente-dia")
        if btn_pd:
            inserir_paciente_dia(pd_data.strftime("%d/%m/%Y"), pd_setor, int(pd_qtd))
            st.success("Paciente-dia registrado!")

    st.markdown("---")
    st.subheader("Histórico de Paciente-dia")
    df_pd = carregar_paciente_dia()
    if not df_pd.empty:
        st.dataframe(df_pd, use_container_width=True)
        total_pd = df_pd["quantidade"].sum()
        st.metric("Total de Paciente-dia Acumulado", int(total_pd))
    else:
        st.info("Nenhum registro de paciente-dia ainda.")

# ------------------------------------------------------------------------------
# ABA 5: DASHBOARD & INDICADORES
# ------------------------------------------------------------------------------
with aba5:
    st.header("📈 Indicadores da Farmácia Clínica")

    df = carregar_intervencoes()
    df_pd_dash = carregar_paciente_dia()

    if df.empty:
        st.warning("Cadastre intervenções na Aba 3 para visualizar os gráficos e indicadores.")
    else:
        total_pd_dash = int(df_pd_dash["quantidade"].sum()) if not df_pd_dash.empty else 0

        total = len(df)
        aceitas = len(df[df["aceitabilidade"].str.contains("Aceita", na=False)])
        taxa_aceitacao = (aceitas / total * 100) if total > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total de Intervenções", total)
        m2.metric("Intervenções Aceitas", aceitas)
        m3.metric("Taxa de Aceitabilidade", f"{taxa_aceitacao:.1f}%")

        if total_pd_dash > 0:
            multiplicador = st.selectbox("Base do indicador (por X paciente-dia):", [100, 1000], index=1)
            taxa_pd = (total / total_pd_dash) * multiplicador
            m4.metric(f"Intervenções / {multiplicador} paciente-dia", f"{taxa_pd:.2f}")
        else:
            m4.metric("Paciente-dia registrado", "0")
            st.info("Registre o paciente-dia na Aba 4 para calcular a taxa de intervenções por paciente-dia.")

        st.markdown("---")
        d_col1, d_col2 = st.columns(2)

        with d_col1:
            st.subheader("Intervenções por Categoria")
            cat_counts = df["categoria"].value_counts()
            st.bar_chart(cat_counts)

        with d_col2:
            st.subheader("Distribuição por Status de Aceitabilidade")
            aceit_counts = df["aceitabilidade"].value_counts()
            st.bar_chart(aceit_counts)

        st.markdown("---")
        st.subheader("Intervenções por Setor")
        if "setor" in df.columns:
            setor_counts = df["setor"].value_counts()
            st.bar_chart(setor_counts)

        st.markdown("---")
        st.subheader("Filtrar e explorar dados brutos")
        setores_disponiveis = df["setor"].dropna().unique().tolist() if "setor" in df.columns else []
        filtro_setor = st.multiselect("Filtrar por setor:", setores_disponiveis, default=setores_disponiveis)
        df_filtrado = df[df["setor"].isin(filtro_setor)] if filtro_setor else df
        st.dataframe(df_filtrado, use_container_width=True)
