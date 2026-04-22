from fastapi import status

from aiogram import F, types

from core.backendAPI import APIcreate, APIread, get_response_status
from core.config import settings
from keyboards.master_kb import get_main_menu, get_tariffs_keyboard

from .formatting import build_tariffs_text
from .payments_utils import PAYLOAD_PREFIX, parse_payment_payload
from .plans import get_plans_from_backend, paid_plans_map
from .router import master_router
from .telegram_helpers import safe_edit_callback_message


@master_router.callback_query(F.data == "tariffs_menu")
async def show_tariffs(callback: types.CallbackQuery):
    tg_id = callback.from_user.id

    user_json = await APIread.userBy_tgID(tg_id)

    response_status_user = get_response_status(user_json)

    if response_status_user == status.HTTP_404_NOT_FOUND:
        await callback.answer("Ошибка: пользователь не найден.")
        return

    elif response_status_user != status.HTTP_200_OK:
        await callback.answer(
            "Ошибка сервера при попытке получить пользователя",
            reply_markup=get_main_menu(),
        )
        return

    current_plan_code = user_json.get("subscription_type") or "Free"
    plans = await get_plans_from_backend()
    if not plans:
        await safe_edit_callback_message(
            callback,
            "Не удалось загрузить тарифы с сервера. Попробуйте позже.",
            reply_markup=get_main_menu(),
        )
        return

    text = build_tariffs_text(plans, current_plan_code)

    await safe_edit_callback_message(
        callback,
        text,
        reply_markup=get_tariffs_keyboard(),
        parse_mode="Markdown",
    )


@master_router.callback_query(F.data.startswith("set_plan_"))
async def process_set_plan(callback: types.CallbackQuery):
    plan_name = callback.data.split("_")[2]
    plans = await get_plans_from_backend()
    paid_plans = paid_plans_map(plans)
    plan = paid_plans.get(plan_name)
    if not plan:
        await callback.answer("Неизвестный тариф.", show_alert=True)
        return

    if not settings.BOT_PAYMENT_TOKEN:
        await callback.answer("Платежи не настроены. Обратитесь в поддержку.", show_alert=True)
        return

    if not callback.message:
        await callback.answer("Не удалось открыть платежное окно. Попробуйте еще раз.", show_alert=True)
        return

    payload = f"{PAYLOAD_PREFIX}:{plan_name}:{callback.from_user.id}"
    prices = [
        types.LabeledPrice(
            label=plan.get("title") or plan_name,
            amount=int(plan.get("telegram_amount_kopecks") or 0),
        )
    ]

    await callback.message.answer_invoice(
        title=f"Подписка {plan.get('title') or plan_name}",
        description=plan.get("telegram_invoice_description") or "",
        payload=payload,
        provider_token=settings.BOT_PAYMENT_TOKEN,
        currency="RUB",
        prices=prices,
        need_email=False,
        need_phone_number=False,
        need_shipping_address=False,
        is_flexible=False,
    )
    await callback.answer("Счет выставлен. Завершите оплату в Telegram.", show_alert=True)


@master_router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    plan_name, payload_tg_id = parse_payment_payload(pre_checkout_query.invoice_payload)

    plans = await get_plans_from_backend()
    paid_plan_codes = set(paid_plans_map(plans).keys())
    if plan_name not in paid_plan_codes or payload_tg_id != pre_checkout_query.from_user.id:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Не удалось проверить заказ. Попробуйте снова через меню тарифов.",
        )
        return

    await pre_checkout_query.answer(ok=True)


@master_router.message(F.successful_payment)
async def handle_successful_payment(message: types.Message):
    successful_payment = message.successful_payment
    plan_name, payload_tg_id = parse_payment_payload(successful_payment.invoice_payload)

    plans = await get_plans_from_backend()
    paid_plan_codes = set(paid_plans_map(plans).keys())
    if plan_name not in paid_plan_codes or payload_tg_id != message.from_user.id:
        await message.answer("Платеж получен, но не удалось определить тариф. Напишите в поддержку.")
        return

    process_response = await APIcreate.processSuccessfulPayment(
        telegram_id=message.from_user.id,
        plan_name=plan_name,
        currency=successful_payment.currency,
        total_amount=successful_payment.total_amount,
        telegram_payment_charge_id=successful_payment.telegram_payment_charge_id,
        provider_payment_charge_id=successful_payment.provider_payment_charge_id,
        invoice_payload=successful_payment.invoice_payload,
    )
    process_status = get_response_status(process_response)

    if process_status != status.HTTP_200_OK:
        await message.answer("Оплата прошла, но активация подписки временно недоступна. Напишите в поддержку.")
        return

    process_result = process_response.get("status")
    if process_result == "duplicate":
        await message.answer("ℹ️ Этот платеж уже был обработан ранее. Повторная активация не требуется.")
        return

    end_date_text = process_response.get("subscription_end_date")
    if end_date_text:
        try:
            end_date_text = end_date_text.replace("T", " ")[:16]
        except Exception:
            pass

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="💎 Открыть тарифы", callback_data="tariffs_menu")],
            [types.InlineKeyboardButton(text="⬅️ В меню", callback_data="start_menu")],
        ]
    )
    await message.answer(
        f"✅ Оплата получена!\n"
        f"Тариф *{plan_name}* активирован до *{end_date_text or 'указанной в профиле даты'}*.",
        parse_mode="Markdown",
        reply_markup=kb,
    )
