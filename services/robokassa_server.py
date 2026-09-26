"""Принимает сигнал Robokassa «оплата прошла» и пишет клиенту в Telegram."""

import logging

from aiohttp import web

from handlers.club import deliver_paid_access
from services.payment_flow import accept_robokassa_result, mark_result_delivered

log = logging.getLogger(__name__)


def build_result_app(bot) -> web.Application:
    app = web.Application()

    async def result(request: web.Request) -> web.Response:
        if request.method == "POST":
            form = await request.post()
            params = {key: str(value) for key, value in form.items()}
        else:
            params = {key: str(value) for key, value in request.query.items()}
        outcome = await accept_robokassa_result(params)
        if outcome is None:
            return web.Response(status=400, text="bad sign")
        if outcome["needs_send"]:
            try:
                await deliver_paid_access(bot, outcome["user_id"], outcome["password"])
            except Exception:
                log.exception("Не удалось отправить доступ %s", outcome["user_id"])
                return web.Response(status=500, text="send failed")
            await mark_result_delivered(outcome["inv_id"])
        return web.Response(text=f"OK{outcome['inv_id']}")

    app.router.add_route("*", "/robokassa/result", result)
    return app


async def start_result_server(bot):
    from config import robokassa_result_port

    port = robokassa_result_port()
    runner = web.AppRunner(build_result_app(bot))
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    try:
        await site.start()
    except OSError:
        log.exception("Порт %s для Robokassa занят", port)
        await runner.cleanup()
        return None
    log.info("Robokassa ResultURL: порт %s, путь /robokassa/result", port)
    return runner
