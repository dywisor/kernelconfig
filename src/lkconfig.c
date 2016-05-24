#include <Python.h>

#define LKCONFIG_PYMOD_NAME  "kernelconfig.lkconfig"

static PyObject* lkconfigKconfigParseError;


static PyMethodDef lkconfig_MethodTable[] = {
    { NULL, NULL, 0, NULL }  /* Sentinel */
};

static int lkconfig_init_module_exc ( PyObject* const m ) {
    PyObject* exc_obj;

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
      _exc_c_var = exc_obj; \
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

    return 0;
}


static struct PyModuleDef lkconfig_Module = {
   /* m_base:            */ PyModuleDef_HEAD_INIT,
   /* m_name:            */ LKCONFIG_PYMOD_NAME,
   /* m_doc:             */ "kernelconfig's lkc bindings",
   /* m_size:            */ -1,
   /* m_methods:         */ lkconfig_MethodTable,
   /* m_slots|m_reload:  */ NULL,
   /* m_traverse:        */ NULL,
   /* m_clear:           */ NULL,
   /* m_free:            */ NULL
};


PyMODINIT_FUNC PyInit_lkconfig (void) {
    PyObject* m;

    m = PyModule_Create ( &lkconfig_Module );
    if ( m == NULL ) { return NULL; }

    if ( lkconfig_init_module_exc ( m ) != 0 ) { return NULL; }

    return m;
}
