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
