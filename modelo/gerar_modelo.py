"""Gera o modelo semântico (TMDL) do estudo de exoplanetas a partir de uma especificação simples.

Uso: python gerar_modelo.py <pasta_do_projeto>
Os lineageTags são derivados do nome do objeto (uuid5), então rodar de novo não muda nada à toa.
"""
import json
import sys
import uuid
from pathlib import Path

RAIZ = Path(sys.argv[1])
MODELO = RAIZ / "Exoplanetas.SemanticModel"
DEF = MODELO / "definition"
NS = uuid.UUID("5b0e3a52-7c1d-4a8e-9a43-0e5f2c1d9b77")


def tag(*partes):
    return str(uuid.uuid5(NS, "/".join(partes)))


def q(nome):
    return f"'{nome}'" if any(c in nome for c in " ()/-ªç%ãéí") else nome


# tabela -> (arquivo csv, [(coluna csv, nome no modelo, tipo M, dataType, formatString, oculta)], passos M extras, colunas extras)
TABELAS = {
    "Estrelas": ("estrelas.csv", [
        ("estrela_id", "estrela_id", "Int64.Type", "int64", "0", True),
        ("estrela", "Estrela", "type text", "string", None, False),
        ("alvo_mast", "Alvo no arquivo da NASA", "type text", "string", None, False),
        ("status_nasa", "Status NASA", "type text", "string", None, False),
        ("fonte_dados", "Fonte dos dados", "type text", "string", None, False),
        ("setores", "Setores TESS", "type text", "string", None, False),
        ("dias_observados", "Dias observados", "type number", "double", "0.0", False),
        ("pontos", "Pontos medidos", "Int64.Type", "int64", "#,0", False),
        ("pontos_defeito", "Pontos com defeito", "Int64.Type", "int64", "#,0", False),
        ("periodo_1a_rodada_dias", "Período 1ª rodada (dias)", "type number", "double", "0.0000", False),
        ("queda_1a_rodada_ppm", "Queda 1ª rodada (ppm)", "type number", "double", "#,0", False),
        ("periodo_achado_dias", "Período achado (dias)", "type number", "double", "0.0000", False),
        ("periodo_nasa_dias", "Período NASA (dias)", "type number", "double", "0.0000", False),
        ("duracao_achada_h", "Duração achada (h)", "type number", "double", "0.0", False),
        ("duracao_nasa_h", "Duração NASA (h)", "type number", "double", "0.0", False),
        ("queda_achada_ppm", "Queda achada (ppm)", "type number", "double", "#,0", False),
        ("queda_nasa_ppm", "Queda NASA (ppm)", "type number", "double", "#,0", False),
        ("sinal_ruido", "Sinal/ruído", "type number", "double", "0.0", False),
    ], ['StatusEN = Table.AddColumn(Tipos, "Status NASA (EN)", each if [Status NASA] = "Confirmado" then "Confirmed" else "Candidate", type text)'],
        [("Status NASA (EN)", "string", None)]),
    "Curva bruta": ("curva_bruta.csv", [
        ("estrela_id", "estrela_id", "Int64.Type", "int64", "0", True),
        ("dia", "Dia", "type number", "double", "0.0", False),
        ("brilho", "Brilho", "type number", "double", "0.000", False),
        ("defeito", "Defeito", "type logical", "boolean", None, True),
    ], ['Indice = Table.AddIndexColumn(Tipos, "Ponto", 1, 1, Int64.Type)',
        'Qualidade = Table.AddColumn(Indice, "Qualidade", each if [Defeito] then "Defeito do telescópio" else "Ponto bom", type text)',
        'QualidadeEN = Table.AddColumn(Qualidade, "Qualidade (EN)", each if [Defeito] then "Telescope glitch" else "Good point", type text)'],
        [("Ponto", "int64", "0"), ("Qualidade", "string", None), ("Qualidade (EN)", "string", None)]),
    "Curva sobreposta": ("curva_sobreposta.csv", [
        ("estrela_id", "estrela_id", "Int64.Type", "int64", "0", True),
        ("tipo", "Tipo", "type text", "string", None, False),
        ("horas", "Horas do meio da passagem", "type number", "double", "0.0", False),
        ("brilho", "Brilho", "type number", "double", "0.000", False),
    ], ['Indice = Table.AddIndexColumn(Tipos, "Ponto", 1, 1, Int64.Type)',
        'TipoEN = Table.AddColumn(Indice, "Tipo (EN)", each if [Tipo] = "Medição" then "Measurement" else "Average every ~15 min", type text)'],
        [("Ponto", "int64", "0"), ("Tipo (EN)", "string", None)]),
    "Busca do período": ("busca_periodo.csv", [
        ("estrela_id", "estrela_id", "Int64.Type", "int64", "0", True),
        ("rodada", "Rodada", "type text", "string", None, False),
        ("periodo_dias", "Período testado (dias)", "type number", "double", "0.00", False),
        ("potencia_rel", "Força do sinal", "type number", "double", "0.00", False),
    ], [], []),
    "Candidatos NASA": ("candidatos_nasa.csv", [
        ("toi", "TOI", "type number", "double", "0.00", False),
        ("tic", "TIC", "Int64.Type", "int64", "0", False),
        ("status", "Status", "type text", "string", None, False),
        ("periodo_dias", "Período (dias)", "type number", "double", "0.00", False),
        ("duracao_h", "Duração (h)", "type number", "double", "0.0", False),
        ("queda_ppm", "Queda (ppm)", "type number", "double", "#,0", False),
        ("raio_terras", "Raio (Terras)", "type number", "double", "0.0", False),
        ("magnitude_tess", "Magnitude TESS", "type number", "double", "0.0", False),
        ("data_criacao", "Data de entrada na lista", "type date", "dateTime", "dd/mm/yyyy", False),
        ("testado_por_mim", "Testado por mim", "type logical", "boolean", None, True),
    ], ['Destaque = Table.AddColumn(Tipos, "Destaque", each if [Testado por mim] then "Testado neste estudo" else "Outros candidatos", type text)',
        'DestaqueEN = Table.AddColumn(Destaque, "Destaque (EN)", each if [Testado por mim] then "Tested in this study" else "Other candidates", type text)',
        'StatusEN = Table.AddColumn(DestaqueEN, "Status (EN)", each Record.FieldOrDefault([Candidate = "Candidate", #"Candidato ambíguo" = "Ambiguous candidate", Confirmado = "Confirmed", #"Já conhecido" = "Known planet", #"Falso positivo" = "False positive", #"Alarme falso" = "False alarm"], [Status], "Unclassified"), type text)',
        'Ano = Table.AddColumn(StatusEN, "Ano de entrada", each Date.Year([Data de entrada na lista]), Int64.Type)'],
        [("Destaque", "string", None), ("Destaque (EN)", "string", None), ("Status (EN)", "string", None),
         ("Ano de entrada", "int64", "0")]),
}

# o registro de tradução do status precisa da chave em português
TABELAS["Candidatos NASA"][2][2] = TABELAS["Candidatos NASA"][2][2].replace("[Candidate =", "[Candidato =")

DIF = "ABS ( Estrelas[Período achado (dias)] - Estrelas[Período NASA (dias)] )"
MEDIDAS = {
    "Estrelas": [
        ("Estrelas testadas", "COUNTROWS ( Estrelas )", "0", "Resultado"),
        ("Períodos que batem", f"COUNTROWS ( FILTER ( Estrelas, DIVIDE ( {DIF}, Estrelas[Período NASA (dias)] ) < 0.01 ) )", "0", "Resultado"),
        ("Períodos que batem (texto)", 'FORMAT ( [Períodos que batem], "0" ) & " de " & FORMAT ( [Estrelas testadas], "0" )', None, "Resultado"),
        ("Períodos que batem (texto EN)", 'FORMAT ( [Períodos que batem], "0" ) & " of " & FORMAT ( [Estrelas testadas], "0" )', None, "Resultado"),
        ("Diferença no período (min)", f"SUMX ( Estrelas, {DIF} ) * 24 * 60", "0.0", "Resultado"),
        ("Maior diferença no período (min)", f"MAXX ( Estrelas, {DIF} ) * 24 * 60", "0", "Resultado"),
        ("Período achado", "AVERAGE ( Estrelas[Período achado (dias)] )", "0.0000", "Resultado"),
        ("Período NASA", "AVERAGE ( Estrelas[Período NASA (dias)] )", "0.0000", "Resultado"),
        ("Duração achada", "AVERAGE ( Estrelas[Duração achada (h)] )", "0.0", "Resultado"),
        ("Queda achada", "AVERAGE ( Estrelas[Queda achada (ppm)] ) / 1000000", "0.00%", "Resultado"),
        ("Queda NASA", "AVERAGE ( Estrelas[Queda NASA (ppm)] ) / 1000000", "0.00%", "Resultado"),
        ("Menor queda achada", "MIN ( Estrelas[Queda achada (ppm)] ) / 1000000", "0.00%", "Resultado"),
        ("Sinal/ruído médio", "AVERAGE ( Estrelas[Sinal/ruído] )", "0", "Resultado"),
        ("Período 1ª rodada", "AVERAGE ( Estrelas[Período 1ª rodada (dias)] )", "0.00", "Primeira rodada"),
        ("Queda 1ª rodada", "AVERAGE ( Estrelas[Queda 1ª rodada (ppm)] ) / 1000000", "0.00%", "Primeira rodada"),
        ("Pontos com defeito (%)", "DIVIDE ( SUM ( Estrelas[Pontos com defeito] ), SUM ( Estrelas[Pontos medidos] ) )", "0.0%", "Primeira rodada"),
    ],
    "Curva bruta": [
        ("Dia (eixo)", "AVERAGE ( 'Curva bruta'[Dia] )", "0.0", None),
        ("Brilho bruto", "AVERAGE ( 'Curva bruta'[Brilho] )", "0.000", None),
        ("Cor do ponto bruto", "IF ( SELECTEDVALUE ( 'Curva bruta'[Defeito] ) = TRUE (), \"#F87171\", \"#4FD1C5\" )", None, "Cores"),
    ],
    "Curva sobreposta": [
        ("Horas (eixo)", "AVERAGE ( 'Curva sobreposta'[Horas do meio da passagem] )", "0.0", None),
        ("Brilho sobreposto", "AVERAGE ( 'Curva sobreposta'[Brilho] )", "0.000", None),
        ("Cor do ponto sobreposto", "IF ( SELECTEDVALUE ( 'Curva sobreposta'[Tipo] ) = \"Medição\", \"#4A6A90\", \"#4FD1C5\" )", None, "Cores"),
    ],
    "Busca do período": [
        ("Força 1ª rodada", "CALCULATE ( MAX ( 'Busca do período'[Força do sinal] ), KEEPFILTERS ( 'Busca do período'[Rodada] = \"1ª rodada (sem limpeza)\" ) )", "0.00", None),
        ("Força final", "CALCULATE ( MAX ( 'Busca do período'[Força do sinal] ), KEEPFILTERS ( 'Busca do período'[Rodada] = \"Final (com limpeza)\" ) )", "0.00", None),
    ],
    "Candidatos NASA": [
        ("TOIs na lista", "COUNTROWS ( 'Candidatos NASA' )", "#,0", None),
        ("Candidatos aguardando", "CALCULATE ( COUNTROWS ( 'Candidatos NASA' ), 'Candidatos NASA'[Status] = \"Candidato\" )", "#,0", None),
        ("Confirmados", "CALCULATE ( COUNTROWS ( 'Candidatos NASA' ), 'Candidatos NASA'[Status] = \"Confirmado\" )", "#,0", None),
        ("Falsos positivos", "CALCULATE ( COUNTROWS ( 'Candidatos NASA' ), 'Candidatos NASA'[Status] IN { \"Falso positivo\", \"Alarme falso\" } )", "#,0", None),
        ("Período médio (dias)", "AVERAGE ( 'Candidatos NASA'[Período (dias)] )", "0.00", None),
        ("Queda média (ppm)", "AVERAGE ( 'Candidatos NASA'[Queda (ppm)] )", "#,0", None),
        ("Cor do candidato", "IF ( SELECTEDVALUE ( 'Candidatos NASA'[Testado por mim] ) = TRUE (), \"#F6AD55\", \"#4A6A90\" )", None, "Cores"),
        ("Tamanho do candidato", "IF ( SELECTEDVALUE ( 'Candidatos NASA'[Testado por mim] ) = TRUE (), 4, 1 )", "0", "Cores"),
    ],
}

DESCRICOES = {
    "Estrelas": "Uma linha por estrela testada: o que o teste achou e o valor oficial da NASA.",
    "Curva bruta": "Brilho da estrela ao longo do tempo (médias de 10 min; defeitos ponto a ponto).",
    "Curva sobreposta": "Todas as passagens do planeta sobrepostas no período achado, em horas a partir do meio da passagem.",
    "Busca do período": "Força do sinal para cada período testado (Box Least Squares), antes e depois da limpeza.",
    "Candidatos NASA": "Lista completa de TOIs (TESS Objects of Interest) com o status atual na NASA.",
}


def coluna(t, nome, tipo, fmt, oculta, fonte=True):
    linhas = [f"\tcolumn {q(nome)}", f"\t\tdataType: {tipo}"]
    if fmt:
        linhas.append(f"\t\tformatString: {fmt}")
    if oculta:
        linhas.append("\t\tisHidden")
    linhas += [f"\t\tlineageTag: {tag(t, nome)}",
               f"\t\tsummarizeBy: none", f"\t\tsourceColumn: {nome}", ""]
    if tipo == "dateTime":
        linhas.insert(-1, "\t\tannotation UnderlyingDateTimeDataType = Date\n")
    return "\n".join(linhas)


def tabela(t):
    csv, cols, passos, extras = TABELAS[t]
    out = [f"/// {DESCRICOES[t]}", f"table {q(t)}", f"\tlineageTag: {tag(t)}", ""]
    for m, fmt_dax, fmt, pasta in MEDIDAS.get(t, []):
        out.append(f"\tmeasure {q(m)} = {fmt_dax}")
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        if pasta:
            out.append(f"\t\tdisplayFolder: {pasta}")
        out += [f"\t\tlineageTag: {tag(t, 'm', m)}", ""]
    for _, nome, _, tipo, fmt, oculta in cols:
        out.append(coluna(t, nome, tipo, fmt, oculta))
    for nome, tipo, fmt in extras:
        out.append(coluna(t, nome, tipo, fmt, False))
    renomes = ", ".join(f'{{"{c}", "{n}"}}' for c, n, *_ in cols if c != n)
    tipos = ", ".join(f'{{"{n}", {m}}}' for _, n, m, *_ in cols)
    ultimo = "Tipos" if not passos else passos[-1].split(" = ")[0]
    m = [
        "let",
        f'    Fonte = Csv.Document(File.Contents(CaminhoDados & "{csv}"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Cabecalhos = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),",
        f"    Nomes = Table.RenameColumns(Cabecalhos, {{{renomes}}}),",
        f'    Tipos = Table.TransformColumnTypes(Nomes, {{{tipos}}}, "en-US")' + ("," if passos else ""),
    ]
    for i, p in enumerate(passos):
        m.append(f"    {p}" + ("," if i < len(passos) - 1 else ""))
    m += ["in", f"    {ultimo}"]
    out.append(f"\tpartition {q(t)} = m\n\t\tmode: import\n\t\tsource =")
    out += [f"\t\t\t\t{l}" for l in m]
    out += ["", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(out)


(DEF / "tables").mkdir(parents=True, exist_ok=True)
for t in TABELAS:
    (DEF / "tables" / f"{t}.tmdl").write_text(tabela(t), encoding="utf-8")

(DEF / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1606\n\n", encoding="utf-8")
refs = "\n".join(f"ref table {q(t)}" for t in TABELAS)
ordem = json.dumps(list(TABELAS) + ["CaminhoDados"], ensure_ascii=False)
(DEF / "model.tmdl").write_text(f"""model Model
	culture: pt-BR
	defaultPowerBIDataSourceVersion: powerBI_V3
	sourceQueryCulture: pt-BR
	discourageImplicitMeasures
	dataAccessOptions
		legacyRedirects
		returnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 0

annotation PBI_QueryOrder = {ordem}

{refs}

""", encoding="utf-8")

pasta_dados = str((RAIZ / "dados").resolve()) + "\\"
(DEF / "expressions.tmdl").write_text(f"""/// Pasta onde estão os CSVs gerados por dados/gerar_dados.py
expression CaminhoDados = "{pasta_dados}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
	lineageTag: {tag('CaminhoDados')}

	annotation PBI_ResultType = Text

""", encoding="utf-8")

rels = []
for t in ("Curva bruta", "Curva sobreposta", "Busca do período"):
    rels.append(f"relationship {tag('rel', t)}\n\tfromColumn: {q(t)}.estrela_id\n\ttoColumn: Estrelas.estrela_id\n")
(DEF / "relationships.tmdl").write_text("\n".join(rels), encoding="utf-8")

(MODELO / "definition.pbism").write_text(json.dumps({
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
(MODELO / ".platform").write_text(json.dumps({
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
    "metadata": {"type": "SemanticModel", "displayName": "Exoplanetas"},
    "config": {"version": "2.0", "logicalId": tag("logicalId")}}, indent=2), encoding="utf-8")
print("ok:", ", ".join(TABELAS))
