# Consulta SNMP de Impressoras

Script simples para consultar o contador de páginas de impressoras via SNMP a partir de uma planilha Excel.

Arquivos principais

- `consultaContadores.py` — lê uma planilha com IPs e grava o contador em uma nova planilha.
- `teste_snmp.py` — script de diagnóstico para testar respostas SNMP por IP.

Requisitos

- Python 3.8+
- Bibliotecas Python:
  - `pysnmp`
  - `pandas`
  - `openpyxl` (para leitura/escrita do Excel)
  - `tkinter` (para diálogo de seleção de arquivo; já incluso na maioria das instalações do Python no Windows)

Instalação rápida

Abra um terminal e rode:

```bash
python -m pip install pysnmp pandas openpyxl
```

Uso

1. `consultaContadores.py`

- Execute o script e selecione a planilha quando o diálogo for exibido. O script espera que a planilha tenha uma coluna chamada `IP` com os endereços.

```bash
python consultaContadores.py
```

- Saída: `impressoras_com_contador.xlsx` no mesmo diretório da planilha origem.

2. `teste_snmp.py`

- Use este script para diagnosticar IPs problemáticos (mostra indicações de erro, status e valores retornados).

```bash
python teste_snmp.py
```

Formato esperado da planilha Excel

- Planilha (XLSX/XLS) com uma coluna chamada `IP` (sem outras formatações obrigatórias). Exemplo:

| IP |
|-----|
| 10.5.0.164 |
| 10.5.0.191 |

Configurações importantes (em `consultaContadores.py`)

- `COMMUNITY` — comunidade SNMP (padrão: `public`).
- `OID` — OID consultado para o contador de páginas (padrão: `1.3.6.1.2.1.43.10.2.1.4.1.1`).
- `TIMEOUT` — tempo de espera por requisição (segundos). Ajuste se impressoras respondem devagar.
- `RETRIES` — número de tentativas adicionais por requisição.
- `CONCORRENCIA` — quantidade máxima de requisições simultâneas (limita uso de rede/CPU).

Dicas de diagnóstico e resolução de problemas

- Se algumas impressoras estão acessíveis na rede mas retornam erro:
  - Verifique se usam SNMPv1 em vez de SNMPv2c. O script já tenta `v2c` e `v1` nesta ordem.
  - Aumente `TIMEOUT` (ex.: 5–10s) e `RETRIES`.
  - Teste um único IP com `teste_snmp.py` para ver mensagens mais detalhadas.
  - Verifique regras de firewall ou ACL que possam limitar o tráfego SNMP (UDP/161).
  - Confirme a comunidade SNMP (pode não ser `public`).

Execução em ambientes sem GUI

- Os scripts atuais abrem um diálogo de arquivo com `tkinter`. Em servidores/headless, edite `consultaContadores.py` e atribua o caminho do arquivo diretamente à variável `ARQUIVO` para evitar o diálogo.

Exemplo:

```python
ARQUIVO = r"C:\caminho\para\planilha.xlsx"
```

Observações finais

- `consultaContadores.py` foi implementado com um `Semaphore` para limitar a concorrência e reutiliza uma instância de `SnmpEngine` para melhor desempenho.
- Se quiser, posso gerar também um `requirements.txt`, um exemplo de planilha ou um `README` mais detalhado com exemplos de troubleshooting e comandos para coletar pacotes de rede (tcpdump/wireshark).

Se quiser que eu adicione algum detalhe extra (ex.: `requirements.txt`, exemplo de planilha ou instruções para execução em Linux), diga qual opção prefere.