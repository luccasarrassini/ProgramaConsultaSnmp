import pandas as pd
import asyncio
import os

from pysnmp.hlapi.v3arch.asyncio import *

from tkinter import Tk, filedialog

# ==========================
# CONFIGURAÇÕES
# ==========================

COMMUNITY = "public"
OID = "1.3.6.1.2.1.43.10.2.1.4.1.1"
OID_MODELO = "1.3.6.1.2.1.25.3.2.1.3.1"

TIMEOUT = 3
RETRIES = 1

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
            return {"contador": "IP Vazio", "modelo": ""}

        print(f"Consultando {ip}...")

        versoes = [
            ("v2c", 1),
            ("v1", 0)
        ]

        contador = None
        modelo = None

        for nome_versao, mp_model in versoes:

            try:

                transport = await UdpTransportTarget.create(
                    (ip, 161),
                    timeout=TIMEOUT,
                    retries=RETRIES
                )

                # Consulta contador
                if not contador:
                    errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
                        snmp_engine,
                        CommunityData(COMMUNITY, mpModel=mp_model),
                        transport,
                        ContextData(),
                        ObjectType(ObjectIdentity(OID))
                    )

                    if not errorIndication and not errorStatus and varBinds:
                        try:
                            contador = int(varBinds[0][1])
                        except:
                            pass

                # Consulta modelo
                if not modelo:
                    errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
                        snmp_engine,
                        CommunityData(COMMUNITY, mpModel=mp_model),
                        transport,
                        ContextData(),
                        ObjectType(ObjectIdentity(OID_MODELO))
                    )

                    if not errorIndication and not errorStatus and varBinds:
                        modelo = str(varBinds[0][1]).strip()

                # Se conseguiu ambos, sai do loop
                if contador and modelo:
                    break

            except Exception:
                pass

        # Fallback para valores não encontrados
        if not contador:
            contador = "Erro"
        if not modelo:
            modelo = "Erro"

        print(
            f"  ✓ {ip} | "
            f"{contador} páginas | "
            f"Modelo: {modelo}"
        )

        return {"contador": contador, "modelo": modelo}

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

    df["Contador"] = [r["contador"] for r in resultados]
    df["Modelo"] = [r["modelo"] for r in resultados]

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

asyncio.run(main())