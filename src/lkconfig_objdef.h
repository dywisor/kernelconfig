#ifndef _KERNELCONFIG_LKCONFIG_OBJDEF_H_
#define _KERNELCONFIG_LKCONFIG_OBJDEF_H_

#include <Python.h>
#include "structmember.h"

#include "lkc/lkc.h"

#define LKCONFIG_PYMOD_NAME  "kernelconfig.kconfig.lkconfig"

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


#endif  /* _KERNELCONFIG_LKCONFIG_OBJDEF_H_ */
