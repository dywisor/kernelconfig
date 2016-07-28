# This file is part of kernelconfig.
# -*- coding: utf-8 -*-

__all__ = [
    "ModaliasCacheError",
    "ModaliasCacheBuildError",
    "ModaliasCacheBuildPrepareError",
    "ModaliasCacheBuildInstallError",
]


class ModaliasCacheError(RuntimeError):
    pass


class ModaliasCacheBuildError(ModaliasCacheError):
    pass


class ModaliasCacheBuildPrepareError(ModaliasCacheBuildError):
    pass


class ModaliasCacheBuildInstallError(ModaliasCacheBuildError):
    pass
