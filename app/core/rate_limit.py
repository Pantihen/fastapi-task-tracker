from slowapi import Limiter
from slowapi.util import get_remote_address

# Лимитер по IP-адресу клиента
limiter = Limiter(key_func=get_remote_address)
