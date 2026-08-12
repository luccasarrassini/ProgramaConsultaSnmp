from pysnmp.hlapi.v3arch.asyncio import *
import asyncio

IPS = [
    "192.168.1.97"
]

COMMUNITY = "public"

# OID do contador
OID_COUNTER = "1.3.6.1.2.1.43.10.2.1.4.1.1"

# OID básica de identificação
OID_SYSINFO = "1.3.6.1.2.1.1.1.0"

TIMEOUT = 5


async def consulta(ip, oid, mp_model):
    try:
        snmp_engine = SnmpEngine()

        transport = await UdpTransportTarget.create(
            (ip, 161),
            timeout=TIMEOUT,
            retries=2
        )

        errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
            snmp_engine,
            CommunityData(COMMUNITY, mpModel=mp_model),
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )

        if errorIndication:
            return False, str(errorIndication)

        if errorStatus:
            return False, str(errorStatus)

        if varBinds:
            return True, str(varBinds[0][1])

        return False, "Sem resposta"

    except Exception as e:
        return False, str(e)


async def test_ip(ip):
    print(f"\n{'='*60}")
    print(f"TESTANDO {ip}")
    print(f"{'='*60}")

    testes = [
        ("v2c + contador", OID_COUNTER, 1),
        ("v1 + contador", OID_COUNTER, 0),
        ("v2c + sysinfo", OID_SYSINFO, 1),
        ("v1 + sysinfo", OID_SYSINFO, 0),
    ]

    for nome, oid, versao in testes:
        ok, resultado = await consulta(ip, oid, versao)

        print(f"\n{nome}")
        print(f"OID: {oid}")

        if ok:
            print(f"✓ SUCESSO: {resultado}")
        else:
            print(f"✗ FALHA: {resultado}")


async def main():
    for ip in IPS:
        await test_ip(ip)

asyncio.run(main())