# xfep-ws

Cliente SOAP/REST para los servicios web de SUNAT (SEE y GRE).

Parte del [ecosistema XFEP](https://github.com/xpertik). Envía XML firmado (de [`xfep-sign`](https://github.com/xpertik/xfep-sign)) a SUNAT y recibe respuestas (CDR).

## Instalación

```bash
pip install xfep-ws
```

## Uso

### SOAP (Facturas, Boletas, NC, ND, Resumenes)

```python
from xfep.ws import SunatSoap

async with SunatSoap("20123456789", "MODDATOS", "MODDATOS") as client:
    # Enviar factura
    response = await client.send_bill(xml_bytes, "20123456789-01-F001-1")
    print(response.cdr_code, response.cdr_description)

    # Enviar resumen diario
    summary = await client.send_summary(xml_bytes, "20123456789-RC-20260101-1")
    print(summary.ticket)

    # Consultar estado
    status = await client.get_status(summary.ticket)
    print(status.status_code)
```

### REST (Guias de Remision)

```python
from xfep.ws import SunatRest

async with SunatRest("client_id", "client_secret") as client:
    result = await client.send_despatch(xml_bytes, "20123456789-09-T001-1")
    status = await client.get_status(result["numTicket"])
```

## Entornos

Por defecto usa SUNAT Beta. Para produccion:

```python
SunatSoap("20123456789", "USER", "PASS", production=True)
SunatRest("client_id", "secret", production=True)
```

## API

### `SunatSoap`

| Método | Retorna | Descripción |
|--------|---------|-------------|
| `send_bill(xml_bytes, filename)` | `BillResponse` | Envío directo (Invoice, NC, ND). CDR inmediato. |
| `send_summary(xml_bytes, filename)` | `SummaryResponse` | Envío batch (Resumen Diario, Baja). Retorna ticket. |
| `get_status(ticket)` | `StatusResponse` | Consultar estado por ticket. |

### `SunatRest`

| Método | Retorna | Descripción |
|--------|---------|-------------|
| `send_despatch(xml_bytes, filename)` | `dict` | Enviar GRE. Retorna ticket. |
| `get_status(ticket)` | `dict` | Consultar estado de GRE. |

### Modelos de respuesta

| Modelo | Campos principales |
|--------|-------------------|
| `BillResponse` | `success`, `cdr_bytes`, `cdr_code`, `cdr_description`, `hash_value` |
| `SummaryResponse` | `success`, `ticket` |
| `StatusResponse` | `success`, `status_code`, `cdr_bytes`, `cdr_code`, `cdr_description` |

## Endpoints SUNAT

| Servicio | Beta | Producción |
|----------|------|------------|
| SOAP (Facturación) | `e-beta.sunat.gob.pe` | `e-factura.sunat.gob.pe` |
| REST (GRE) | `api-cpe-beta.sunat.gob.pe` | `api-cpe.sunat.gob.pe` |

## Desarrollo

```bash
git clone https://github.com/xpertik/xfep-ws.git
cd xfep-ws
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

## Stack

- **Python** >= 3.13
- **httpx** >= 0.27 (SOAP + REST, async)
- **pytest-asyncio** (tests)
- **Build**: Hatchling

## Parte del ecosistema XFEP

| Paquete | Estado | Descripción |
|---------|--------|-------------|
| [xfep-models](https://github.com/xpertik/xfep-models) | v0.1.0 | Modelos de datos |
| [xfep-xml](https://github.com/xpertik/xfep-xml) | v0.1.0 | Generación XML UBL 2.1 |
| [xfep-sign](https://github.com/xpertik/xfep-sign) | v0.1.0 | Firma digital XMLDSig |
| **xfep-ws** | **v0.1.0** | **Cliente SOAP/REST SUNAT** |
| xfep-parser | pendiente | Parseo de respuestas SUNAT |

## Licencia

Apache License 2.0 — ver [LICENSE](LICENSE).
