"""Расчёт индивидуальной скидки партнёра."""


def calculate_partner_discount(total_quantity: int) -> int:
    """Возвращает процент скидки по суммарному объёму покупок."""
    if isinstance(total_quantity, bool) or not isinstance(total_quantity, int):
        raise TypeError("Суммарный объём должен быть целым числом")
    if total_quantity < 0:
        raise ValueError("Суммарный объём не может быть отрицательным")
    if total_quantity < 10_000:
        return 0
    if total_quantity < 50_000:
        return 5
    if total_quantity < 300_000:
        return 10
    return 15
