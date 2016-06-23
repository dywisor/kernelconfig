static void lkconfig_set_and_ref (
    PyObject** const pyvar, PyObject* const pyval
) {
    Py_INCREF ( pyval );
    *pyvar = pyval;
}

/*
static void lkconfig_reset_and_ref (
    PyObject** const pyvar, PyObject* const pyval
) {
    Py_CLEAR ( *pyvar );
    lkconfig_set_and_ref ( pyvar, pyval );
}
*/

static void lkconfig_set_and_ref_if_null (
    PyObject** const pyvar, PyObject* const pyval
) {
    if ( *pyvar == NULL ) {
        lkconfig_set_and_ref ( pyvar, pyval );
    }
}


static int lkconfig_dict_add_str_x_int (
    PyObject* const d,
    const char* const key,
    const int value
) {
    PyObject* value_obj;
    int dictadd_ret;

    value_obj = PyLong_FromLong ( value );
    dictadd_ret = -1;
    if ( value_obj != NULL ) {
        dictadd_ret = PyDict_SetItemString ( d, key, value_obj );
        Py_DECREF ( value_obj );
    }

    return dictadd_ret;
}

/**
 * Steals a reference to 'item' and adds it to the list 'l'.
 *
 * Item may be null, in which case -2 is returned.
 * The reference count of 'item' is decremented even if list-append fails.
 *
 *
 * @param l       PyList
 * @param item    PyObject item to append (can be null)
 *
 * @return 0 on success, else non-zero
 * */
static int lkconfig_list_append_steal_ref (
    PyObject* const l, PyObject* const item
) {
    int append_ret;

    if ( item == NULL ) { return -2; }
    append_ret = PyList_Append ( l, item );
    Py_DECREF ( item );
    return append_ret;
}


/*
static int lkconfig_list_append_ptr_steal_ref (
    PyObject* const l, PyObject** const item_ptr
) {
    int append_ret;

    if ( *item_ptr == NULL ) { return -2; }
    append_ret = PyList_Append ( l, *item_ptr );
    Py_DECREF ( *item_ptr );
    *item_ptr = NULL;
    return append_ret;
}
*/


static int lkconfig_logv (
    PyObject* const logger,
    const int log_level,
    const char* const format,
    va_list vargs
) {
    static const char* meth_names[lkconfig__log_level_count] = {
        "debug", "info", "warning", "error", "critical"
    };
    PyObject* msg;
    PyObject* logret;

    if ( logger == NULL ) { return 0; }

    if ( (log_level < 0) || (log_level >= lkconfig__log_level_count) ) {
        PyErr_Format (
            PyExc_ValueError, "unknown log level %d", log_level
        );
        return -1;
    }

    msg = PyUnicode_FromFormatV ( format, vargs );
    if ( msg == NULL ) { return -1; }

    logret = PyObject_CallMethod ( logger, meth_names[log_level], "O", msg );

    Py_DECREF ( msg );

    if ( logret == NULL ) {
        return -1;
    }

    Py_DECREF ( logret );
    return 0;
}

static int lkconfig_log (
    PyObject* const logger,
    const int log_level,
    const char* const format,
    ...
) {
    va_list vargs;
    int ret;

    va_start ( vargs, format );
    ret = lkconfig_logv ( logger, log_level, format, vargs );
    va_end ( vargs );

    return ret;
}
