import logging
from datetime import datetime
from typing import List, Dict

import telegram
from apscheduler.schedulers.base import BaseScheduler
from telegram import ChatAction, Bot, Message, InputMediaPhoto
from telegram.constants import PARSEMODE_MARKDOWN_V2
from telegram.utils.helpers import escape_markdown

from configuration import ConfigWrapper
from camera import Camera
from klippy import Klippy

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: ConfigWrapper, bot: Bot, klippy: Klippy, camera_wrapper: Camera, scheduler: BaseScheduler, logging_handler: logging.Handler = None):
        self._bot: Bot = bot
        self._chat_id: int = config.bot.chat_id
        self._cam_wrap: Camera = camera_wrapper
        self._sched = scheduler
        self._klippy: Klippy = klippy

        self._percent: int = config.notifications.percent
        self._height: float = config.notifications.height
        self._interval: int = config.notifications.interval
        self._notify_groups: List[int] = config.notifications.notify_groups
        self._group_only: bool = config.notifications.group_only

        self._silent_progress: bool = config.telegram_ui.silent_progress
        self._silent_commands: bool = config.telegram_ui.silent_commands
        self._silent_status: bool = config.telegram_ui.silent_status
        self._status_single_message: bool = config.telegram_ui.status_single_message
        self._pin_status_single_message: bool = config.telegram_ui.pin_status_single_message  # Todo: implement
        self._message_parts: List[str] = config.telegram_ui.status_message_content

        self._last_height: int = 0
        self._last_percent: int = 0
        self._last_m117_status: str = ''
        self._last_tgnotify_status: str = ''

        self._status_message: Message = None
        self._groups_status_mesages: Dict[int, Message] = {}

        if logging_handler:
            logger.addHandler(logging_handler)
        if config.bot.debug:
            logger.setLevel(logging.DEBUG)

    @property
    def silent_commands(self) -> bool:
        return self._silent_commands

    @property
    def silent_status(self) -> bool:
        return self._silent_status

    @property
    def m117_status(self) -> str:
        return self._last_m117_status

    @m117_status.setter
    def m117_status(self, new_value: str):
        self._last_m117_status = new_value
        if self._klippy.printing:
            self._schedule_notification()

    @property
    def tgnotify_status(self) -> str:
        return self._last_tgnotify_status

    @tgnotify_status.setter
    def tgnotify_status(self, new_value: str):
        self._last_tgnotify_status = new_value
        if self._klippy.printing:
            self._schedule_notification()

    @property
    def percent(self) -> int:
        return self._percent

    @percent.setter
    def percent(self, new_value: int):
        if new_value >= 0:
            self._percent = new_value

    @property
    def height(self) -> float:
        return self._height

    @height.setter
    def height(self, new_value: float):
        if new_value >= 0:
            self._height = new_value

    @property
    def interval(self) -> int:
        return self._interval

    @interval.setter
    def interval(self, new_value: int):
        if new_value == 0:
            self._interval = new_value
            self.remove_notifier_timer()
        elif new_value > 0:
            self._interval = new_value
            self._reschedule_notifier_timer()

    def _send_message(self, message: str, silent: bool, group_only: bool = False, manual: bool = False):
        if not group_only:
            self._bot.send_chat_action(chat_id=self._chat_id, action=ChatAction.TYPING)
            if self._status_single_message and not manual:
                if not self._status_message:
                    self._status_message = self._bot.send_message(self._chat_id, text=message, parse_mode=PARSEMODE_MARKDOWN_V2, disable_notification=silent)
                else:
                    if self._status_message.caption:
                        self._status_message.edit_caption(caption=message, parse_mode=PARSEMODE_MARKDOWN_V2)
                    else:
                        self._status_message.edit_text(text=message, parse_mode=PARSEMODE_MARKDOWN_V2)
            else:
                self._bot.send_message(self._chat_id, text=message, parse_mode=PARSEMODE_MARKDOWN_V2, disable_notification=silent)
        for group in self._notify_groups:
            self._bot.send_chat_action(chat_id=group, action=ChatAction.TYPING)
            if self._status_single_message and not manual:
                if not group in self._groups_status_mesages:
                    self._groups_status_mesages[group] = self._bot.send_message(group, text=message, parse_mode=PARSEMODE_MARKDOWN_V2, disable_notification=silent)
                else:
                    mess = self._groups_status_mesages[group]
                    if mess.caption:
                        mess.edit_caption(caption=message, parse_mode=PARSEMODE_MARKDOWN_V2)
                    else:
                        mess.edit_text(text=message, parse_mode=PARSEMODE_MARKDOWN_V2)
            else:
                self._bot.send_message(group, text=message, parse_mode=PARSEMODE_MARKDOWN_V2, disable_notification=silent)

    def _notify(self, message: str, silent: bool, group_only: bool = False, manual: bool = False):
        if self._cam_wrap.enabled:
            with self._cam_wrap.take_photo() as photo:
                if not group_only:
                    self._bot.send_chat_action(chat_id=self._chat_id, action=ChatAction.UPLOAD_PHOTO)
                    if self._status_single_message and not manual:
                        if not self._status_message:
                            self._status_message = self._bot.send_photo(self._chat_id, photo=photo, caption=message, parse_mode=PARSEMODE_MARKDOWN_V2, disable_notification=silent)
                        else:
                            # Fixme: check if media in message!
                            self._status_message.edit_media(media=InputMediaPhoto(photo))
                            self._status_message.edit_caption(caption=message, parse_mode=PARSEMODE_MARKDOWN_V2)
                    else:
                        self._bot.send_photo(self._chat_id, photo=photo, caption=message, parse_mode=PARSEMODE_MARKDOWN_V2, disable_notification=silent)
                for group_ in self._notify_groups:
                    photo.seek(0)
                    self._bot.send_chat_action(chat_id=group_, action=ChatAction.UPLOAD_PHOTO)
                    if self._status_single_message and not manual:
                        if not group_ in self._groups_status_mesages:
                            self._groups_status_mesages[group_] = self._bot.send_photo(group_, text=message, parse_mode=PARSEMODE_MARKDOWN_V2, disable_notification=silent)
                        else:
                            mess = self._groups_status_mesages[group_]
                            mess.edit_media(media=InputMediaPhoto(photo))
                            mess.edit_caption(caption=message, parse_mode=PARSEMODE_MARKDOWN_V2)
                    else:
                        self._bot.send_photo(group_, photo=photo, caption=message, parse_mode=PARSEMODE_MARKDOWN_V2, disable_notification=silent)
                photo.close()
        else:
            self._send_message(message, silent, manual)

    # manual notification methods
    def send_error(self, message: str):
        self._sched.add_job(self._send_message, kwargs={'message': escape_markdown(message, version=2), 'silent': False, 'manual': True}, misfire_grace_time=None, coalesce=False, max_instances=6, replace_existing=False)

    def send_error_with_photo(self, message: str):
        self._sched.add_job(self._notify, kwargs={'message': escape_markdown(message, version=2), 'silent': False, 'manual': True}, misfire_grace_time=None, coalesce=False, max_instances=6, replace_existing=False)

    def send_notification(self, message: str):
        self._sched.add_job(self._send_message, kwargs={'message': escape_markdown(message, version=2), 'silent': self._silent_status, 'manual': True}, misfire_grace_time=None, coalesce=False, max_instances=6,
                            replace_existing=False)

    def send_notification_with_photo(self, message: str):
        self._sched.add_job(self._notify, kwargs={'message': escape_markdown(message, version=2), 'silent': self._silent_status, 'manual': True}, misfire_grace_time=None, coalesce=False, max_instances=6,
                            replace_existing=False)

    def reset_notifications(self) -> None:
        self._last_percent = 0
        self._last_height = 0
        self._klippy.printing_duration = 0
        self._last_m117_status = ''
        self._last_tgnotify_status = ''
        self._status_message = None
        self._groups_status_mesages = {}

    def _schedule_notification(self, message: str = '', schedule: bool = False):
        mess = escape_markdown(self._klippy.get_print_stats(message), version=2)
        if self._last_m117_status and 'm117_status' in self._message_parts:
            mess += f"{escape_markdown(self._last_m117_status, version=2)}\n"
        if self._last_tgnotify_status and 'tgnotify_status' in self._message_parts:
            mess += f"{escape_markdown(self._last_tgnotify_status, version=2)}\n"
        if 'last_update_time' in self._message_parts:
            mess += f"_Last update at {datetime.now():%H:%M:%S}_"
        if schedule:
            self._sched.add_job(self._notify, kwargs={'message': mess, 'silent': self._silent_progress, 'group_only': self._group_only}, misfire_grace_time=None, coalesce=False, max_instances=6, replace_existing=False)
        else:
            self._notify(mess, self._silent_progress, self._group_only)

    def schedule_notification(self, progress: int = 0, position_z: int = 0):
        if not self._klippy.printing or self._klippy.printing_duration <= 0.0 or (self._height == 0 and self._percent == 0):
            return

        notify = False
        if progress != 0 and self._percent != 0:
            if progress < self._last_percent - self._percent:
                self._last_percent = progress
            if progress % self._percent == 0 and progress > self._last_percent:
                self._last_percent = progress
                notify = True

        if position_z != 0 and self._height != 0:
            if position_z < self._last_height - self._height:
                self._last_height = position_z
            if position_z % self._height == 0 and position_z > self._last_height:
                self._last_height = position_z
                notify = True

        if notify:
            self._schedule_notification(schedule=True)

    def _notify_by_time(self):
        if not self._klippy.printing or self._klippy.printing_duration <= 0.0:
            return
        self._schedule_notification()

    def add_notifier_timer(self):
        if self._interval > 0:
            # Todo: maybe check if job exists?
            self._sched.add_job(self._notify_by_time, 'interval', seconds=self._interval, id='notifier_timer', replace_existing=True)

    def remove_notifier_timer(self):
        if self._sched.get_job('notifier_timer'):
            self._sched.remove_job('notifier_timer')

    def _reschedule_notifier_timer(self):
        if self._interval > 0 and self._sched.get_job('notifier_timer'):
            self._sched.add_job(self._notify_by_time, 'interval', seconds=self._interval, id='notifier_timer', replace_existing=True)

    def stop_all(self):
        self.reset_notifications()
        self.remove_notifier_timer()

    def _send_print_start_info(self):
        message, bio = self._klippy.get_file_info('Printer started printing')
        if bio is not None:
            status_message = self._bot.send_photo(self._chat_id, photo=bio, caption=message, disable_notification=self.silent_status)
            for group_ in self._notify_groups:
                bio.seek(0)
                self._groups_status_mesages[group_] = self._bot.send_photo(group_, photo=bio, caption=message, disable_notification=self.silent_status)
            bio.close()
        else:
            status_message = self._bot.send_message(self._chat_id, message, disable_notification=self.silent_status)
            for group_ in self._notify_groups:
                self._groups_status_mesages[group_] = self._bot.send_message(group_, message, disable_notification=self.silent_status)
        if self._status_single_message:
            self._status_message = status_message

    def send_print_start_info(self):
        self._sched.add_job(self._send_print_start_info, misfire_grace_time=None, coalesce=False, max_instances=1, replace_existing=True)
        # Todo: reset something?

    def _send_print_finish(self):
        self._schedule_notification(message='Finished printing')
        self.reset_notifications()

    def send_print_finish(self):
        self._sched.add_job(self._send_print_finish, misfire_grace_time=None, coalesce=False, max_instances=1, replace_existing=True)

    def update_status(self):
        self._schedule_notification()

    def parse_notification_params(self, message: str):
        mass_parts = message.split(sep=" ")
        mass_parts.pop(0)
        response = ''
        for part in mass_parts:
            try:
                if 'percent' in part:
                    self.percent = int(part.split(sep="=").pop())
                    response += f"percent={self.percent} "
                elif 'height' in part:
                    self.height = float(part.split(sep="=").pop())
                    response += f"height={self.height} "
                elif 'time' in part:
                    self.interval = int(part.split(sep="=").pop())
                    response += f"time={self.interval} "
                else:
                    self._klippy.execute_command(f'RESPOND PREFIX="Notification params error" MSG="unknown param `{part}`"')
            except Exception as ex:
                self._klippy.execute_command(f'RESPOND PREFIX="Notification params error" MSG="Failed parsing `{part}`. {ex}"')
        if response:
            full_conf = f"percent={self.percent} height={self.height} time={self.interval} "
            self._klippy.execute_command(f'RESPOND PREFIX="Notification params" MSG="Changed Notification params: {response}"')
            self._klippy.execute_command(f'RESPOND PREFIX="Notification params" MSG="Full Notification config: {full_conf}"')
