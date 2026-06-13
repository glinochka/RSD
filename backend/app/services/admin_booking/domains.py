"""Domain registry for crm_admin template subdomains.

Each entry describes a booking subdomain (beauty salon, dental clinic, etc.)
and controls UI hints, staff/resource terminology, and LLM prompt context.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainConfig:
    label_ru: str
    label_en: str
    staff_role_default: str
    staff_label_ru: str
    resource_examples: list[str]
    resources_mode: str               # "none" | "optional" | "required"
    resource_linked_to_staff: bool    # True → resource auto-created per staff member
    domain_instruction_ru: str
    default_services_hints: list[str]
    custom_domain: bool = False

    def __post_init__(self):
        if self.resources_mode not in ("none", "optional", "required"):
            raise ValueError(f"Invalid resources_mode: {self.resources_mode!r}")

    def to_dict(self, key: str) -> dict:
        return {
            "key": key,
            "label_ru": self.label_ru,
            "label_en": self.label_en,
            "staff_role_default": self.staff_role_default,
            "staff_label_ru": self.staff_label_ru,
            "resource_examples": list(self.resource_examples),
            "resources_mode": self.resources_mode,
            "resource_linked_to_staff": self.resource_linked_to_staff,
            "domain_instruction_ru": self.domain_instruction_ru,
            "default_services_hints": list(self.default_services_hints),
            "custom_domain": self.custom_domain,
        }


DOMAIN_REGISTRY: dict[str, DomainConfig] = {
    "beauty_salon": DomainConfig(
        label_ru="Салон красоты",
        label_en="Beauty Salon",
        staff_role_default="master",
        staff_label_ru="Мастер",
        resource_examples=["chair"],
        resources_mode="optional",
        resource_linked_to_staff=True,
        domain_instruction_ru=(
            "Предметная область: салон красоты. "
            "Используй терминологию мастер/услуга и уточняй предпочтения по времени."
        ),
        default_services_hints=["Стрижка", "Окрашивание", "Маникюр"],
    ),
    "dental_clinic": DomainConfig(
        label_ru="Стоматологическая клиника",
        label_en="Dental Clinic",
        staff_role_default="doctor",
        staff_label_ru="Врач",
        resource_examples=["room"],
        resources_mode="optional",
        resource_linked_to_staff=True,
        domain_instruction_ru=(
            "Предметная область: стоматологическая клиника. "
            "Используй терминологию врач/процедура и уточняй длительность приема."
        ),
        default_services_hints=["Осмотр", "Чистка", "Лечение кариеса"],
    ),
    "auto_service": DomainConfig(
        label_ru="Автосервис",
        label_en="Auto Service",
        staff_role_default="mechanic",
        staff_label_ru="Механик",
        resource_examples=["bay", "lift"],
        resources_mode="optional",
        resource_linked_to_staff=False,
        domain_instruction_ru=(
            "Предметная область: автосервис. "
            "Используй терминологию механик/бокс/подъёмник/работа. "
            "Уточняй марку и модель автомобиля, характер неисправности."
        ),
        default_services_hints=["Замена масла", "Диагностика", "Шиномонтаж"],
    ),
    "spa": DomainConfig(
        label_ru="СПА-салон",
        label_en="SPA",
        staff_role_default="therapist",
        staff_label_ru="Терапевт / Массажист",
        resource_examples=["room", "cabin"],
        resources_mode="optional",
        resource_linked_to_staff=False,
        domain_instruction_ru=(
            "Предметная область: СПА-салон. "
            "Используй терминологию терапевт/кабинет/процедура. "
            "Уточняй предпочтения по типу процедуры и длительности."
        ),
        default_services_hints=["Массаж классический", "Обёртывание", "Сауна"],
    ),
    "med_center": DomainConfig(
        label_ru="Медицинский центр",
        label_en="Medical Center",
        staff_role_default="doctor",
        staff_label_ru="Врач",
        resource_examples=["room", "equipment"],
        resources_mode="optional",
        resource_linked_to_staff=False,
        domain_instruction_ru=(
            "Предметная область: медицинский центр. "
            "Используй терминологию врач/кабинет/приём/процедура. "
            "Уточняй специализацию врача и направление."
        ),
        default_services_hints=["Первичный приём", "УЗИ", "Анализы", "ЭКГ"],
    ),
    "custom": DomainConfig(
        label_ru="Другое (настроить вручную)",
        label_en="Custom",
        staff_role_default="specialist",
        staff_label_ru="Специалист",
        resource_examples=[],
        resources_mode="optional",
        resource_linked_to_staff=False,
        domain_instruction_ru="",
        default_services_hints=[],
        custom_domain=True,
    ),
}


def get_domain_config(domain_type: str) -> DomainConfig | None:
    """Return DomainConfig for the given domain_type key, or None if not found."""
    return DOMAIN_REGISTRY.get(domain_type)


def get_domain_instruction(domain_type: str, custom_instruction: str | None = None) -> str:
    """Return the domain instruction string for the given domain_type.

    For the 'custom' domain, falls back to ``custom_instruction`` if provided.
    """
    config = DOMAIN_REGISTRY.get(domain_type)
    if config is None:
        return ""
    if config.custom_domain and custom_instruction:
        return custom_instruction.strip()
    return config.domain_instruction_ru
