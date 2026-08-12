import pandas as pd
import asyncio
import os

from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

from tkinter import Tk, filedialog
from consulta_snmp import (
    STATUS_OK,
    STATUS_UNKNOWN_ERROR,
    _select_snmp_version,
    _snmp_get,
)

# ==========================
# CONFIGURAÇÕES
# ==========================

OID_MODELO = "1.3.6.1.2.1.25.3.2.1.3.1"

# Quantidade máxima de consultas simultâneas
CONCORRENCIA = 20

# ==========================
# SELEÇÃO DO ARQUIVO
# ==========================

root = Tk()
root.withdraw()

ARQUIVO = filedialog.askopenfilename(
    title="Selecione a planilha",
    filetypes=[
        ("Planilhas Excel", "*.xlsx *.xls"),
        ("Todos os arquivos", "*.*")
    ]
)

if not ARQUIVO:
    print("Nenhum arquivo selecionado.")
    exit()

# ==========================
# SNMP
# ==========================

snmp_engine = SnmpEngine()

semaforo = asyncio.Semaphore(CONCORRENCIA)

async def consultar_contador(ip):
    async with semaforo:
        ip = str(ip).strip()
        if not ip:
            return {
                "contador": None,
                "modelo": None,
                "status": STATUS_UNKNOWN_ERROR,
                "versao_snmp": None,
                "motivo": "IP vazio",
            }

        print(f"Consultando {ip}...")
        versao, mp_model, contador_result = await _select_snmp_version(ip, snmp_engine)
        if versao is None:
            print(f"  ✗ {ip} | {contador_result['status']}: {contador_result['reason']}")
            return {
                "contador": None,
                "modelo": None,
                "status": contador_result["status"],
                "versao_snmp": None,
                "motivo": contador_result["reason"],
            }

        modelo_result = await _snmp_get(ip, OID_MODELO, mp_model, snmp_engine)
        status = STATUS_OK if contador_result["ok"] else contador_result["status"]
        motivo = contador_result["reason"] if not contador_result["ok"] else None
        if modelo_result["value"] is None and motivo is None:
            status = modelo_result["status"]
            motivo = modelo_result["reason"]

        print(
            f"  {'✓' if status == STATUS_OK else '✗'} {ip} | {status} | "
            f"{contador_result['value']} páginas | Modelo: {modelo_result['value']} | SNMP: {versao}"
        )
        return {
            "contador": contador_result["value"],
            "modelo": modelo_result["value"],
            "status": status,
            "versao_snmp": versao,
            "motivo": motivo,
        }

# ==========================
# PROCESSAMENTO
# ==========================

async def main():

    print("\nLendo planilha...\n")

    df = pd.read_excel(ARQUIVO)

    if "IP" not in df.columns:
        print("Coluna 'IP' não encontrada.")
        return

    tarefas = [
        consultar_contador(ip)
        for ip in df["IP"]
    ]

    resultados = await asyncio.gather(*tarefas)

    df["Contador"] = ["" if r["contador"] is None else r["contador"] for r in resultados]
    df["Modelo"] = ["" if r["modelo"] is None else r["modelo"] for r in resultados]
    df["Status"] = [r["status"] for r in resultados]
    df["Versão SNMP"] = ["" if r["versao_snmp"] is None else r["versao_snmp"] for r in resultados]
    df["Motivo da falha"] = ["" if r["motivo"] is None else r["motivo"] for r in resultados]

    arquivo_saida = os.path.join(
        os.path.dirname(ARQUIVO),
        "impressoras_com_contador.xlsx"
    )

    df.to_excel(
        arquivo_saida,
        index=False
    )

    print("\n====================================")
    print("PROCESSAMENTO CONCLUÍDO")
    print("====================================")
    print(f"Arquivo salvo em:\n{arquivo_saida}")

try:
    asyncio.run(main())
finally:
    dispatcher = getattr(snmp_engine, "transport_dispatcher", None)
    close_dispatcher = getattr(dispatcher, "close_dispatcher", None)
    if callable(close_dispatcher):
        close_dispatcher()
