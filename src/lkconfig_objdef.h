#ifndef _KERNELCONFIG_LKCONFIG_OBJDEF_H_
#define _KERNELCONFIG_LKCONFIG_OBJDEF_H_

#include <Python.h>
#include "structmember.h"

#include "lkc/lkc.h"

#define LKCONFIG_PYMOD_NAME  "kernelconfig.kconfig.lkconfig"

enum {
    lkconfig_debug,
    lkconfig_info,
    lkconfig_warning,
    lkconfig_error,
    lkconfig_critical,

    lkconfig__log_level_count
};


#define lkconfig_SymbolViewName  "SymbolView"
typedef struct {
    PyObject_HEAD

    /* make a few fields available as PyObjects */
    PyObject* name;
    int s_type;

    const struct symbol* kconfig_sym;
} lkconfig_SymbolViewObject;


#define lkconfig_ExprViewName  "ExprView"
typedef struct {
    PyObject_HEAD
    int e_type;

    const struct expr* kconfig_expr;
} lkconfig_ExprViewObject;


static PyObject* lkconfig_ExprViewObject_new_from_struct (
    const struct expr* kconfig_expr
);

static PyObject* lkconfig_SymbolViewObject_new_from_struct (
    const struct symbol* const sym
);

/**
 * log function, va_list variant.
 *
 * If logger is NULL ("not set"), returns immediately w/ success status code.
 *
 * Otherwise, builds a Python string from format and vargs,
 * and calls the logger's debug, info, warning, error or critical method,
 * depending on the log_level parameter.
 *
 * @param logger       logger, may be NULL
 * @param log_level    log level, must be one of lkconfig_{debug,...}
 * @param format       log message format string
 * @param vargs        log message varargs
 *
 * @return 0 => success, non-zero => failure
 * */
static int lkconfig_logv (
    PyObject* const logger,
    const int log_level,
    const char* const format,
    va_list vargs
);

/**
 * log function, varargs variant.
 *
 * See lkconfig_logv().
 * */
__attribute__((format (printf, 3, 4)))
static int lkconfig_log (
    PyObject* const logger,
    const int log_level,
    const char* const format,
    ...
);


/*
 * PyUnicode_FromFormatV(fmt, vargs) does not need to be NULL-terminated

#define lkconfig_log(logger, log_level, ...)  \
    _lkconfig_log((logger), (log_level), __VA_ARGS__, NULL)
*/

/**
 * log function, message string variant.
 *
 * See lkconfig_logv().
 * */
#define lkconfig_logs(logger, log_level, s)  \
    lkconfig_log((logger), (log_level), "%s", (s))

#endif  /* _KERNELCONFIG_LKCONFIG_OBJDEF_H_ */
