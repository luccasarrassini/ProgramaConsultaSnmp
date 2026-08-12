import asyncio

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
)

from consulta_snmp import (
    COMMUNITY,
    RETRIES,
    TIMEOUT,
    VERSOES,
    STATUS_OK,
    STATUS_UNKNOWN_ERROR,
    _classify_snmp_error,
    _format_value,
    _is_unsupported_oid_value,
)

IPS = [
    "192.168.1.97",
]

OID_COUNTER = "1.3.6.1.2.1.43.10.2.1.4.1.1"
OID_SYSINFO = "1.3.6.1.2.1.1.1.0"


async def consulta(ip, oid, mp_model, snmp_engine):
    """Executa uma consulta de diagnóstico com o mesmo timeout/retries do programa."""
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
        return False, STATUS_UNKNOWN_ERROR, f"Falha de transporte: {exc}", None
    except Exception as exc:
        return False, STATUS_UNKNOWN_ERROR, f"{type(exc).__name__}: {exc}", None

    if error_indication:
        status, reason = _classify_snmp_error(str(error_indication))
        return False, status, reason, None

    if error_status:
        status, reason = _classify_snmp_error(str(error_status))
        return False, status, reason, None

    if not var_binds:
        return False, "ERRO SNMP", "Resposta SNMP sem valores", None

    value = _format_value(var_binds[0][1])
    if _is_unsupported_oid_value(value):
        return False, "OID NÃO SUPORTADO", value, None

    return True, STATUS_OK, None, value


async def test_ip(ip, snmp_engine):
    print(f"\n{'=' * 60}")
    print(f"TESTANDO {ip}")
    print(f"{'=' * 60}")

    testes = [
        ("Contador de páginas", OID_COUNTER),
        ("Identificação do equipamento", OID_SYSINFO),
    ]

    for descricao, oid in testes:
        print(f"\n{descricao}\nOID: {oid}")
        for version, mp_model in VERSOES:
            ok, status, reason, value = await consulta(ip, oid, mp_model, snmp_engine)
            if ok:
                print(f"✓ {version}: respondeu | Valor: {value}")
            else:
                print(f"✗ {version}: {status} | Motivo: {reason}")


async def main():
    snmp_engine = SnmpEngine()
    try:
        for ip in IPS:
            await test_ip(ip, snmp_engine)
    finally:
        dispatcher = getattr(snmp_engine, "transport_dispatcher", None)
        close_dispatcher = getattr(dispatcher, "close_dispatcher", None)
        if callable(close_dispatcher):
            close_dispatcher()


if __name__ == "__main__":
    asyncio.run(main())
