import asyncio
import ipaddress
import math
import os
import re

import pandas as pd
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
)

# ==========================
# Configurações SNMP
# ==========================
COMMUNITY = "public"
TIMEOUT = 3
RETRIES = 1
CONCORRENCIA = 10

# OIDs padrão para impressoras
OID_SERIAL = "1.3.6.1.2.1.43.5.1.1.17.1"  # Número de série
OID_MODEL = "1.3.6.1.2.1.25.3.2.1.3.1"    # Modelo padrão (nome comercial) - Padrão Brother
OID_BRAND = "1.3.6.1.2.1.1.1.0"           # sysDescr (marca/descrição)
OID_COUNTER = "1.3.6.1.2.1.43.10.2.1.4.1.1"  # Contador de páginas
OID_ALT_MODEL = "1.3.6.1.2.1.43.5.1.1.16.1"  # Modelo alternativo (fallback)
OID_BROTHER_MODEL = "1.3.6.1.4.1.1240.2.1.1.1.0"  # Modelo alternativo Brother (legacy)

# Versões SNMP a tentar, na ordem preferida
VERSOES = [
    ("v2c", 1),
    ("v1", 0),
]

OUTPUT_COLUMNS = [
    "Serial Number",
    "IP",
    "Brand",
    "Model",
    "Page Count",
    "Status",
    "SNMP Version",
    "Failure Reason",
]

STATUS_OK = "OK"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_SNMP_ERROR = "ERRO SNMP"
STATUS_OID_NOT_SUPPORTED = "OID NÃO SUPORTADO"
STATUS_UNKNOWN_ERROR = "ERRO DESCONHECIDO"


def _format_value(value):
    """Converte valor SNMP para string e remove espaços extras."""
    if value is None:
        return ""
    return str(value).strip()


def _extract_brand(brand_raw):
    """Extrai apenas o primeiro nome/palavra do brand (a marca)."""
    if not brand_raw:
        return ""
    
    # Pega o primeiro word separado por espaço, ponto-e-vírgula ou outros separadores
    parts = str(brand_raw).strip().split()
    if parts:
        return parts[0]
    return brand_raw


def _is_valid_ip(ip):
    """Valida se o campo contém um endereço IPv4/IPv6 válido."""
    if ip is None:
        return False

    if isinstance(ip, float) and math.isnan(ip):
        return False

    texto = str(ip).strip()
    if not texto:
        return False

    try:
        ipaddress.ip_address(texto)
        return True
    except ValueError:
        return False


async def _snmp_get(ip, oid, mp_model, snmp_engine):
    """Consulta um OID e retorna valor ou falha classificada, sem ocultar erros."""
    try:
        transport = await UdpTransportTarget.create(
            (ip, 161),
            timeout=TIMEOUT,
            retries=RETRIES,
        )
        error_indication, error_status, _, var_binds = await get_cmd(
            snmp_engine,
            CommunityData(COMMUNITY, mpModel=mp_model),
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
    except (OSError, ValueError) as exc:
        return _failure_result(STATUS_UNKNOWN_ERROR, f"Falha de transporte: {exc}")
    except Exception as exc:
        return _failure_result(STATUS_UNKNOWN_ERROR, f"{type(exc).__name__}: {exc}")

    if error_indication:
        status, reason = _classify_snmp_error(str(error_indication))
        return _failure_result(status, reason)

    if error_status:
        status, reason = _classify_snmp_error(str(error_status))
        return _failure_result(status, reason)

    if not var_binds:
        return _failure_result(STATUS_SNMP_ERROR, "Resposta SNMP sem valores")

    value = var_binds[0][1]
    value_text = _format_value(value)
    if _is_unsupported_oid_value(value_text):
        return _failure_result(STATUS_OID_NOT_SUPPORTED, value_text)

    return {"ok": True, "value": value_text, "status": STATUS_OK, "reason": None}


def _failure_result(status, reason):
    return {"ok": False, "value": None, "status": status, "reason": reason}


def _classify_snmp_error(message):
    """Classifica mensagens do pysnmp em status que serão gravados na planilha."""
    normalized = message.strip().lower()
    if "timeout" in normalized or "no snmp response received" in normalized:
        return STATUS_TIMEOUT, message
    if _is_unsupported_oid_value(normalized):
        return STATUS_OID_NOT_SUPPORTED, message
    return STATUS_SNMP_ERROR, message


def _is_unsupported_oid_value(value):
    normalized = str(value).strip().lower()
    markers = ("nosuchobject", "no such object", "nosuchinstance", "no such instance", "nosuchname", "no such name")
    return any(marker in normalized for marker in markers)


async def _select_snmp_version(ip, snmp_engine):
    """Testa o contador em v2c e v1, preservando o resultado da tentativa válida."""
    last_result = _failure_result(STATUS_SNMP_ERROR, "Nenhuma versão SNMP respondeu")
    for version, mp_model in VERSOES:
        result = await _snmp_get(ip, OID_COUNTER, mp_model, snmp_engine)
        if result["ok"] or result["status"] == STATUS_OID_NOT_SUPPORTED:
            return version, mp_model, result
        last_result = result
    return None, None, last_result


KNOWN_BRANDS = [
    "Brother",
    "Samsung",
    "HP",
    "Hewlett-Packard",
    "Canon",
    "Epson",
    "Ricoh",
    "Xerox",
    "Kyocera",
    "Konica Minolta",
    "Lexmark",
    "OKI",
    "Toshiba",
]

BROTHER_MODEL_PREFIXES = [
    "MFC",
    "DCP",
    "HL",
    "QL",
    "PT",
    "FAX",
    "ADS",
    "DW",
]

BROTHER_MODEL_PATTERN = re.compile(
    r"\bBrother\b[\s,:;-]*(?P<model>(?:MFC|DCP|HL|QL|PT|FAX|ADS|DW|MZ|RJ|TD|PJ|VS|HLL|HLLJ)[-\w]*)",
    re.IGNORECASE,
)


def _parse_brand_model(sysdescr):
    """Extrai marca e modelo a partir do sysDescr de impressoras."""
    if not sysdescr:
        return None, None

    texto = sysdescr.strip()
    texto_lower = texto.lower()
    skip_words = {"series", "machine", "printer", "ver.", "ver", "series,"}

    brother_match = BROTHER_MODEL_PATTERN.search(texto)
    if brother_match:
        modelo = brother_match.group("model").strip()
        if modelo:
            return "Brother", modelo

    for marca in KNOWN_BRANDS:
        marca_lower = marca.lower()
        if marca_lower in texto_lower:
            pattern = re.compile(
                fr"\b{re.escape(marca)}\b\s+([^,]+?)(?:\s+(?:series|machine|printer|ver\.?|version|build)\b|,|$)",
                re.IGNORECASE,
            )
            match = pattern.search(texto)
            if match:
                model = match.group(1).strip()
                model = re.sub(r"\b(series|machine|printer|ver\.?|version|build)\b", "", model, flags=re.IGNORECASE).strip()
                model = re.sub(r"[(),]", "", model).strip()
                if model and not _is_reject_model_text(model):
                    if marca_lower == "hewlett-packard":
                        marca = "HP"
                    return marca, model

            partes = texto.split()
            model = None
            for idx, parte in enumerate(partes):
                if parte.lower() == marca_lower and idx + 1 < len(partes):
                    model_candidate = partes[idx + 1]
                    if (
                        model_candidate.lower() not in skip_words
                        and re.search(r"\d", model_candidate)
                        and not _is_reject_model_text(model_candidate)
                    ):
                        model = model_candidate
                        break

            if model is None:
                for parte in partes:
                    if (
                        parte.lower() not in skip_words
                        and parte.lower() != marca_lower
                        and re.search(r"\d", parte)
                        and not _is_reject_model_text(parte)
                    ):
                        model = parte
                        break

            if marca_lower == "hewlett-packard":
                marca = "HP"

            return marca, model

    return None, None


def _is_reject_model_text(modelo):
    if not modelo:
        return False

    valor = str(modelo).strip().lower()
    reject_terms = ["node", "host", "hostname", "port", "interface", "service"]
    return any(term in valor for term in reject_terms)


def _is_brother_model(modelo):
    if not modelo:
        return False

    valor = str(modelo).strip().upper()
    if not valor:
        return False

    if _is_reject_model_text(valor):
        return False

    for prefix in BROTHER_MODEL_PREFIXES:
        if valor.startswith(prefix):
            return bool(re.search(r"\d", valor))

    return False


def _is_printer_model(modelo, marca=None):
    """Verifica se o valor parece ser um modelo de impressora válido."""
    if not modelo:
        return False

    valor = str(modelo).strip()
    lower_valor = valor.lower()
    reject_terms = [
        "ethernet", "lan", "network", "adapter", "nic", "wireless",
        "realtek", "intel", "broadcom", "rtl", "usb", "gigabit",
        "ether", "fast", "1000", "100", "packet", "interface",
        "serial", "mac", "port", "driver",
    ]

    if any(term in lower_valor for term in reject_terms):
        return False

    if marca and "brother" in str(marca).lower():
        if _is_brother_model(valor):
            return True
        return False

    if lower_valor.startswith("nc-") or lower_valor.startswith("nc") and re.match(r"^nc[-\d]+$", lower_valor):
        return False

    if len(valor) < 3:
        return False

    return bool(re.search(r"[a-zA-Z]", valor) and re.search(r"\d", valor))


def _clean_model(modelo, marca, sysdescr):
    """Limpa o campo de modelo para deixar somente a informação relevante."""
    if not modelo or modelo.lower() in ("erro", "unknown", ""):
        return modelo

    modelo_text = str(modelo).strip()
    marca_text = str(marca).strip()
    lower_model = modelo_text.lower()
    lower_brand = marca_text.lower()

    # Se o modelo contém a marca, remova-a.
    if lower_brand and lower_brand in lower_model:
        cleaned = re.sub(re.escape(lower_brand), "", lower_model, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"(series|printer|machine|ver\.?|\(|\)|,)", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            return cleaned.upper()

    # Extração direta a partir do sysDescr, que pode conter modelo mais claro.
    if sysdescr:
        _, parsed_model = _parse_brand_model(sysdescr)
        if parsed_model and _is_printer_model(parsed_model, marca):
            return parsed_model

    if marca and "brother" in str(marca).lower() and modelo_text:
        if _is_brother_model(modelo_text):
            return modelo_text
        modelo_text = modelo_text.upper()
        if any(modelo_text.startswith(prefix) for prefix in BROTHER_MODEL_PREFIXES):
            return modelo_text

    return modelo_text


async def _consultar_impressora_async(ip, snmp_engine, semaforo):
    """Consulta uma impressora sem deixar uma falha individual interromper o lote."""
    try:
        return await _consultar_impressora_interno(ip, snmp_engine, semaforo)
    except Exception as exc:
        return _printer_failure(
            _failure_result(STATUS_UNKNOWN_ERROR, f"{type(exc).__name__}: {exc}")
        )


async def _consultar_impressora_interno(ip, snmp_engine, semaforo):
    """Executa a consulta protegida pelo limite de concorrência."""
    async with semaforo:
        version, mp_model, counter_result = await _select_snmp_version(ip, snmp_engine)
        if version is None:
            return _printer_failure(counter_result)

        # Depois de identificar a versão, consulta os outros OIDs apenas uma vez.
        serial_result, brand_result, model_result = await asyncio.gather(
            _snmp_get(ip, OID_SERIAL, mp_model, snmp_engine),
            _snmp_get(ip, OID_BRAND, mp_model, snmp_engine),
            _snmp_get(ip, OID_MODEL, mp_model, snmp_engine),
        )

        model_value = model_result["value"]
        model_reason = model_result["reason"]
        model_status = model_result["status"]
        if model_value is None and model_result["status"] == STATUS_OID_NOT_SUPPORTED:
            alt_model_result = await _snmp_get(ip, OID_ALT_MODEL, mp_model, snmp_engine)
            if alt_model_result["ok"]:
                model_value = alt_model_result["value"]
                model_reason = None
                model_status = STATUS_OK
            else:
                model_reason = alt_model_result["reason"]
                model_status = alt_model_result["status"]

        brand_raw = brand_result["value"]
        brand = _extract_brand(brand_raw) if brand_raw is not None else None
        if brand_raw is not None and model_value is not None:
            _, parsed_model = _parse_brand_model(brand_raw)
            if parsed_model and _is_printer_model(parsed_model, brand):
                model_value = _clean_model(parsed_model, brand, brand_raw)

        failure_reason = None
        status = STATUS_OK
        if not counter_result["ok"]:
            status = counter_result["status"]
            failure_reason = counter_result["reason"]
        else:
            field_failures = [
                result
                for result in (serial_result, brand_result)
                if not result["ok"]
            ]
            if model_value is None:
                field_failures.append({"status": model_status, "reason": model_reason})
            if field_failures:
                status = field_failures[0]["status"]
                failure_reason = "; ".join(
                    result["reason"] for result in field_failures if result["reason"]
                ) or None

        return {
            "Serial Number": serial_result["value"],
            "Brand": brand,
            "Model": model_value,
            "Page Count": counter_result["value"],
            "Status": status,
            "SNMP Version": version,
            "Failure Reason": failure_reason,
        }


def _printer_failure(result):
    return {
        "Serial Number": None,
        "Brand": None,
        "Model": None,
        "Page Count": None,
        "Status": result["status"],
        "SNMP Version": None,
        "Failure Reason": result["reason"],
    }


def _to_spreadsheet_value(value, error_value=""):
    """Converte None em texto somente no momento de gerar a planilha."""
    return error_value if value is None else value


async def _processar_planilha_async(caminho_arquivo, logger=print, progress_callback=None):
    """Lê a planilha, consulta todos os IPs de forma concorrente e grava a saída."""
    logger(f"Lendo planilha: {caminho_arquivo}")

    df = pd.read_excel(caminho_arquivo)

    if "IP" not in df.columns:
        raise ValueError("Coluna 'IP' não encontrada na planilha.")

    resultados = []
    tarefas = []

    snmp_engine = SnmpEngine()
    semaforo = asyncio.Semaphore(CONCORRENCIA)
    try:
        for linha, ip in enumerate(df["IP"], start=1):
            ip_str = str(ip).strip()

            if not _is_valid_ip(ip_str):
                logger(f"[{linha}] IP inválido ou ausente: {ip}")
                resultados.append({
                    "Serial Number": None,
                    "IP": ip_str,
                    "Brand": None,
                    "Model": None,
                    "Page Count": None,
                    "Status": STATUS_UNKNOWN_ERROR,
                    "SNMP Version": None,
                    "Failure Reason": "IP inválido ou ausente",
                })
                continue

            logger(f"[{linha}] Agendando consulta para IP: {ip_str}")
            tarefas.append((linha, ip_str, asyncio.create_task(_consultar_impressora_async(ip_str, snmp_engine, semaforo))))

        total = len(tarefas)
        if progress_callback is not None:
            progress_callback(0, total)

        concluido = 0
        for linha, ip_str, tarefa in tarefas:
            dados = await tarefa
            dados["IP"] = ip_str
            resultados.append(dados)
            concluido += 1

            if progress_callback is not None:
                progress_callback(concluido, total)

            logger(
                f"[{linha}] Status: {dados['Status']} | SNMP: {dados['SNMP Version'] or '-'} | "
                f"Serial Number: {dados['Serial Number']} | Brand: {dados['Brand']} | "
                f"Model: {dados['Model']} | Page Count: {dados['Page Count']}"
            )
    finally:
        dispatcher = getattr(snmp_engine, "transport_dispatcher", None)
        close_dispatcher = getattr(dispatcher, "close_dispatcher", None)
        if callable(close_dispatcher):
            close_dispatcher()

    for resultado in resultados:
        for field in ("Serial Number", "Brand", "Model", "Page Count", "SNMP Version", "Failure Reason"):
            resultado[field] = _to_spreadsheet_value(resultado[field])

    df_saida = pd.DataFrame(resultados, columns=OUTPUT_COLUMNS)
    pasta_saida = os.path.dirname(caminho_arquivo)
    nome_arquivo = os.path.splitext(os.path.basename(caminho_arquivo))[0]
    arquivo_saida = os.path.join(pasta_saida, f"{nome_arquivo}_com_consulta_snmp.xlsx")
    df_saida.to_excel(arquivo_saida, index=False)

    logger(f"Planilha salva em: {arquivo_saida}")
    return arquivo_saida


def processar_planilha(caminho_arquivo, logger=print, progress_callback=None):
    """Função de entrada síncrona para o frontend."""
    return asyncio.run(_processar_planilha_async(caminho_arquivo, logger=logger, progress_callback=progress_callback))
