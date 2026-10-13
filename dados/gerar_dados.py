"""Gera os CSVs do dashboard a partir dos dados públicos do TESS (NASA).

Para cada estrela: baixa a curva de luz, marca os defeitos do instrumento, procura
o período das quedas de brilho (Box Least Squares) antes e depois da limpeza e
compara com o catálogo oficial. Também baixa a lista completa de candidatos (TOIs).

Uso: python -P -E gerar_dados.py <pasta_cache_fits> <pasta_saida_csv>
"""
import sys
from pathlib import Path

import lightkurve as lk
import numpy as np
import pandas as pd
from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive

cache, saida = Path(sys.argv[1]), Path(sys.argv[2])
saida.mkdir(parents=True, exist_ok=True)

# (id, nome exibido, como buscar no MAST, TOI ou None, nome do planeta no catálogo)
ESTRELAS = [
    (1, "WASP-126", "WASP-126", None, "WASP-126 b"),
    (2, "TOI-7831", None, 7831.01, None),
    (3, "TOI-7814", None, 7814.01, None),
    (4, "TOI-7817", None, 7817.01, None),
]
PERIODOS = np.linspace(0.5, 15, 30000)
LIMITE_DEFEITO = 0.05  # nenhum planeta muda o brilho da estrela em mais de 5%


def num(valor):
    return float(getattr(valor, "value", valor))


def baixar(alvo):
    """Até 3 setores; prefere 2 min (SPOC), senão imagens completas (TESS-SPOC, QLP).

    Devolve a curva como vem (filtro padrão) e a curva limpa (filtro rigoroso de
    qualidade + corte dos pontos que mudam mais de 5% do brilho).
    """
    for autor, exptime in (("SPOC", 120), ("TESS-SPOC", None), ("QLP", None)):
        busca = lk.search_lightcurve(alvo, mission="TESS", author=autor, exptime=exptime)
        if len(busca):
            n = 1 if autor == "SPOC" else 3
            como_vem = busca[:n].download_all(download_dir=str(cache), quality_bitmask="default")
            rigoroso = busca[:n].download_all(download_dir=str(cache), quality_bitmask="hard")
            como_vem = como_vem.stitch().remove_nans().normalize()
            limpa = rigoroso.stitch().remove_nans().normalize()
            limpa = limpa[np.abs(limpa.flux.value - np.nanmedian(limpa.flux.value)) < LIMITE_DEFEITO]
            return como_vem, limpa, autor, [lc.sector for lc in rigoroso]
    raise RuntimeError(f"sem curva de luz para {alvo}")


def bls(curva, periodos=PERIODOS, **kw):
    plana = curva.flatten(window_length=901).remove_outliers(sigma_upper=4, sigma_lower=20)
    return plana, plana.to_periodogram(method="bls", period=periodos, frequency_factor=500, **kw)


def busca_completa(curva):
    """Busca larga, protege as quedas na limpeza da variação lenta e refina perto do pico."""
    _, largo = bls(curva)
    p, t0, dur = largo.period_at_max_power.value, float(largo.transit_time_at_max_power.value), largo.duration_at_max_power.value
    mascara = curva.create_transit_mask(period=p, transit_time=t0, duration=dur * 1.5)
    plana = curva.flatten(window_length=901, mask=mascara).remove_outliers(sigma_upper=4, sigma_lower=20)
    largo = plana.to_periodogram(method="bls", period=PERIODOS, frequency_factor=500)
    fino = plana.to_periodogram(method="bls", period=np.linspace(p * 0.99, p * 1.01, 20000),
                                duration=np.linspace(0.05, 0.3, 30))
    return plana, largo, fino


def resumir_periodograma(pg, estrela_id, rodada, n=1500):
    """Reduz a curva de potência a n faixas, guardando o máximo de cada faixa (o pico não some)."""
    per, pot = pg.period.value, pg.power.value
    faixas = np.array_split(np.arange(len(per)), n)
    linhas = []
    for f in faixas:
        i = f[np.nanargmax(pot[f])]
        linhas.append((estrela_id, rodada, round(per[i], 5), pot[i]))
    df = pd.DataFrame(linhas, columns=["estrela_id", "rodada", "periodo_dias", "potencia"])
    df["potencia_rel"] = (df["potencia"] / df["potencia"].max()).round(5)
    return df.drop(columns="potencia")


estrelas, brutas, dobradas, periodogramas = [], [], [], []
for estrela_id, nome, alvo, toi, planeta in ESTRELAS:
    if toi:
        oficial = NasaExoplanetArchive.query_criteria(
            table="toi", select="tid,tfopwg_disp,pl_orbper,pl_trandurh,pl_trandep", where=f"toi={toi}")[0]
        alvo = f"TIC {int(oficial['tid'])}"
        nasa = dict(status="Candidato", periodo=num(oficial["pl_orbper"]),
                    duracao_h=num(oficial["pl_trandurh"]), queda_ppm=num(oficial["pl_trandep"]))
    else:
        oficial = NasaExoplanetArchive.query_criteria(
            table="pscomppars", select="pl_orbper,pl_trandur,pl_trandep", where=f"pl_name='{planeta}'")[0]
        nasa = dict(status="Confirmado", periodo=num(oficial["pl_orbper"]),
                    duracao_h=num(oficial["pl_trandur"]), queda_ppm=num(oficial["pl_trandep"]) * 1e4)

    curva, limpa, fonte, setores = baixar(alvo)
    defeito = ~np.isin(curva.time.value, limpa.time.value)
    print(f"{nome}: fonte {fonte}, setores {setores}, {len(curva)} pontos, {defeito.sum()} defeitos")

    # 1ª rodada: sem descartar os defeitos (é o que deu a queda absurda nos dados QLP)
    _, pg1 = bls(curva)
    p1, q1 = pg1.period_at_max_power.value, pg1.depth_at_max_power.value * 1e6
    periodogramas.append(resumir_periodograma(pg1, estrela_id, "1ª rodada (sem limpeza)"))

    plana, largo, fino = busca_completa(limpa)
    p, t0 = fino.period_at_max_power.value, float(fino.transit_time_at_max_power.value)
    dur_h, queda = fino.duration_at_max_power.value * 24, fino.depth_at_max_power.value * 1e6
    dentro = plana.create_transit_mask(period=p, transit_time=t0, duration=dur_h / 24)
    ruido = np.nanstd(plana.flux.value[~dentro])
    sinal_ruido = float((queda / 1e6) / (ruido / np.sqrt(dentro.sum())))
    periodogramas.append(resumir_periodograma(largo, estrela_id, "Final (com limpeza)"))
    print(f"   1ª rodada {p1:.4f} d / {q1:.0f} ppm | final {p:.4f} d / {queda:.0f} ppm | NASA {nasa['periodo']:.4f} d")

    estrelas.append(dict(
        estrela_id=estrela_id, estrela=nome, alvo_mast=alvo, status_nasa=nasa["status"], fonte_dados=fonte,
        setores=", ".join(str(s) for s in setores), dias_observados=round(float(np.ptp(curva.time.value)), 1),
        pontos=len(curva), pontos_defeito=int(defeito.sum()),
        periodo_1a_rodada_dias=round(p1, 4), queda_1a_rodada_ppm=round(q1),
        periodo_achado_dias=round(p, 4), periodo_nasa_dias=round(nasa["periodo"], 4),
        duracao_achada_h=round(dur_h, 2), duracao_nasa_h=round(nasa["duracao_h"], 2),
        queda_achada_ppm=round(queda), queda_nasa_ppm=round(nasa["queda_ppm"]),
        sinal_ruido=round(sinal_ruido, 1),
    ))

    # curva bruta em médias de 10 min; defeitos ficam ponto a ponto para aparecerem no gráfico
    t, f = curva.time.value, curva.flux.value
    ok = ~defeito
    faixa = np.floor((t[ok] - t.min()) / (10 / 1440))
    bruta = (pd.DataFrame(dict(faixa=faixa, tempo=t[ok], brilho=f[ok]))
             .groupby("faixa", as_index=False).mean().drop(columns="faixa"))
    bruta["defeito"] = False
    bruta = pd.concat([bruta, pd.DataFrame(dict(tempo=t[defeito], brilho=f[defeito], defeito=True))])
    bruta["estrela_id"] = estrela_id
    bruta["dia"] = (bruta["tempo"] - t.min()).round(4)
    brutas.append(bruta[["estrela_id", "dia", "brilho", "defeito"]].round({"brilho": 5}))

    # curva sobreposta (dobrada no período achado), em horas a partir do meio da passagem
    dob = plana.fold(period=p, epoch_time=t0)
    janela = max(0.3, dur_h / 24 * 2)
    fase, fl = dob.time.value, dob.flux.value
    perto = np.abs(fase) < janela
    medicoes = pd.DataFrame(dict(horas=fase[perto] * 24, brilho=fl[perto], tipo="Medição"))
    media = dob.bin(time_bin_size=0.01)
    perto_m = np.abs(media.time.value) < janela
    medias = pd.DataFrame(dict(horas=media.time.value[perto_m] * 24, brilho=media.flux.value[perto_m],
                               tipo="Média a cada ~15 min"))
    dobrada = pd.concat([medicoes, medias]).dropna()
    dobrada["estrela_id"] = estrela_id
    dobradas.append(dobrada[["estrela_id", "tipo", "horas", "brilho"]].round({"horas": 3, "brilho": 5}))

pd.DataFrame(estrelas).to_csv(saida / "estrelas.csv", index=False)
pd.concat(brutas).to_csv(saida / "curva_bruta.csv", index=False)
pd.concat(dobradas).to_csv(saida / "curva_sobreposta.csv", index=False)
pd.concat(periodogramas).to_csv(saida / "busca_periodo.csv", index=False)

# a fila da NASA: todos os TOIs com o status atual
tois = NasaExoplanetArchive.query_criteria(
    table="toi", select="toi,tid,tfopwg_disp,pl_orbper,pl_trandurh,pl_trandep,pl_rade,st_tmag,toi_created").to_pandas()
status = {"PC": "Candidato", "APC": "Candidato ambíguo", "CP": "Confirmado", "KP": "Já conhecido",
          "FP": "Falso positivo", "FA": "Alarme falso"}
tois["status"] = tois["tfopwg_disp"].map(status).fillna("Sem classificação")
tois["testado_por_mim"] = tois["toi"].round(2).isin([t for *_, t, _ in ESTRELAS if t])
tois["data_criacao"] = pd.to_datetime(tois["toi_created"]).dt.date
tois = tois.rename(columns={"tid": "tic", "pl_orbper": "periodo_dias", "pl_trandurh": "duracao_h",
                            "pl_trandep": "queda_ppm", "pl_rade": "raio_terras", "st_tmag": "magnitude_tess"})
tois[["toi", "tic", "status", "periodo_dias", "duracao_h", "queda_ppm", "raio_terras", "magnitude_tess",
      "data_criacao", "testado_por_mim"]].to_csv(saida / "candidatos_nasa.csv", index=False)
print(f"TOIs: {len(tois)} | {tois['status'].value_counts().to_dict()}")
