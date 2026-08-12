# Consulta SNMP de Impressoras

Uma ferramenta desktop para consultar impressoras em rede por SNMP e transformar uma planilha de IPs em um inventário pronto para uso.

Com uma única execução, o programa coleta **número de série**, **marca**, **modelo** e **contador de páginas** de várias impressoras em paralelo.

## O que ela entrega

- Interface gráfica simples: selecione a planilha e acompanhe o progresso em tempo real.
- Leitura de planilhas `.xlsx` e `.xls` com uma coluna chamada `IP`.
- Consultas SNMP v2c com tentativa automática de fallback para SNMP v1.
- Coleta de número de série, marca, modelo e total de páginas impressas.
- Processamento concorrente para acelerar consultas em lote.
- Planilha de saída organizada e salva ao lado do arquivo de origem.

## Como usar

### 1. Instale os requisitos

É necessário ter o Python 3.8 ou superior instalado.

```bash
python -m pip install pandas openpyxl pysnmp
```

No Linux, instale também o suporte ao Tkinter:

```bash
sudo apt install python3-tk
```

### 2. Prepare a planilha

Crie uma planilha Excel com uma coluna chamada `IP`:

| IP |
| --- |
| 192.168.1.10 |
| 192.168.1.11 |

### 3. Abra o programa

```bash
python ui.py
```

1. Clique em **Selecionar arquivo**.
2. Escolha a planilha com os IPs.
3. Clique em **Iniciar consulta**.
4. Ao final, abra a planilha gerada na mesma pasta do arquivo original.

Se a entrada for `impressoras.xlsx`, a saída será:

```text
impressoras_com_consulta_snmp.xlsx
```

## Estrutura da planilha gerada

| Serial Number | IP | Brand | Model | Page Count |
| --- | --- | --- | --- | --- |
| E12345A | 192.168.1.10 | Brother | MFC-L6902DW | 12450 |

Quando uma consulta não puder ser concluída, o respectivo campo será preenchido com `Erro`. IPs ausentes ou inválidos também são registrados na planilha de saída.

## Configuração SNMP

As configurações principais ficam em [consulta_snmp.py](consulta_snmp.py):

```python
COMMUNITY = "public"
TIMEOUT = 3
RETRIES = 1
CONCORRENCIA = 10
```

Altere `COMMUNITY` caso sua rede utilize outra comunidade SNMP. O serviço SNMP da impressora deve estar habilitado e acessível pela porta UDP 161.

## Diagnóstico de uma impressora

Use `teste_snmp.py` para testar um ou mais IPs manualmente. Edite a lista `IPS` no arquivo e execute:

```bash
python teste_snmp.py
```

O script mostra o resultado para SNMP v1 e v2c, consultando o contador e as informações básicas do equipamento.

## Gerar um executável (Windows)

O arquivo `consulta_snmp.spec` está preparado para o PyInstaller.

```bash
python -m pip install pyinstaller
pyinstaller consulta_snmp.spec
```

O executável será gerado em `dist/consulta_snmp/`.

## Principais arquivos

| Arquivo | Função |
| --- | --- |
| `ui.py` | Interface gráfica em Tkinter. |
| `consulta_snmp.py` | Lógica de leitura, consultas SNMP e criação da planilha de saída. |
| `teste_snmp.py` | Diagnóstico SNMP para IPs específicos. |
| `consulta_snmp.spec` | Configuração de empacotamento com PyInstaller. |
| `consultaContadores.py` | Versão de linha de comando para contador e modelo. |

---

Desenvolvido por **Lucca Sarrassini**.
