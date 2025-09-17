"""Herramientas reutilizables para los viewsets del módulo ``core``.

Este módulo define un mixin que provee el endpoint ``get_related`` solicitado
en el enunciado. La implementación se concentra aquí para que todos los
``ViewSet`` puedan heredarla sin duplicar código ni lógica de parsing.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Set, Tuple, Type

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response


@dataclass
class _JoinSpec:
    """Representa una ruta de join solicitada por el cliente.

    ``lookup`` es el nombre de la relación en formato ``__`` (compatible con
    ``select_related``/``prefetch_related``) y ``segments`` la lista de sus
    componentes en formato de atributo (``brand`` o ``items`` por ejemplo).
    ``use_select_related`` indica si se puede resolver únicamente con joins a
    relaciones de cardinalidad 1 (``ForeignKey``/``OneToOne``). En caso
    contrario se usará ``prefetch_related`` para evitar consultas N+1.
    """

    lookup: str
    segments: List[str]
    use_select_related: bool


class RelatedQueryMixin:
    """Mixin que implementa el endpoint GET ``get_related``.

    El endpoint permite:

    * Navegar relaciones directas e inversas utilizando el parámetro ``join``.
    * Limitar los campos devueltos por modelo mediante ``fields[modelo]``.
    * Aplicar filtros dinámicos usando ``filter[atributo]=valor``.

    Cada ``ViewSet`` que herede este mixin dispondrá de la ruta
    ``/<recurso>/related/`` registrada automáticamente por DRF.
    """

    join_param = "join"
    filter_prefix = "filter["
    fields_prefix = "fields["
    ordering_param = "ordering"
    distinct_param = "distinct"
    related_max_join_depth = 3
    related_allowed_joins: Sequence[str] = ()

    @action(detail=False, methods=["get"], url_path="related")
    def get_related(self, request: Request, *args, **kwargs) -> Response:
        """Resuelve la consulta dinámica solicitada por el cliente.

        La lógica principal se compone de varios pasos encadenados:

        1. Interpretar filtros dinámicos ``filter[foo]=bar``.
        2. Validar y aplicar los joins solicitados, respetando profundidad y
           lista blanca por recurso.
        3. Determinar ordenamiento y ``distinct`` cuando se soliciten.
        4. Serializar la respuesta respetando los campos elegidos y la
           paginación configurada en el proyecto.
        """

        started_at = perf_counter()
        queryset = self.filter_queryset(self.get_queryset())
        base_model = queryset.model

        try:
            filters, applied_filters = self._parse_filters(request, base_model)
        except ValueError as exc:  # pragma: no cover - validación defensiva
            raise ValidationError(str(exc))
        if filters:
            queryset = queryset.filter(**filters)

        try:
            join_specs = self._parse_joins(request, base_model)
        except ValueError as exc:
            raise ValidationError(str(exc))
        if join_specs.select_related:
            queryset = queryset.select_related(*join_specs.select_related)
        if join_specs.prefetch_related:
            queryset = queryset.prefetch_related(*join_specs.prefetch_related)

        try:
            ordering_fields, ordering_meta = self._parse_ordering(request, base_model)
        except ValueError as exc:  # pragma: no cover - validación defensiva
            raise ValidationError(str(exc))
        if ordering_fields:
            queryset = queryset.order_by(*ordering_fields)
        distinct = self._parse_distinct(request)
        if distinct:
            queryset = queryset.distinct()

        try:
            field_map = self._parse_fields(request, join_specs.included_models)
        except ValueError as exc:  # pragma: no cover - validación defensiva
            raise ValidationError(str(exc))

        page = self.paginate_queryset(queryset)
        if page is None:
            page_objects = list(queryset)
        else:
            page_objects = list(page)

        data = [
            self._serialize_instance(
                instance=obj,
                model=obj.__class__,
                join_tree=join_specs.join_tree,
                field_map=field_map,
            )
            for obj in page_objects
        ]

        elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
        serialized_filters = {
            key: [self._serialize_value(item) for item in value]
            if isinstance(value, list)
            else self._serialize_value(value)
            for key, value in applied_filters.items()
        }
        selected_fields_meta = self._build_selected_fields_meta(
            join_specs.included_models, field_map
        )
        meta = {
            "applied_filters": serialized_filters,
            "applied_joins": join_specs.applied_joins,
            "selected_fields": selected_fields_meta,
            "ordering": ordering_meta,
            "distinct": distinct,
            "query_time_ms": elapsed_ms,
            "warnings": [],
        }

        if page is not None:
            response = self.get_paginated_response(data)
            response.data["meta"] = meta
            return response

        return Response(
            {
                "count": len(data),
                "next": None,
                "previous": None,
                "results": data,
                "meta": meta,
            }
        )

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------
    def _parse_filters(
        self, request: Request, base_model: Type[models.Model]
    ) -> Tuple[Dict[str, object], Dict[str, object]]:
        """Extrae y normaliza los filtros ``filter[llave]=valor`` de la query."""

        filters: Dict[str, object] = {}
        applied: Dict[str, object] = {}
        for key, values in request.query_params.lists():
            if not key.startswith(self.filter_prefix) or not key.endswith("]"):
                continue

            lookup = key[len(self.filter_prefix) : -1].replace(".", "__").strip()
            if not lookup:
                continue

            field, operator = self._resolve_lookup(base_model, lookup)
            coerced_values = [self._coerce_filter_value(value, field) for value in values]

            if len(coerced_values) > 1 and operator is None:
                lookup_key = f"{lookup}__in"
                filters[lookup_key] = coerced_values
                applied[lookup_key] = coerced_values
            elif len(coerced_values) == 1:
                filters[lookup] = coerced_values[0]
                applied[lookup] = coerced_values[0]
            else:
                filters[lookup] = coerced_values
                applied[lookup] = coerced_values

        return filters, applied

    @dataclass
    class _JoinParsingResult:
        select_related: List[str]
        prefetch_related: List[str]
        join_tree: MutableMapping[str, dict]
        included_models: Dict[str, Type[models.Model]]
        applied_joins: List[str]

    def _parse_joins(
        self, request: Request, base_model: Type[models.Model]
    ) -> "RelatedQueryMixin._JoinParsingResult":
        """Interpreta el parámetro ``join`` y decide la estrategia de carga."""

        raw_values = request.query_params.getlist(self.join_param)
        join_entries: List[str] = []
        for raw in raw_values:
            for item in raw.split(","):
                item = item.strip()
                if item:
                    join_entries.append(item)

        allowed_paths = self._get_allowed_join_paths()
        if join_entries and not allowed_paths:
            raise ValueError("No hay joins habilitados para este recurso")
        select_related: List[str] = []
        prefetch_related: List[str] = []
        join_tree: MutableMapping[str, dict] = defaultdict(dict)
        included_models: Dict[str, Type[models.Model]] = {
            base_model._meta.model_name: base_model,
        }
        applied_joins: List[str] = []

        for entry in join_entries:
            spec = self._build_join_spec(entry, base_model, allowed_paths)
            if not spec:
                continue

            if spec.use_select_related:
                select_related.append(spec.lookup)
            else:
                prefetch_related.append(spec.lookup)

            self._inject_join_path(join_tree, spec.segments)
            applied_joins.append(spec.lookup.replace("__", "."))

            # Registrar cada modelo involucrado para que pueda limitar sus campos
            current_model = base_model
            for segment in spec.segments:
                field = self._get_relation_field(current_model, segment)
                current_model = field.related_model
                included_models[current_model._meta.model_name] = current_model

        return self._JoinParsingResult(
            select_related=list(dict.fromkeys(select_related)),
            prefetch_related=list(dict.fromkeys(prefetch_related)),
            join_tree=join_tree,
            included_models=included_models,
            applied_joins=list(dict.fromkeys(applied_joins)),
        )

    def _build_join_spec(
        self,
        entry: str,
        base_model: Type[models.Model],
        allowed_paths: Set[Tuple[str, ...]],
    ) -> Optional[_JoinSpec]:
        """Convierte ``brand.products`` o ``brand__products`` en un ``_JoinSpec``."""

        normalized = entry.replace(".", "__")
        segments = tuple(segment for segment in normalized.split("__") if segment)
        if not segments:
            return None

        if len(segments) > self.related_max_join_depth:
            raise ValueError(
                f"La ruta '{entry}' supera la profundidad máxima de {self.related_max_join_depth} relaciones"
            )

        if allowed_paths and segments not in allowed_paths:
            raise ValueError(
                f"La ruta de join '{entry}' no está permitida para este recurso"
            )

        current_model = base_model
        use_select_related = True
        for segment in segments:
            field = self._get_relation_field(current_model, segment)
            # Para relaciones de colección necesitamos ``prefetch_related``
            if getattr(field, "one_to_many", False) or getattr(field, "many_to_many", False):
                use_select_related = False
            current_model = field.related_model

        lookup = "__".join(segments)
        return _JoinSpec(lookup=lookup, segments=list(segments), use_select_related=use_select_related)

    def _inject_join_path(self, tree: MutableMapping[str, dict], segments: Iterable[str]) -> None:
        """Construye un árbol anidado con las relaciones solicitadas."""

        if not segments:
            return

        head, *tail = segments
        subtree = tree.setdefault(head, {})
        if tail:
            self._inject_join_path(subtree, tail)

    def _get_allowed_join_paths(self) -> Set[Tuple[str, ...]]:
        """Normaliza la lista blanca de joins configurada en el ViewSet."""

        normalized: Set[Tuple[str, ...]] = set()
        for raw_path in getattr(self, "related_allowed_joins", ()):
            normalized_path = raw_path.replace(".", "__")
            segments = tuple(segment for segment in normalized_path.split("__") if segment)
            if segments:
                normalized.add(segments)
        return normalized

    def _parse_fields(
        self,
        request: Request,
        included_models: Dict[str, Type[models.Model]],
    ) -> Dict[str, List[str]]:
        """Lee los parámetros ``fields[modelo]`` y devuelve un mapa por modelo."""

        field_map: Dict[str, List[str]] = {}
        for key, values in request.query_params.lists():
            if not key.startswith(self.fields_prefix) or not key.endswith("]"):
                continue

            model_label = key[len(self.fields_prefix) : -1].strip().lower()
            if not model_label or model_label not in included_models:
                continue

            model = included_models[model_label]
            fields: List[str] = []
            for value in values:
                for item in value.split(","):
                    field_name = item.strip()
                    if not field_name:
                        continue
                    self._ensure_model_field_exists(model, field_name)
                    fields.append(field_name)

            if fields:
                field_map[model_label] = fields

        return field_map

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------
    def _serialize_instance(
        self,
        instance: models.Model,
        model: Type[models.Model],
        join_tree: MutableMapping[str, dict],
        field_map: Dict[str, List[str]],
    ) -> Dict[str, object]:
        """Serializa un objeto y sus relaciones según el árbol de joins."""

        model_label = model._meta.model_name
        selected_fields = field_map.get(model_label)
        if not selected_fields:
            selected_fields = [field.name for field in model._meta.fields]

        payload: Dict[str, object] = {}
        for field_name in selected_fields:
            value = getattr(instance, field_name, None)
            payload[field_name] = self._serialize_value(value)

        for relation_name, subtree in join_tree.items():
            field = self._get_relation_field(model, relation_name)
            if field.one_to_many or field.many_to_many:
                manager = getattr(instance, relation_name)
                payload[relation_name] = [
                    self._serialize_instance(child, field.related_model, subtree, field_map)
                    for child in manager.all()
                ]
            else:
                try:
                    related = getattr(instance, relation_name)
                except field.related_model.DoesNotExist:  # type: ignore[attr-defined]
                    related = None

                if related is None:
                    payload[relation_name] = None
                else:
                    payload[relation_name] = self._serialize_instance(
                        related,
                        field.related_model,
                        subtree,
                        field_map,
                    )

        return payload

    def _serialize_value(self, value: object) -> object:
        """Normaliza valores para que sean serializables por JSONRenderer."""

        if isinstance(value, models.Model):
            return value.pk
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date, time, timedelta)):
            return value.isoformat() if hasattr(value, "isoformat") else str(value)
        return value

    # ------------------------------------------------------------------
    # Utilidades varias
    # ------------------------------------------------------------------
    def _parse_ordering(
        self, request: Request, base_model: Type[models.Model]
    ) -> Tuple[List[str], List[str]]:
        """Procesa el parámetro ``ordering`` (coma separada)."""

        raw = request.query_params.get(self.ordering_param, "")
        if not raw:
            return [], []

        ordering_fields: List[str] = []
        ordering_meta: List[str] = []
        for chunk in raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue

            descending = chunk.startswith("-")
            lookup = chunk[1:] if descending else chunk
            lookup = lookup.replace(".", "__").strip()
            if not lookup:
                continue

            self._resolve_lookup(base_model, lookup)
            prefix = "-" if descending else ""
            ordering_fields.append(f"{prefix}{lookup}")
            ordering_meta.append(f"{prefix}{lookup.replace('__', '.')}")

        return ordering_fields, ordering_meta

    def _parse_distinct(self, request: Request) -> bool:
        """Interpreta ``distinct=true`` como booleano."""

        raw = request.query_params.get(self.distinct_param)
        if raw is None:
            return False
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _build_selected_fields_meta(
        self,
        included_models: Dict[str, Type[models.Model]],
        field_map: Dict[str, List[str]],
    ) -> Dict[str, List[str]]:
        """Informa qué campos quedaron seleccionados para cada modelo."""

        meta: Dict[str, List[str]] = {}
        for label, _model in included_models.items():
            if label in field_map:
                meta[label] = field_map[label]
            else:
                meta[label] = ["*"]
        return meta

    def _get_relation_field(self, model: Type[models.Model], name: str) -> models.Field:
        """Obtiene la definición de una relación y valida que exista."""

        try:
            field = model._meta.get_field(name)
        except models.FieldDoesNotExist as exc:  # pragma: no cover - validación defensiva
            raise ValueError(f"La relación '{name}' no existe en {model.__name__}") from exc

        if not field.is_relation:
            raise ValueError(
                f"El atributo '{name}' de {model.__name__} no es una relación válida para 'join'"
            )

        return field

    def _ensure_model_field_exists(self, model: Type[models.Model], name: str) -> None:
        """Valida que ``name`` sea un campo o relación del modelo."""

        try:
            model._meta.get_field(name)
        except models.FieldDoesNotExist as exc:  # pragma: no cover - validación defensiva
            raise ValueError(
                f"El modelo {model.__name__} no posee un campo o relación llamado '{name}'"
            ) from exc

    def _resolve_lookup(
        self, base_model: Type[models.Model], lookup: str
    ) -> Tuple[models.Field, Optional[str]]:
        """Localiza el campo final y el operador (si lo hubiera) de un lookup."""

        segments = [segment for segment in lookup.split("__") if segment]
        if not segments:
            raise ValueError("El parámetro de filtro no puede estar vacío")

        model = base_model
        field: Optional[models.Field] = None
        operator: Optional[str] = None
        for index, segment in enumerate(segments):
            try:
                candidate = model._meta.get_field(segment)
            except models.FieldDoesNotExist as exc:
                if field is None:
                    raise ValueError(
                        f"El modelo {model.__name__} no posee el atributo '{segment}' en el lookup '{lookup}'"
                    ) from exc
                operator = "__".join(segments[index:])
                break

            actual_field = getattr(candidate, "field", candidate)
            field = actual_field

            if getattr(candidate, "is_relation", False) and getattr(candidate, "related_model", None):
                model = candidate.related_model

            if index == len(segments) - 1:
                operator = None

        if field is None:
            raise ValueError(f"No fue posible resolver el lookup '{lookup}'")

        return field, operator

    def _coerce_filter_value(self, value: str, field: Optional[models.Field]) -> Any:
        """Intenta castear valores hacia el tipo Python esperado por el campo."""

        if field is None:
            return value

        target_field: Optional[models.Field] = field
        if hasattr(field, "target_field") and getattr(field, "target_field", None):
            target_field = field.target_field  # ForeignKey/OneToOne target

        try:
            assert target_field is not None
            return target_field.to_python(value)
        except (AssertionError, TypeError, ValueError, ValidationError, DjangoValidationError):
            lowered = value.strip().lower()
            if lowered in {"true", "false"}:
                return lowered == "true"
            try:
                return int(value)
            except (TypeError, ValueError):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return value