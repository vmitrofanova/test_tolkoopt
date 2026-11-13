"""Учебный фрагмент для тестового задания ТОЛЬКООПТ.

Python 3.10+, только стандартная библиотека. Запуск примера: python starter.py
В функции recommend_price намеренно есть ошибки. Исправьте её по правилам ниже.
sample_fetch_offers имитирует внешний источник: реальные запросы не нужны.

Контракт fetch_offers(): async-функция без аргументов, возвращает словарь
со status (success / partial / error) и offers (список предложений).
Все суммы на входе — положительные Decimal с точностью до копейки.
seller — строка; delivery_days — неотрицательное целое число или None.
Формат входных данных корректен; дополнительных проверок типов не требуется.
fetch_offers может завершиться исключением или долго ожидать ответа.
current_price — текущая цена; min_price — минимально допустимая цена.
timeout_s — положительное число секунд, по умолчанию 2.

ПРАВИЛА В ПОРЯДКЕ ПРИМЕНЕНИЯ
1. Ограничьте ожидание fetch_offers значением timeout_s. При ошибке источника,
   тайм-ауте или status != success верните текущую цену и HOLD.
2. Учитывайте предложения с известной доставкой не более 6 дней.
   Исключайте собственный магазин MYSHOP независимо от регистра букв.
3. Если подходящих предложений нет, верните текущую цену и HOLD,
   даже если текущая цена ниже min_price.
4. Минимальную цену подходящего конкурента уменьшите на 1,5% и округлите
   вниз до копейки. Рекомендация — максимум из этой суммы и min_price.
5. Если рекомендация отличается от текущей цены более чем на 30% в любую
   сторону, верните рекомендацию и REVIEW. Иначе — рекомендацию и APPLY.
   Ровно 30% допускается. REVIEW означает, что автоматическое применение
   запрещено до ручной проверки.

РЕЗУЛЬТАТ
Словарь с полями price (Decimal), decision (APPLY / REVIEW / HOLD),
reason (короткая понятная причина). Сохраните интерфейс recommend_price;
вспомогательные функции допустимы. Пример ниже после исправления должен
вернуть price = Decimal("4728.00"), decision = "APPLY".

ПРОВЕРКА
Добавьте минимум два автоматических теста: обычный расчёт и один сбой
или граничный случай на ваш выбор. Укажите команду запуска тестов.
Достаточно стандартной библиотеки; pytest также допустим.
Запуск тестов: python -m unittest -v test_starter
"""

import asyncio
from decimal import ROUND_DOWN, Decimal, localcontext


_pending_fetch_tasks = set()


def _forget_fetch_task(task):
    _pending_fetch_tasks.discard(task)
    if not task.cancelled():
        task.exception()


async def recommend_price(fetch_offers, current_price, min_price, timeout_s=2.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    fetch_task = asyncio.create_task(fetch_offers())
    _pending_fetch_tasks.add(fetch_task)
    fetch_task.add_done_callback(_forget_fetch_task)
    try:
        done, _ = await asyncio.wait((fetch_task,), timeout=deadline - loop.time())
        if fetch_task not in done or loop.time() >= deadline:
            raise asyncio.TimeoutError
        result = fetch_task.result()
    except (asyncio.TimeoutError, TimeoutError):
        return {
            "price": current_price,
            "decision": "HOLD",
            "reason": "Источник не ответил вовремя",
        }
    except Exception:
        return {"price": current_price, "decision": "HOLD", "reason": "Ошибка источника"}
    finally:
        # Источник может перехватить отмену и завершиться уже после возврата рекомендации.
        fetch_task.cancel()

    if result["status"] != "success":
        return {
            "price": current_price,
            "decision": "HOLD",
            "reason": "Источник не завершил сбор успешно",
        }

    prices = []
    for offer in result["offers"]:
        delivery_days = offer["delivery_days"]
        if (
            delivery_days is not None
            and delivery_days <= 6
            and offer["seller"].casefold() != "myshop"
        ):
            prices.append(offer["price"])

    if not prices:
        return {"price": current_price, "decision": "HOLD", "reason": "Нет подходящих предложений"}

    competitor_price = min(prices)
    with localcontext() as context:
        # Сохраняем точность до явного округления, в том числе для больших сумм.
        integer_digits = max(
            1,
            competitor_price.adjusted() + 1,
            current_price.adjusted() + 1,
            min_price.adjusted() + 1,
        )
        context.prec = max(context.prec, integer_digits + 5)
        discounted_price = (competitor_price * Decimal("0.985")).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
        price = max(discounted_price, min_price)
        change = abs(price - current_price)
        change_limit = current_price * Decimal("0.30")

    if change > change_limit:
        return {"price": price, "decision": "REVIEW", "reason": "Изменение цены больше 30%"}

    if price > discounted_price:
        reason = "Применена минимально допустимая цена"
    else:
        reason = "Цена конкурента снижена на 1,5%"
    return {"price": price, "decision": "APPLY", "reason": reason}


async def sample_fetch_offers():
    return {
        "status": "success",
        "offers": [
            {"seller": "myshop", "price": Decimal("4300.00"), "delivery_days": 2},
            {"seller": "PARTS", "price": Decimal("4800.00"), "delivery_days": 3},
            {"seller": "SLOW", "price": Decimal("4700.00"), "delivery_days": 8},
        ],
    }


if __name__ == "__main__":
    print(asyncio.run(recommend_price(
        sample_fetch_offers,
        current_price=Decimal("4900.00"),
        min_price=Decimal("4500.00"),
    )))
