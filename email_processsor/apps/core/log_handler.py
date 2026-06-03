import logging
import traceback as tb


class DatabaseLogHandler(logging.Handler):
    def emit(self, record):
        try:
            from django.apps import apps
            if not apps.ready:
                return
            AppLog = apps.get_model('core', 'AppLog')
            trace = None
            if record.exc_info:
                trace = ''.join(tb.format_exception(*record.exc_info))
            AppLog.objects.create(
                level=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                traceback=trace,
            )
        except Exception:
            pass
