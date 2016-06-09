#include <Python.h>
#include "structmember.h"
#include "lkc/lkc.h"



#include "lkconfig_objdef.h"

#include "lkconfig_utilfuncs.c"
#include "lkconfig_symbol.c"
#include "lkconfig_expr.c"
#include "lkconfig_conf.c"

/* exceptions */
static PyObject* lkconfigKconfigParseError;


/* function sig */
static PyObject* lkconfig_read_symbols ( PyObject* self, PyObject* args );
static PyObject* lkconfig_get_symbols ( PyObject* self, PyObject* noargs );
static PyObject* lkconfig_oldconfig ( PyObject* self, PyObject* args );

PyMODINIT_FUNC PyInit_lkconfig (void);


/* module */
static PyMethodDef lkconfig_MethodTable[] = {
    {
        "read_symbols",
        lkconfig_read_symbols,
        METH_VARARGS,
        PyDoc_STR (
            "_read_symbols(kconfig_file)\n"
            "\n"
            "Reads kconfig files.\n"
            "\n"
            "Arguments:\n"
            "* kconfig_file     -- top-level Kconfig file\n"
            "\n"
            "Notes:\n"
            "* environment sensitive: ARCH, SRCARCH and KERNELVERSION need to be set\n"
            "                         in os.environ prior to calling this function.\n"
            "* must not be called more than once\n"  /* due to how lkc stores symbols */
        )
    },
    {
        "get_symbols",
        lkconfig_get_symbols,
        METH_NOARGS,
        PyDoc_STR (
            "get_symbols()\n"
            "\n"
            "Returns a list of kconfig symbols (as SymbolViewObject).\n"
            "\n"
            "Note: read_symbols() must be called before calling this function!\n"
        )
    },
    {
        "oldconfig",
        lkconfig_oldconfig,
        METH_VARARGS,
        PyDoc_STR (
            "oldconfig(input_file, output_file, decisions_dict)\n"
            "\n"
            "Runs oldconfig.\n"
            "\n"
            "Note: read_symbols() must be called before this function!\n"
        )
    },
    /* and returns a list of all symbols.\n"*/
    { NULL, NULL, 0, NULL }  /* Sentinel */
};


static struct PyModuleDef lkconfig_Module = {
   /* m_base:            */ PyModuleDef_HEAD_INIT,
   /* m_name:            */ LKCONFIG_PYMOD_NAME,
   /* m_doc:             */ "kernelconfig's lkc bindings",
   /* m_size:            */ -1,
   /* m_methods:         */ lkconfig_MethodTable,
   /* m_slots|m_reload:  */ NULL,
   /* m_traverse:        */ NULL,
   /* m_clear:           */ NULL,   /* FIXME: required, free symbols! */
   /* m_free:            */ NULL
};



static int lkconfig_init_module_exc ( PyObject* const m ) {
#define _LKCONFIG_INIT_EXC(_exc_c_var, _exc_py_varname, _exc_base, _exc_doc)  \
   do { \
      PyObject* exc_obj; \
      \
      exc_obj = PyErr_NewExceptionWithDoc ( \
         (char*) (LKCONFIG_PYMOD_NAME "." _exc_py_varname), \
         (char*) (_exc_doc), \
         _exc_base, \
         NULL \
      ); \
      if ( exc_obj == NULL ) { return -1; } \
      _exc_c_var = exc_obj; exc_obj = NULL; \
      Py_INCREF ( _exc_c_var ); \
      PyModule_AddObject ( m, _exc_py_varname, _exc_c_var ); \
   } while (0)
/*
#define LKCONFIG_INIT_EXC(exc_var, exc_base, exc_doc)  \
   _LKCONFIG_INIT_EXC(exc_var, #exc_var, exc_base, exc_doc)
*/

    _LKCONFIG_INIT_EXC (
        lkconfigKconfigParseError,
        "KconfigParseError",
        PyExc_Exception,
        PyDoc_STR ( "kconfig parser related error" )
    );

/*#undef LKCONFIG_INIT_EXC*/
#undef _LKCONFIG_INIT_EXC
    return 0;
}

static int lkconfig_init_constants ( PyObject* const m ) {
#define _LKCONFIG_INT_CONST(_name, _value)  \
    do { \
        if ( PyModule_AddIntConstant(m, (_name), (_value)) != 0 ) { \
            return -1; \
        } \
    } while (0)

#define LKCONFIG_INT_CONST(_d)  _LKCONFIG_INT_CONST(#_d, _d)

    LKCONFIG_INT_CONST ( S_UNKNOWN );
    LKCONFIG_INT_CONST ( S_BOOLEAN );
    LKCONFIG_INT_CONST ( S_TRISTATE );
    LKCONFIG_INT_CONST ( S_INT );
    LKCONFIG_INT_CONST ( S_HEX );
    LKCONFIG_INT_CONST ( S_STRING );
    LKCONFIG_INT_CONST ( S_OTHER );

    return 0;

#undef LKCONFIG_INT_CONST
}

PyMODINIT_FUNC PyInit_lkconfig (void) {
    PyObject* m;

    if ( PyType_Ready(&lkconfig_SymbolViewType) < 0 ) {
        return NULL;
    }

    if ( lkconfig_ExprViewObject_cls_init ( &lkconfig_ExprViewType ) < 0 ) {
        return NULL;
    }

    m = PyModule_Create ( &lkconfig_Module );
    if ( m == NULL ) { return NULL; }

    if ( lkconfig_init_module_exc ( m ) != 0 ) { return NULL; }
    if ( lkconfig_init_constants ( m ) != 0 ) { return NULL; }

    Py_INCREF ( &lkconfig_SymbolViewType );
    PyModule_AddObject (
        m, lkconfig_SymbolViewName, (PyObject*) &lkconfig_SymbolViewType
    );

    Py_INCREF ( &lkconfig_ExprViewType );
    PyModule_AddObject (
        m, lkconfig_ExprViewName, (PyObject*) &lkconfig_ExprViewType
    );

    return m;
}


/* functions */

/**
 * Helper function.
 *
 * Reads symbols from a kconfig file and returns zero on success.
 * Otherwise, a python exception is created and a non-zero value is returned.
 *
 * @param kconfig_file   path to the top-level Kconfig file
 *
 * @return 0 => success, non-zero => failure
 *
 * */
static int lkconfig__conf_parse ( const char* const kconfig_file ) {
    /*
     * FIXME:
     * conf_parse() from zconf.tab.c calls exit(1) on errors;
     * could modify it to return non-zero int on error
     * */
    conf_parse ( kconfig_file );
    return 0;
}


static PyObject* lkconfig_oldconfig ( PyObject* self, PyObject* args ) {
    PyDictObject* conf_decisions = NULL;
    const char* infile  = NULL;
    const char* outfile = NULL;

    if (
        ! PyArg_ParseTuple (
            args, "ssO!", &infile, &outfile, &PyDict_Type, &conf_decisions
        )
    ) {
        return NULL;
    }

    lkconfig_conf_main ( infile, outfile, conf_decisions );
    Py_RETURN_NONE;
}


static PyObject* lkconfig_read_symbols ( PyObject* self, PyObject* args ) {
    const char* kconfig_file = NULL;

    /* parse args */
    if ( ! PyArg_ParseTuple ( args, "s", &kconfig_file ) ) { return NULL; }

    /* read symbols */
    if ( lkconfig__conf_parse ( kconfig_file ) != 0 ) { return NULL; }

    Py_RETURN_NONE;
}

static PyObject* lkconfig_get_symbols ( PyObject* self, PyObject* noargs ) {
    unsigned int i;
    const struct symbol* sym;
    int append_ret;

    PyObject* pysym_list;
    PyObject* pysym;

    /* create py-symbol list */
    pysym_list = PyList_New(0);
    if ( pysym_list == NULL ) { return NULL; }

    for_all_symbols(i, sym) {
        switch ( sym->type ) {
            case S_UNKNOWN:
                break;

            case S_TRISTATE:
            case S_BOOLEAN:
            case S_STRING:
            case S_INT:
            case S_HEX:
            case S_OTHER:
                pysym = lkconfig_SymbolViewObject_new_from_struct ( sym );
                if ( pysym == NULL ) {
                    append_ret = -1;
                } else {
                    append_ret = PyList_Append ( pysym_list, pysym );
                    Py_DECREF ( pysym ); pysym = NULL;
                }

                if ( append_ret != 0 ) {
                    Py_DECREF ( pysym_list );
                    return NULL;
                }
                break;

        }
    }

    return pysym_list;
}
