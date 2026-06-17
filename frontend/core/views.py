from datetime import date, datetime
from math import ceil
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .services import ApiError, api_delete, api_get, api_patch, api_post, api_put

PATIENTS_PER_PAGE = 10
TIPOS_ATENDIMENTO = ('Ambulatório', 'Externo', 'Urgência', 'Internação')
PRAZOS_RECURSO_CONVENIO_PATH = "/app_glosas/prazos-recurso-convenio"


def format_api_date(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")

    text = str(value).strip()
    if not text:
        return "-"

    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).strftime("%d/%m/%Y")
    except ValueError:
        pass

    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return text[:10]

    return text


def format_api_date_input(value):
    if not value:
        return ""
    if isinstance(value, datetime | date):
        return value.strftime("%Y-%m-%d")

    text = str(value).strip()
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return ""


def format_api_datetime(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M:%S")

    text = str(value).strip()
    if not text:
        return "-"

    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        pass

    return text


def format_lancamento_datetime(dt_lancamento, hr_lancamento):
    formatted = format_api_datetime(hr_lancamento)
    if formatted != "-" and "/" in formatted:
        return formatted

    data = format_api_date(dt_lancamento)
    if data == "-":
        return formatted
    if formatted == "-":
        return data
    return f"{data} {formatted}"


def format_api_error(exc: ApiError, endpoint_name: str) -> str:
    if exc.status_code == 401:
        return f"{endpoint_name}: API exige autenticacao. Configure API_BEARER_TOKEN no ambiente do frontend."
    if exc.status_code == 404:
        return f"{endpoint_name}: endpoint ainda nao encontrado na API."
    return f"{endpoint_name}: {exc}"


def is_service_unavailable_error(exc: ApiError) -> bool:
    text = str(exc).lower()
    unavailable_terms = (
        "timeout",
        "timed out",
        "ora-",
        "oracle",
        "banco",
        "database",
        "connection",
    )
    return exc.status_code is None or exc.status_code >= 500 or any(term in text for term in unavailable_terms)


def is_browser_reload(request):
    if request.GET.get("_modal_action") == "1":
        return False

    cache_control = request.headers.get("Cache-Control", "").lower()
    pragma = request.headers.get("Pragma", "").lower()
    return (
        "max-age=0" in cache_control
        or "no-cache" in cache_control
        or pragma == "no-cache"
    )


def with_modal_action_marker(full_path):
    parts = urlsplit(full_path)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["_modal_action"] = "1"
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def is_ajax_request(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def modal_action_response(request, message, tag, status=200, api_payload=None):
    if is_ajax_request(request):
        return JsonResponse(
            {
                "ok": status < 400,
                "message": message,
                "tag": tag,
                "payload": api_payload,
            },
            status=status,
        )

    getattr(messages, "error" if tag == "error" else tag)(request, message)
    return redirect(with_modal_action_marker(request.get_full_path()))


def _group_itens_by_grupo_faturamento(itens):
    grupos = {}
    ordem = []
    for item in itens:
        grupo = item.get("ds_gru_fat") or "Grupo nao informado"
        if grupo not in grupos:
            grupos[grupo] = []
            ordem.append(grupo)
        grupos[grupo].append(item)

    return [
        {
            "ds_gru_fat": grupo,
            "itens": grupos[grupo],
            "num_lancamentos": len(grupos[grupo]),
        }
        for grupo in ordem
    ]


def _group_contas(contas):
    """Group a flat list of contas by nm_paciente, cd_remessa and cd_atendimento."""
    by_paciente = {}
    order_paciente = []
    for conta in contas:
        pac = conta.get("nm_paciente") or "-"
        rem = str(conta.get("cd_remessa") or "-")
        atd = str(conta.get("cd_atendimento") or "-")
        if pac not in by_paciente:
            by_paciente[pac] = {}
            order_paciente.append(pac)
        if rem not in by_paciente[pac]:
            by_paciente[pac][rem] = {}
        if atd not in by_paciente[pac][rem]:
            by_paciente[pac][rem][atd] = []
        by_paciente[pac][rem][atd].append(conta)

    result = []
    for pac in order_paciente:
        remessas = []
        pac_total = 0.0
        pac_lancamentos = 0
        pac_convenios = set()
        pac_atendimentos = 0
        for rem, atendimentos_por_remessa in by_paciente[pac].items():
            atendimentos = []
            rem_total = 0.0
            rem_lancamentos = 0
            rem_convenios = set()
            rem_procedimentos = set()
            for atd, itens in atendimentos_por_remessa.items():
                atd_total = 0.0
                atd_convenios = set()
                atd_procedimentos = set()
                for item in itens:
                    try:
                        atd_total += float(item.get("vl_total_conta") or 0)
                    except (TypeError, ValueError):
                        pass
                    conv = item.get("nm_convenio")
                    if conv:
                        atd_convenios.add(conv)
                    proc = item.get("cd_pro_fat")
                    if proc:
                        atd_procedimentos.add(str(proc))
                rem_total += atd_total
                rem_lancamentos += len(itens)
                rem_convenios |= atd_convenios
                rem_procedimentos |= atd_procedimentos
                primeiro_item = itens[0] if itens else {}
                atendimentos.append({
                    "cd_atendimento": atd,
                    "itens": itens,
                    "total": atd_total,
                    "num_lancamentos": len(itens),
                    "convenios": sorted(atd_convenios),
                    "procedimentos": sorted(atd_procedimentos),
                    "grupos_faturamento": _group_itens_by_grupo_faturamento(
                        itens
                    ),
                    "dt_atendimento": primeiro_item.get(
                        "dt_atendimento_formatada"
                    ),
                    "dt_alta": primeiro_item.get("dt_alta_formatada"),
                })
            pac_total += rem_total
            pac_lancamentos += rem_lancamentos
            pac_atendimentos += len(atendimentos)
            pac_convenios |= rem_convenios
            remessas.append({
                "cd_remessa": rem,
                "atendimentos": atendimentos,
                "num_atendimentos": len(atendimentos),
                "num_lancamentos": rem_lancamentos,
                "total": rem_total,
                "convenios": sorted(rem_convenios),
                "procedimentos": sorted(rem_procedimentos),
            })
        result.append({
            "nm_paciente": pac,
            "remessas": remessas,
            "num_remessas": len(remessas),
            "num_atendimentos": pac_atendimentos,
            "num_lancamentos": pac_lancamentos,
            "total": pac_total,
            "convenios": sorted(pac_convenios),
        })
    return result


def as_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("atendimentos", "items", "results", "contas", "dados", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    return []


def as_positive_int(value, default=1):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def as_int_or_zero(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def as_int_or_none(value):
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float_or_zero(value):
    text = str(value or "").strip()
    text = "".join(char for char in text if char.isdigit() or char in ",.-")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def as_float_or_none(value):
    if value in (None, ""):
        return None

    text = str(value).strip()
    text = "".join(char for char in text if char.isdigit() or char in ",.-")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")

    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def format_brl_input(value):
    if value in (None, ""):
        return ""

    try:
        amount = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return ""

    formatted = f"{amount:,.2f}"
    return f"R$ {formatted}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_api_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass

    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def bucket_reference_date(registro):
    return (
        parse_api_date(registro.get("dt_pagamento"))
        or parse_api_date(registro.get("data_criacao"))
        or parse_api_date(registro.get("dt_recurso"))
        or parse_api_date(registro.get("data_glosa"))
        or date.today()
    )


def age_bucket(registro):
    reference_date = bucket_reference_date(registro)
    days = max((date.today() - reference_date).days, 0)
    if days < 30:
        return "ate_30"
    if days < 60:
        return "ate_60"
    if days <= 90:
        return "ate_90"
    return "mais_90"


def valor_registro_recurso(registro):
    return as_float_or_zero(
        registro.get("valor_glosado")
        if registro.get("valor_glosado") not in (None, "")
        else registro.get("valor")
    )


def qtd_registro_recurso(registro):
    return as_float_or_zero(
        registro.get("qtd_glosada")
        if registro.get("qtd_glosada") not in (None, "")
        else 1
    )


def processo_card_key(registro):
    return (
        registro.get("processo_recurso")
        or registro.get("processo_controle_fatura_gab")
        or f"registro-{registro.get('id')}"
    )


def build_acompanhamento_rows(registros):
    rows = []
    for registro in registros:
        if not isinstance(registro, dict):
            continue
        if registro.get("sn_glosado") != "true":
            continue
        if not registro.get("processo_recurso"):
            continue

        row = dict(registro)
        row["paciente_label"] = (
            row.get("nm_paciente")
            or f"Paciente {row.get('codigo_paciente') or '-'}"
        )
        row["idade_bucket"] = age_bucket(row)
        row["idade_bucket_label"] = ACOMPANHAMENTO_BUCKETS[row["idade_bucket"]]
        row["qtd_recurso"] = qtd_registro_recurso(row)
        row["valor_recurso"] = valor_registro_recurso(row)
        row["valor_recurso_formatado"] = format_brl_input(row["valor_recurso"])
        row["valor_recebido_formatado"] = format_brl_input(
            row.get("valor_recebido")
        )
        row["dt_recebimento_input"] = format_api_date_input(
            row.get("dt_recebimento")
        )
        row["dt_recebimento_formatada"] = format_api_date(
            row.get("dt_recebimento")
        )
        rows.append(row)
    return rows


ACOMPANHAMENTO_BUCKETS = {
    "ate_30": "Até 30 dias",
    "ate_60": "Até 60 dias",
    "ate_90": "Até 90 dias",
    "mais_90": "Há +90 dias",
    "recebidas": "Glosas recebidas",
}


def unique_join(values):
    normalized = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return ", ".join(normalized) or "-"


def build_acompanhamento_cards(rows):
    grouped = {}
    for row in rows:
        key = processo_card_key(row)
        grouped.setdefault(key, []).append(row)

    cards = []
    for key, itens in grouped.items():
        all_received = all(item.get("dt_recebimento") for item in itens)
        oldest_item = min(itens, key=bucket_reference_date)
        bucket_key = "recebidas" if all_received else age_bucket(oldest_item)
        total = sum(item["valor_recurso"] for item in itens)
        qtd = sum(item["qtd_recurso"] for item in itens)
        reference_date = bucket_reference_date(oldest_item)
        cards.append(
            {
                "key": str(key),
                "bucket": bucket_key,
                "reference_date": reference_date.isoformat(),
                "ids": ",".join(str(item["id"]) for item in itens if item.get("id")),
                "processos_originais": unique_join(
                    item.get("processo_controle_fatura_gab") for item in itens
                ),
                "processo_recurso": unique_join(
                    item.get("processo_recurso") for item in itens
                ),
                "pacientes": unique_join(item.get("paciente_label") for item in itens),
                "convenios": unique_join(item.get("convenio") for item in itens),
                "qtd_total": qtd,
                "valor_total": total,
                "valor_total_formatado": format_brl_input(total),
                "itens": itens,
                "has_mini_table": len(itens) > 1,
            }
        )
    return cards


def build_kanban_columns(cards):
    columns = []
    for key, label in ACOMPANHAMENTO_BUCKETS.items():
        column_cards = [card for card in cards if card["bucket"] == key]
        valor_total = sum(card["valor_total"] for card in column_cards)
        columns.append(
            {
                "key": key,
                "label": label,
                "cards": column_cards,
                "valor_total": valor_total,
                "valor_total_formatado": format_brl_input(valor_total),
            }
        )
    return columns


def _glosa_match_key(item):
    return (
        str(as_int_or_zero(item.get("cd_remessa"))),
        str(as_int_or_zero(item.get("cd_atendimento"))),
        str(as_int_or_zero(item.get("cd_reg") or item.get("conta"))),
        str(item.get("cd_pro_fat") or item.get("procedimento") or ""),
        str(item.get("nr_guia") or item.get("cd_guia") or item.get("guia") or ""),
    )


def _prepare_registro_glosa(registro):
    prepared = dict(registro)
    qtd_glosada = registro.get("qtd_glosada")
    prepared["data_glosa_input"] = format_api_date_input(registro.get("data_glosa"))
    prepared["dt_recurso_input"] = format_api_date_input(registro.get("dt_recurso"))
    prepared["dt_pagamento_input"] = format_api_date_input(registro.get("dt_pagamento"))
    prepared["valor_glosado_input"] = format_brl_input(registro.get("valor_glosado"))
    try:
        prepared["qtd_glosada_input"] = int(float(str(qtd_glosada).replace(",", ".")))
    except (TypeError, ValueError):
        prepared["qtd_glosada_input"] = ""
    return prepared


def attach_registros_glosa(contas, filtros):
    if not contas:
        return

    params = {
        key: value
        for key, value in filtros.items()
        if key in {"cd_remessa", "cd_atendimento", "cd_reg", "tp_atendimento"} and value
    }
    params["limit"] = 5000
    payload = api_get(settings.API_REGISTRO_GLOSA_PATH, params)
    registros = payload.get("glosas", []) if isinstance(payload, dict) else []

    registros_por_linha = {}
    for registro in registros:
        if not isinstance(registro, dict):
            continue
        key = _glosa_match_key(registro)
        if key not in registros_por_linha:
            registros_por_linha[key] = _prepare_registro_glosa(registro)

    for conta in contas:
        if not isinstance(conta, dict):
            continue
        registro = registros_por_linha.get(_glosa_match_key(conta))
        if registro:
            conta["registro_glosa"] = registro
            conta["registro_glosa_id"] = registro.get("id")
            conta["registro_glosa_status"] = registro.get("sn_glosado")


def build_registro_glosa_payload(data):
    return {
        "codigo_paciente": as_int_or_zero(data.get("cd_paciente")),
        "nm_paciente": data.get("nm_paciente") or None,
        "cd_remessa": as_int_or_zero(data.get("cd_remessa")),
        "cd_atendimento": as_int_or_zero(data.get("cd_atendimento")),
        "conta": as_int_or_zero(data.get("cd_reg")),
        "cd_prestador": as_int_or_zero(data.get("cd_prestador")),
        "cd_convenio": as_int_or_zero(data.get("cd_convenio")),
        "tp_atendimento": data.get("tp_atendimento") or "",
        "procedimento": str(data.get("cd_pro_fat") or ""),
        "convenio": data.get("nm_convenio") or "",
        "guia": str(data.get("nr_guia") or data.get("cd_guia") or ""),
        "prestador": data.get("nm_prestador") or "",
        "data_atendimento": data.get("dt_atendimento")
        or data.get("dt_lancamento")
        or None,
        "valor": as_float_or_zero(data.get("vl_total_conta")),
        "sn_glosado": data.get("sn_glosado") or None,
        "processo_controle_fatura_gab": data.get("processo_controle_fatura_gab") or "",
        "processo_recurso": data.get("processo_recurso") or None,
        "data_glosa": data.get("data_glosa") or None,
        "motivo_glosa": data.get("motivo_glosa") or "",
        "descricao_glosa": data.get("descricao_glosa") or "",
        "qtd_glosada": as_int_or_none(data.get("qtd_glosada")),
        "valor_glosado": as_float_or_none(data.get("valor_glosado")),
        "dt_recurso": data.get("dt_recurso") or None,
        "dt_pagamento": data.get("dt_pagamento") or None,
    }


def normalize_flag(value):
    return str(value or "").strip().lower()


def is_active_registro(registro):
    return normalize_flag(registro.get("sn_ativo")) in {"true", "sim", "s", "1"}


def is_recurso_registro(registro):
    return normalize_flag(registro.get("sn_glosado")) in {"true", "sim", "s", "1"}


def is_acato_registro(registro):
    return normalize_flag(registro.get("sn_glosado")) in {
        "not",
        "false",
        "não",
        "nao",
        "n",
        "0",
    }


def registro_valor_glosado(registro):
    return as_float_or_zero(
        registro.get("valor_glosado")
        if registro.get("valor_glosado") not in (None, "")
        else registro.get("valor")
    )


def percent_value(part, total):
    if not total:
        return 0
    return round((part / total) * 100, 1)


def aging_days(registro):
    reference = (
        parse_api_date(registro.get("data_glosa"))
        or parse_api_date(registro.get("data_criacao"))
        or date.today()
    )
    return max((date.today() - reference).days, 0)


def aging_bucket_key(days):
    if days <= 7:
        return "0_7"
    if days <= 15:
        return "8_15"
    if days <= 30:
        return "16_30"
    if days <= 60:
        return "31_60"
    return "mais_60"


AGING_BUCKETS = {
    "0_7": "0 a 7 dias",
    "8_15": "8 a 15 dias",
    "16_30": "16 a 30 dias",
    "31_60": "31 a 60 dias",
    "mais_60": "Acima de 60 dias",
}


def month_key(value):
    parsed = parse_api_date(value)
    if not parsed:
        return "Sem data"
    return parsed.strftime("%Y-%m")


def month_label(key):
    if key == "Sem data":
        return key
    try:
        return datetime.strptime(key, "%Y-%m").strftime("%m/%Y")
    except ValueError:
        return key


def top_groups(rows, key_name, value_name, limit=6):
    groups = {}
    for row in rows:
        name = row.get(key_name) or "Não informado"
        current = groups.setdefault(name, {"label": name, "count": 0, "value": 0})
        current["count"] += 1
        current["value"] += as_float_or_zero(row.get(value_name))

    ordered = sorted(
        groups.values(),
        key=lambda item: (item["value"], item["count"]),
        reverse=True,
    )[:limit]
    max_value = max((item["value"] for item in ordered), default=0)
    for item in ordered:
        item["value_formatado"] = format_brl_input(item["value"])
        item["bar_width"] = percent_value(item["value"], max_value)
    return ordered


def top_count_groups(rows, key_name, limit=6):
    groups = {}
    for row in rows:
        name = row.get(key_name) or "Não informado"
        current = groups.setdefault(name, {"label": name, "count": 0, "value": 0})
        current["count"] += 1
        current["value"] += registro_valor_glosado(row)

    ordered = sorted(
        groups.values(),
        key=lambda item: (item["count"], item["value"]),
        reverse=True,
    )[:limit]
    max_count = max((item["count"] for item in ordered), default=0)
    for item in ordered:
        item["value_formatado"] = format_brl_input(item["value"])
        item["bar_width"] = percent_value(item["count"], max_count)
    return ordered


def normalize_lookup_text(value):
    return " ".join(str(value or "").strip().upper().split())


def build_prazos_convenio_lookup(convenios):
    lookup = {}
    for convenio in convenios or []:
        dias = as_positive_int(convenio.get("dias_para_recurso"), None)
        if dias is None:
            continue

        cd_convenio = convenio.get("cd_convenio")
        if cd_convenio not in (None, ""):
            lookup[f"cd:{cd_convenio}"] = dias

        nome = normalize_lookup_text(convenio.get("convenio"))
        if nome:
            lookup[f"nome:{nome}"] = dias
    return lookup


def prazo_recurso_registro(registro, prazos_lookup, prazo_padrao):
    cd_convenio = registro.get("cd_convenio")
    if cd_convenio not in (None, ""):
        prazo = prazos_lookup.get(f"cd:{cd_convenio}")
        if prazo is not None:
            return prazo

    nome = normalize_lookup_text(registro.get("convenio"))
    if nome:
        prazo = prazos_lookup.get(f"nome:{nome}")
        if prazo is not None:
            return prazo

    return prazo_padrao


def registro_tem_prazo_parametrizado(registro, prazos_lookup):
    cd_convenio = registro.get("cd_convenio")
    if cd_convenio not in (None, "") and f"cd:{cd_convenio}" in prazos_lookup:
        return True

    nome = normalize_lookup_text(registro.get("convenio"))
    return bool(nome and f"nome:{nome}" in prazos_lookup)


def build_dashboard_indicadores(registros, prazo_sla=10, prazos_convenio=None):
    prazos_lookup = build_prazos_convenio_lookup(prazos_convenio or [])
    rows = [registro for registro in registros if is_active_registro(registro)]
    recursos = [registro for registro in rows if is_recurso_registro(registro)]
    acatos = [registro for registro in rows if is_acato_registro(registro)]
    total_glosado = sum(registro_valor_glosado(registro) for registro in rows)
    total_recursos_valor = sum(
        registro_valor_glosado(registro) for registro in recursos
    )
    total_acatos_valor = sum(registro_valor_glosado(registro) for registro in acatos)
    total_recebido = sum(
        as_float_or_zero(registro.get("valor_recebido"))
        for registro in rows
        if registro.get("dt_recebimento")
    )

    recursos_com_sucesso = [
        registro
        for registro in recursos
        if as_float_or_zero(registro.get("valor_recebido")) > 0
    ]
    glosas_sem_processo = [
        registro
        for registro in recursos
        if not registro.get("processo_recurso") or not registro.get("dt_recurso")
    ]
    sem_recuperacao = [
        registro
        for registro in recursos
        if as_float_or_zero(registro.get("valor_recebido")) <= 0
    ]

    aging = []
    for key, label in AGING_BUCKETS.items():
        bucket_rows = [
            registro for registro in rows if aging_bucket_key(aging_days(registro)) == key
        ]
        value = sum(registro_valor_glosado(registro) for registro in bucket_rows)
        aging.append(
            {
                "key": key,
                "label": label,
                "count": len(bucket_rows),
                "value": value,
                "value_formatado": format_brl_input(value),
            }
        )
    max_aging = max((item["count"] for item in aging), default=0)
    for item in aging:
        item["bar_width"] = percent_value(item["count"], max_aging)

    sla_dentro = 0
    sla_fora = 0
    sla_sem_atendimento = 0
    sla_sem_parametro = 0
    for registro in recursos:
        data_atendimento = parse_api_date(registro.get("data_atendimento"))
        if data_atendimento is None:
            sla_sem_atendimento += 1
        data_inicio = (
            data_atendimento
            or parse_api_date(registro.get("data_glosa"))
            or parse_api_date(registro.get("data_criacao"))
            or date.today()
        )
        data_tratativa = parse_api_date(registro.get("dt_recurso")) or date.today()
        prazo_registro = prazo_recurso_registro(registro, prazos_lookup, prazo_sla)
        if not registro_tem_prazo_parametrizado(registro, prazos_lookup):
            sla_sem_parametro += 1
        dias_tratativa = max((data_tratativa - data_inicio).days, 0)
        if dias_tratativa <= prazo_registro:
            sla_dentro += 1
        else:
            sla_fora += 1

    mensal = {}
    for registro in rows:
        key = month_key(registro.get("data_glosa"))
        current = mensal.setdefault(
            key,
            {
                "label": month_label(key),
                "count": 0,
                "value": 0,
                "recursos": 0,
                "acatos": 0,
            },
        )
        current["count"] += 1
        current["value"] += registro_valor_glosado(registro)
        if is_recurso_registro(registro):
            current["recursos"] += 1
        elif is_acato_registro(registro):
            current["acatos"] += 1

    volume_mensal = [
        mensal[key]
        for key in sorted(
            mensal,
            key=lambda item: "0000-00" if item == "Sem data" else item,
        )
    ][-8:]
    max_volume = max((item["value"] for item in volume_mensal), default=0)
    for item in volume_mensal:
        item["value_formatado"] = format_brl_input(item["value"])
        item["bar_width"] = percent_value(item["value"], max_volume)

    recuperado_convenio = top_groups(
        [
            registro
            for registro in rows
            if registro.get("dt_recebimento")
            and as_float_or_zero(registro.get("valor_recebido")) > 0
        ],
        "convenio",
        "valor_recebido",
    )
    motivo_top = top_groups(rows, "motivo_glosa", "valor_glosado")
    aberto_top = sorted(
        glosas_sem_processo,
        key=lambda registro: aging_days(registro),
        reverse=True,
    )[:6]
    aberto_top = [
        {
            "processo": registro.get("processo_controle_fatura_gab") or "-",
            "convenio": registro.get("convenio") or "-",
            "motivo": registro.get("motivo_glosa") or "-",
            "aging": aging_days(registro),
            "valor": format_brl_input(registro_valor_glosado(registro)),
        }
        for registro in aberto_top
    ]

    return {
        "kpis": {
            "total_registros": len(rows),
            "total_recursos": len(recursos),
            "total_acatos": len(acatos),
            "total_glosado": total_glosado,
            "total_glosado_formatado": format_brl_input(total_glosado),
            "total_recursos_valor": total_recursos_valor,
            "total_recursos_valor_formatado": format_brl_input(
                total_recursos_valor
            ),
            "total_acatos_valor": total_acatos_valor,
            "total_acatos_valor_formatado": format_brl_input(total_acatos_valor),
            "total_recebido": total_recebido,
            "total_recebido_formatado": format_brl_input(total_recebido),
            "glosas_sem_processo": len(glosas_sem_processo),
            "sem_recuperacao": len(sem_recuperacao),
            "taxa_recurso": percent_value(len(recursos), len(rows)),
            "taxa_sucesso_qtd": percent_value(len(recursos_com_sucesso), len(recursos)),
            "taxa_sucesso_financeira": percent_value(
                total_recebido,
                total_recursos_valor,
            ),
        },
        "prazo_sla": prazo_sla,
        "prazos": {
            "configurados": len(
                [
                    convenio
                    for convenio in (prazos_convenio or [])
                    if convenio.get("dias_para_recurso") not in (None, "")
                ]
            ),
            "fallback": prazo_sla,
        },
        "sla": {
            "dentro": sla_dentro,
            "fora": sla_fora,
            "total": len(recursos),
            "dentro_pct": percent_value(sla_dentro, len(recursos)),
            "fora_pct": percent_value(sla_fora, len(recursos)),
            "sem_atendimento": sla_sem_atendimento,
            "sem_parametro": sla_sem_parametro,
        },
        "aging": aging,
        "volume_mensal": volume_mensal,
        "volume_convenio": top_count_groups(rows, "convenio"),
        "volume_prestador": top_count_groups(rows, "prestador"),
        "volume_tipo_atendimento": top_count_groups(rows, "tp_atendimento"),
        "recuperado_convenio": recuperado_convenio,
        "motivo_top": motivo_top,
        "aberto_top": aberto_top,
    }


def dashboard(request):
    prazo_sla = as_positive_int(request.GET.get("sla"), 10)
    prazos_convenio = []
    try:
        prazos_payload = api_get(PRAZOS_RECURSO_CONVENIO_PATH)
        prazos_convenio = prazos_payload.get("convenios", [])
    except ApiError as exc:
        messages.warning(request, format_api_error(exc, "Prazos por convênio"))

    try:
        payload = api_get(settings.API_REGISTRO_GLOSA_PATH, {"limit": 5000})
        registros = payload.get("glosas", []) if isinstance(payload, dict) else []
        indicadores = build_dashboard_indicadores(
            registros,
            prazo_sla,
            prazos_convenio,
        )
    except ApiError as exc:
        indicadores = build_dashboard_indicadores([], prazo_sla, prazos_convenio)
        messages.error(request, format_api_error(exc, "Indicadores"))
    return render(request, "dashboard.html", {"indicadores": indicadores})


@require_http_methods(["GET", "POST"])
def prazos_recurso_convenio(request):
    if request.method == "POST":
        payload = []
        errors = []
        for cd_convenio in request.POST.getlist("cd_convenio"):
            convenio = request.POST.get(f"convenio_{cd_convenio}", "").strip()
            dias_raw = request.POST.get(f"dias_para_recurso_{cd_convenio}", "").strip()
            if not dias_raw:
                continue

            dias = as_positive_int(dias_raw, None)
            if dias is None:
                errors.append(convenio or cd_convenio)
                continue

            payload.append(
                {
                    "cd_convenio": int(cd_convenio),
                    "convenio": convenio,
                    "dias_para_recurso": dias,
                }
            )

        if errors:
            messages.error(
                request,
                "Informe uma quantidade de dias válida para: "
                + ", ".join(errors),
            )
        else:
            try:
                api_put(PRAZOS_RECURSO_CONVENIO_PATH, payload)
                messages.success(request, "Prazos por convênio atualizados.")
                return redirect("prazos_recurso_convenio")
            except ApiError as exc:
                messages.error(request, format_api_error(exc, "Prazos por convênio"))

    try:
        payload = api_get(PRAZOS_RECURSO_CONVENIO_PATH)
        convenios = payload.get("convenios", [])
    except ApiError as exc:
        convenios = []
        messages.error(request, format_api_error(exc, "Prazos por convênio"))

    resumo = {
        "convenios": len(convenios),
        "configurados": sum(
            1 for convenio in convenios if convenio.get("dias_para_recurso") not in (None, "")
        ),
    }
    return render(
        request,
        "prazos_recurso_convenio.html",
        {
            "convenios": convenios,
            "resumo": resumo,
        },
    )


@require_http_methods(["GET", "POST"])
def conta_atendimento(request):
    if request.method == "POST":
        registro_id = request.POST.get("registro_glosa_id")
        form_action = request.POST.get("form_action") or "salvar"
        try:
            if form_action == "desfazer" and registro_id:
                api_delete(f"{settings.API_REGISTRO_GLOSA_PATH}/{registro_id}")
                return modal_action_response(
                    request,
                    "Registro desfeito a partir da conta selecionada.",
                    "error",
                )

            payload = build_registro_glosa_payload(request.POST)
            is_acatar = payload.get("sn_glosado") == "not"
            if registro_id:
                api_payload = api_put(f"{settings.API_REGISTRO_GLOSA_PATH}/{registro_id}", payload)
                success_message = (
                    "Acato atualizado a partir da conta selecionada."
                    if is_acatar
                    else "Glosa atualizada a partir da conta selecionada."
                )
                return modal_action_response(
                    request,
                    success_message,
                    "warning",
                    api_payload=api_payload,
                )
            else:
                api_payload = api_post(settings.API_REGISTRO_GLOSA_PATH, payload)
                success_message = (
                    "Acato registrado a partir da conta selecionada."
                    if is_acatar
                    else "Glosa registrada a partir da conta selecionada."
                )
                return modal_action_response(
                    request,
                    success_message,
                    "success",
                    api_payload=api_payload,
                )
        except ApiError as exc:
            payload = build_registro_glosa_payload(request.POST)
            is_acatar = payload.get("sn_glosado") == "not"
            action_name = "acato" if is_acatar else "glosa"
            if form_action == "desfazer":
                error_message = f"Falha ao desfazer registro: {exc}"
            else:
                error_message = f"Falha ao salvar {action_name}: {exc}"
            return modal_action_response(
                request,
                error_message,
                "error",
                status=400,
            )

    if request.method == "GET" and request.GET and is_browser_reload(request):
        return redirect(request.path)

    filtros = request.GET.dict()
    filtros.pop("_modal_action", None)
    filtros.pop("limit", None)
    filtros.pop("offset", None)
    page = as_positive_int(filtros.pop("page", None), 1)
    limit = PATIENTS_PER_PAGE
    offset = (page - 1) * limit
    api_filtros = {k: v for k, v in filtros.items() if v}
    api_filtros["limit"] = limit
    api_filtros["offset"] = offset
    consulta_indisponivel = False
    total_pacientes = 0
    tiss_motivos = []
    try:
        payload_tiss = api_get(settings.API_TISS_PATH, {"limit": 600})
        if isinstance(payload_tiss, dict):
            tiss_motivos = payload_tiss.get("itens", [])
    except ApiError as exc:
        messages.error(request, format_api_error(exc, "Consulta TISS"))

    try:
        if request.GET:
            payload = api_get(settings.API_CONTA_ATENDIMENTO_PATH, api_filtros)
            contas = as_list(payload)
            if isinstance(payload, dict):
                total_pacientes = as_int_or_zero(payload.get("total"))
                limit = as_positive_int(payload.get("limit"), PATIENTS_PER_PAGE)
                offset = as_int_or_zero(payload.get("offset"))
            else:
                total_pacientes = len(_group_contas(contas))
            try:
                attach_registros_glosa(contas, api_filtros)
            except ApiError as exc:
                messages.error(
                    request,
                    format_api_error(exc, "Consulta de glosas registradas"),
                )
        else:
            contas = []
    except ApiError as exc:
        contas = []
        if is_service_unavailable_error(exc):
            consulta_indisponivel = True
        else:
            messages.error(request, format_api_error(exc, "Consulta de conta/atendimento"))
    for conta in contas:
        if isinstance(conta, dict):
            conta["dt_atendimento_formatada"] = format_api_date(
                conta.get("dt_atendimento")
            )
            conta["dt_alta_formatada"] = format_api_date(
                conta.get("dt_alta")
            )
            conta["hr_lancamento_formatada"] = format_lancamento_datetime(
                conta.get("dt_lancamento"),
                conta.get("hr_lancamento"),
            )
    grupos = _group_contas(contas)
    if request.GET and not total_pacientes:
        total_pacientes = len(grupos)

    base_query = {k: v for k, v in filtros.items() if v}
    total_pages = max(ceil(total_pacientes / PATIENTS_PER_PAGE), 1)
    if request.GET and page > total_pages:
        return redirect(
            f"{request.path}?{urlencode({**base_query, 'page': total_pages})}"
        )

    page = min(page, total_pages)
    grupos_pagina = grupos
    page_options = [
        {"number": number, "selected": number == page}
        for number in range(1, total_pages + 1)
    ]
    pagination = {
        "page": page,
        "total_pages": total_pages,
        "page_options": page_options,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "previous_url": (
            f"?{urlencode({**base_query, 'page': page - 1})}"
            if page > 1
            else ""
        ),
        "next_url": (
            f"?{urlencode({**base_query, 'page': page + 1})}"
            if page < total_pages
            else ""
        ),
        "start": offset + 1 if grupos and total_pacientes else 0,
        "end": min(offset + len(grupos), total_pacientes),
        "total": total_pacientes,
        "query": base_query,
    }
    resumo = {
        "agrupamentos": len(grupos),
        "pacientes": len(grupos),
        "atendimentos": sum(g.get("num_atendimentos", 0) for g in grupos),
        "valor_total": sum(g.get("total", 0) for g in grupos),
    }
    return render(
        request,
        "conta_atendimento.html",
        {
            "grupos": grupos_pagina,
            "filtros": filtros,
            "resumo": resumo,
            "pagination": pagination,
            "consulta_indisponivel": consulta_indisponivel,
            "tipos_atendimento": TIPOS_ATENDIMENTO,
            "tiss_motivos": tiss_motivos,
        },
    )


@require_http_methods(["GET", "POST"])
def acompanhamento(request):
    if request.method == "POST":
        registro_ids = [
            item.strip()
            for item in (request.POST.get("registro_ids") or "").split(",")
            if item.strip()
        ]
        payload = {
            "dt_recebimento": request.POST.get("dt_recebimento") or None,
            "valor_recebido": as_float_or_zero(request.POST.get("valor_recebido")),
            "observacao_recebimento": (
                request.POST.get("observacao_recebimento") or None
            ),
        }
        if not registro_ids:
            messages.error(request, "Nenhum registro selecionado para recebimento.")
            return redirect("acompanhamento")

        try:
            for registro_id in registro_ids:
                api_patch(
                    f"{settings.API_REGISTRO_GLOSA_PATH}/{registro_id}/recebimento",
                    payload,
                )
            messages.success(
                request,
                "Recebimento registrado para o processo selecionado.",
            )
        except ApiError as exc:
            messages.error(request, format_api_error(exc, "Recebimento de glosa"))

        redirect_url = request.get_full_path()
        if request.POST.get("next"):
            redirect_url = request.POST["next"]
        return redirect(redirect_url)

    filtros = request.GET.dict()
    modo = filtros.pop("modo", "kanban")
    faixa = filtros.pop("faixa", "")
    api_filtros = {
        key: value
        for key, value in filtros.items()
        if key
        in {
            "cd_remessa",
            "cd_atendimento",
            "cd_reg",
            "nm_convenio",
            "nm_paciente",
            "tp_atendimento",
        }
        and value
    }
    api_filtros["limit"] = 5000

    try:
        payload = api_get(settings.API_REGISTRO_GLOSA_PATH, api_filtros)
        registros = payload.get("glosas", []) if isinstance(payload, dict) else []
    except ApiError as exc:
        registros = []
        messages.error(request, format_api_error(exc, "Acompanhamento"))

    rows = build_acompanhamento_rows(registros)
    cards = build_acompanhamento_cards(rows)
    kanban_columns = build_kanban_columns(cards)
    if faixa:
        rows_filtradas = [
            row
            for row in rows
            if ("recebidas" if row.get("dt_recebimento") else row["idade_bucket"])
            == faixa
        ]
    else:
        rows_filtradas = rows

    cards_filtrados = build_acompanhamento_cards(rows_filtradas)
    resumo = {
        "processos": len(cards_filtrados),
        "registros": len(rows_filtradas),
        "valor_total": sum(row["valor_recurso"] for row in rows_filtradas),
        "recebidos": sum(
            1 for row in rows_filtradas if row.get("dt_recebimento")
        ),
    }

    return render(
        request,
        "acompanhamento.html",
        {
            "filtros": filtros,
            "modo": modo if modo in {"kanban", "tabela"} else "kanban",
            "faixa": faixa,
            "faixas": ACOMPANHAMENTO_BUCKETS,
            "kanban_columns": kanban_columns,
            "rows": rows_filtradas,
            "resumo": resumo,
            "tipos_atendimento": TIPOS_ATENDIMENTO,
            "current_full_path": request.get_full_path(),
        },
    )


def glosas(request):
    try:
        registros = api_get("/glosas", request.GET.dict())
    except ApiError as exc:
        registros = []
        messages.error(request, format_api_error(exc, "Glosas"))
    return render(request, "glosas.html", {"glosas": registros})


@require_http_methods(["GET", "POST"])
def remessas(request):
    if request.method == "POST":
        try:
            api_post("/remessas", request.POST.dict())
            messages.success(request, "Remessa enviada para cadastro.")
            return redirect("remessas")
        except ApiError as exc:
            messages.error(request, format_api_error(exc, "Cadastro de remessa"))
    try:
        registros = api_get("/remessas")
    except ApiError as exc:
        registros = []
        messages.error(request, format_api_error(exc, "Remessas"))
    return render(request, "remessas.html", {"remessas": registros})


@require_http_methods(["GET", "POST"])
def recursos(request):
    if request.method == "POST":
        try:
            api_post("/recursos", request.POST.dict())
            messages.success(request, "Recurso enviado para cadastro.")
            return redirect("recursos")
        except ApiError as exc:
            messages.error(request, format_api_error(exc, "Cadastro de recurso"))
    try:
        registros = api_get("/recursos")
    except ApiError as exc:
        registros = []
        messages.error(request, format_api_error(exc, "Recursos"))
    return render(request, "recursos.html", {"recursos": registros})


@require_http_methods(["GET", "POST"])
def recebimentos(request):
    if request.method == "POST":
        try:
            api_post("/recebimentos", request.POST.dict())
            messages.success(request, "Recebimento enviado para cadastro.")
            return redirect("recebimentos")
        except ApiError as exc:
            messages.error(request, format_api_error(exc, "Cadastro de recebimento"))
    try:
        registros = api_get("/recebimentos")
    except ApiError as exc:
        registros = []
        messages.error(request, format_api_error(exc, "Recebimentos"))
    return render(request, "recebimentos.html", {"recebimentos": registros})


@require_http_methods(["GET", "POST"])
def conciliacao(request):
    if request.method == "POST":
        try:
            divergencias = api_post("/conciliacao/executar", {})
            messages.success(request, "Conciliacao executada.")
            return render(request, "conciliacao.html", {"divergencias": divergencias})
        except ApiError as exc:
            messages.error(request, format_api_error(exc, "Execucao da conciliacao"))
    try:
        divergencias = api_get("/conciliacao/divergencias")
    except ApiError as exc:
        divergencias = []
        messages.error(request, format_api_error(exc, "Conciliacao"))
    return render(request, "conciliacao.html", {"divergencias": divergencias})
