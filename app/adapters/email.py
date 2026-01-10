import asyncio
import time
import imaplib
import email as email_lib
from email.header import decode_header

from app.adapters.base import BaseAdapter
from app.core.logger import logger


class EmailAdapter(BaseAdapter):
    """
    Адаптер для получения событий из email через IMAP.
    
    Формат токена: host:port:username:password
    Пример: imap.gmail.com:993:user@gmail.com:app_password
    """
    
    def __init__(self, token: str, redis_queue):
        super().__init__(token, redis_queue)
        self.last_activity = time.monotonic()
        
        parts = token.split(":")
        if len(parts) < 4:
            raise ValueError(
                "Неверный формат токена email. "
                "Ожидается: host:port:username:password"
            )
        
        self.host = parts[0]
        self.port = int(parts[1])
        self.username = parts[2]
        self.password = ":".join(parts[3:])  # Пароль может содержать ":"
        
        self.last_uid = 0
        self.imap = None

    def _get_bot_id(self) -> str:
        """Возвращает идентификатор для логов"""
        return f"{self.username[:15]}..."

    async def start_polling(self):
        """Запускает polling для email"""
        bot_id = self._get_bot_id()
        logger.info(f"Стартую polling для email: {bot_id}")
        
        while True:
            timeout = int(self.get_dynamic_timeout())
            try:
                # Выполняем IMAP операции в отдельном потоке (IMAP синхронный)
                new_emails = await asyncio.get_event_loop().run_in_executor(
                    None, self._check_new_emails
                )
                
                if new_emails:
                    logger.info(
                        f"Получено {len(new_emails)} новых писем для {bot_id}"
                    )
                
                for email_data in new_emails:
                    try:
                        await self.redis.publish_event({
                            "messenger": "email",
                            "token": self.token,
                            "data": email_data
                        })
                        self.last_activity = time.monotonic()
                    except Exception as e:
                        logger.error(
                            f"Ошибка публикации email в Redis: {e}",
                            exc_info=True
                        )
                
                await asyncio.sleep(timeout)
                
            except asyncio.CancelledError:
                logger.info(f"Остановка polling для email: {bot_id}")
                self._disconnect()
                break
            except Exception as e:
                logger.error(f"Ошибка polling email {bot_id}: {e}", exc_info=True)
                self._disconnect()
                await asyncio.sleep(5)

    def _connect(self):
        """Подключается к IMAP серверу"""
        if self.imap is not None:
            # Проверяем, что соединение живое
            try:
                self.imap.noop()
                return
            except Exception:
                self._disconnect()
        
        try:
            self.imap = imaplib.IMAP4_SSL(self.host, self.port)
            self.imap.login(self.username, self.password)
            self.imap.select("INBOX")
            logger.info(f"Подключено к IMAP: {self.host}")
        except Exception as e:
            logger.error(f"Ошибка подключения к IMAP {self.host}: {e}")
            self.imap = None
            raise

    def _disconnect(self):
        """Отключается от IMAP сервера"""
        if self.imap:
            try:
                self.imap.logout()
            except Exception:
                pass
            self.imap = None

    def _check_new_emails(self) -> list:
        """Проверяет новые письма (синхронно)"""
        try:
            self._connect()
            
            # Используем UID SEARCH для поиска новых писем
            # UID больше last_uid (или все непрочитанные при первом запуске)
            if self.last_uid > 0:
                search_criteria = f"UID {self.last_uid + 1}:*"
                status, data = self.imap.uid("search", None, search_criteria)
            else:
                # Первый запуск — берём только непрочитанные
                status, data = self.imap.uid("search", None, "UNSEEN")
            
            if status != "OK" or not data[0]:
                return []
            
            uid_list = data[0].split()
            if not uid_list:
                return []
            
            uid_list = uid_list[-10:]  # Максимум 10 писем за итерацию
            
            new_emails = []
            for uid in uid_list:
                uid_int = int(uid)
                if uid_int <= self.last_uid:
                    continue
                    
                try:
                    email_data = self._fetch_email_by_uid(uid)
                    if email_data:
                        new_emails.append(email_data)
                        if uid_int > self.last_uid:
                            self.last_uid = uid_int
                except Exception as e:
                    logger.warning(f"Ошибка обработки письма UID {uid}: {e}")
            
            return new_emails
            
        except Exception as e:
            logger.error(f"Ошибка проверки email: {e}")
            self._disconnect()
            return []

    def _fetch_email_by_uid(self, uid: bytes) -> dict | None:
        """Получает данные письма по UID"""
        status, msg_data = self.imap.uid("fetch", uid, "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            return None
        
        # msg_data[0] может быть tuple или None
        if isinstance(msg_data[0], tuple):
            raw_email = msg_data[0][1]
        else:
            return None
        
        msg = email_lib.message_from_bytes(raw_email)
        
        # Декодируем заголовки
        subject = self._decode_header(msg["Subject"])
        from_addr = self._decode_header(msg["From"])
        date = msg["Date"]
        
        body = self._get_body(msg)
        
        return {
            "uid": int(uid),
            "message_id": msg["Message-ID"],
            "from": from_addr,
            "subject": subject,
            "date": date,
            "body": body[:1000] if body else None,
        }

    def _decode_header(self, header: str | None) -> str:
        """Декодирует заголовок письма"""
        if not header:
            return ""
        
        try:
            decoded_parts = decode_header(header)
            result = []
            for part, charset in decoded_parts:
                if isinstance(part, bytes):
                    result.append(part.decode(charset or "utf-8", errors="replace"))
                else:
                    result.append(str(part))
            return "".join(result)
        except Exception:
            return str(header)

    def _get_body(self, msg) -> str | None:
        """Извлекает текст письма"""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            return payload.decode(charset, errors="replace")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        except Exception:
            pass
        return None
