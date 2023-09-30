# Longcat Voice Logging Botkit
Комплект ботов, логирующих действия лонгкета в голосовых чатах.

Telegram бот уведомляет, когда лонгкет заходит/выходит из голосового чата.

Discord бот логирует все подключения/отключения лонгкета из голосовых чатов и записывает голосовые разговоры с ним.

## Установка
Для работы записи голоса нужно установить пакеты libffi-dev (libffi-devel на некоторых системах) и python-dev (например python3.11-dev для Python 3.11).
После установки нужных системных пакетов, введите ```poetry install``` в корне проекта. 

## Запуск ботов
```shell
poetry run python bot.py
```
