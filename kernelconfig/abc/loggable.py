# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import logging

__all__ = ["AbstractLoggable"]


class AbstractLoggable(object, metaclass=abc.ABCMeta):
    DEFAULT_LOGGER_NAME = None

    def __init__(self, *, logger=None, logger_name=None, parent_logger=None):
        super(AbstractLoggable, self).__init__()
        self.logger = None
        self.set_logger(
            logger=logger, logger_name=logger_name, parent_logger=parent_logger
        )
    # --- end of __init__ (...) ---

    def create_loggable(self, loggable_cls, *args, **kwargs):
        kwargs.setdefault("parent_logger", self.logger)
        return loggable_cls(*args, **kwargs)
    # --- end of create_loggable (...) ---

    def set_logger(self, logger=None, logger_name=None, parent_logger=None):
        if logger is not None:
            self.logger = logger
        else:
            logger_name = (
                logger_name
                or self.DEFAULT_LOGGER_NAME or self.__class__.__name__
            )
            if parent_logger is not None:
                self.logger = parent_logger.getChild(logger_name)
            else:
                self.logger = logging.getLogger(logger_name)
    # --- end of set_logger (...) ---
# --- end of AbstractLoggable ---
