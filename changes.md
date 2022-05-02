# Список изменений с версии 1.4.2

## Новые функции
* Поддержка api-token для авторизации ( секция bot )
* Multi instance installer
* Добавлен скрипт удаления
* НАстройка параметров cv2 для камеры с использованием [camera.cv2] (указываем название параметра cv2 и его значение) Никаких проверок!

## Добработки и мелкие исправления

* Листание для списка файлов
* ujson при обработке http
* Исправлено построение таймлапса по высоте
* Полное отключение уведомлений при отсутствии секции [progress_notification]
* Убран legacy режим уведомелний и соотсветсвующий пункт конфига
* Добавлена отправка служебных сообщений для вызова уведомелния

## Описать в документации

* Загрузку файлов через бота (отправляем файл .gcode или архив .zip с gcode. только один файл gcode в архиве! Файл загружается в moonraker и выдается предложение печати файла - аналогично с командой files)
* Описать status_message_m117_update