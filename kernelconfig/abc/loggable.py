# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

import abc
import logging

__all__ = ["AbstractLoggable"]


class AbstractLoggable(object, metaclass=abc.ABCMeta):
    """Base class for objects with a logger.

    @cvar DEFAULT_LOGGER_NAME:  default logger name,
                                the class name is used if empty/None
    @type DEFAULT_LOGGER_NAME:  C{str} or C{None}

    @ivar logger:  logger
    @type logger:  L{logging.Logger}
    """

    __slots__ = ["logger"]

    DEFAULT_LOGGER_NAME = None

    def __init__(self, *, logger=None, logger_name=None, parent_logger=None):
        """Constructor.

        @keyword logger:         logger, if this parameter is not None,
                                 then logger_name and parent_logger will be
                                 ignored. Defaults to None.
        @type    logger:         C{logging.Logger} or C{None}
        @keyword logger_name:    logger name, used when creating a new one
        @type    logger_name:    C{str} or C{None}
        @keyword parent_logger:  parent logger, which will be used to create
                                 a child logger if logger is not set.
                                 Defaults to None.
        @type    parent_logger:  L{logging.Logger} or C{None}
        """

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
