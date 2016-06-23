/** is_choice :: SymbolViewObject -> bool */
static PyObject* lkconfig_SymbolViewObject_is_choice (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    if ( sym_is_choice((struct symbol*) self->kconfig_sym) ) {
        Py_RETURN_TRUE;
    } else {
        Py_RETURN_FALSE;
    }
}

#define lkconfig_SymbolViewObject__is_of_type_func_body(_type)  \
    do { \
        if ( self->kconfig_sym->type == (_type) ) { \
            Py_RETURN_TRUE; \
        } else { \
            Py_RETURN_FALSE; \
        } \
    } while (0)

/** is_tristate :: SymbolViewObject -> bool */
static PyObject* lkconfig_SymbolViewObject_is_tristate (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    lkconfig_SymbolViewObject__is_of_type_func_body ( S_TRISTATE );
}

/** is_boolean :: SymbolViewObject -> bool */
static PyObject* lkconfig_SymbolViewObject_is_boolean (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    lkconfig_SymbolViewObject__is_of_type_func_body ( S_BOOLEAN );
}

/** is_string :: SymbolViewObject -> bool */
static PyObject* lkconfig_SymbolViewObject_is_string (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    lkconfig_SymbolViewObject__is_of_type_func_body ( S_STRING );
}

/** is_int :: SymbolViewObject -> bool */
static PyObject* lkconfig_SymbolViewObject_is_int (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    lkconfig_SymbolViewObject__is_of_type_func_body ( S_INT );
}

/** is_hex :: SymbolViewObject -> bool */
static PyObject* lkconfig_SymbolViewObject_is_hex (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    lkconfig_SymbolViewObject__is_of_type_func_body ( S_HEX );
}

/** is_other :: SymbolViewObject -> bool */
static PyObject* lkconfig_SymbolViewObject_is_other (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    lkconfig_SymbolViewObject__is_of_type_func_body ( S_OTHER );
}

#undef lkconfig_SymbolViewObject__is_of_type_func_body

static PyObject* lkconfig_SymbolViewObject_get_dir_dep (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    if ( self->kconfig_sym == NULL ) {
        Py_RETURN_NONE;
    } else {
        return lkconfig_ExprViewObject_new_from_struct (
            (self->kconfig_sym->dir_dep).expr
        );
    }
}

static PyObject* lkconfig_SymbolViewObject_get_rev_dep (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    if ( self->kconfig_sym == NULL ) {
        Py_RETURN_NONE;
    } else {
        return lkconfig_ExprViewObject_new_from_struct (
            (self->kconfig_sym->rev_dep).expr
        );
    }
}


static int lkconfig_SymbolViewObject__create_prompt_and_append_to_list (
    PyObject* const l, const struct property* const prompt
) {
    PyObject* text;
    PyObject* eview;
    PyObject* prompt_tuple;

    text = NULL;
    if ( prompt->text != NULL ) {
        text = PyUnicode_FromString ( prompt->text );
        if ( text == NULL ) { return -1; }
    }

    eview = NULL;
    if ( prompt->visible.expr != NULL ) {
        eview = lkconfig_ExprViewObject_new_from_struct (
            prompt->visible.expr
        );

        if ( eview == NULL ) {
            Py_XDECREF ( text );
            return -1;
        }
    }

    if ( (text == NULL) && (eview == NULL) ) {
        /* then prompt is of no interest */
        return 0;
    }

    lkconfig_set_and_ref_if_null ( &text,  Py_None );
    lkconfig_set_and_ref_if_null ( &eview, Py_None );

    /*
     * Py_BuildValue w/ "N" could leak
     *  https://bugs.python.org/issue26168
     * */
    prompt_tuple = Py_BuildValue( "(OO)", text, eview );
    Py_DECREF ( text );
    Py_DECREF ( eview );

    return lkconfig_list_append_steal_ref ( l, prompt_tuple );
}


static PyObject* lkconfig_SymbolViewObject_get_prompt (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    const struct property* prompt;
    PyObject* prompt_list;

    prompt_list = PyList_New(0);

    if ( prompt_list != NULL ) {
        for_all_prompts ( self->kconfig_sym, prompt ) {
            if ( prompt->text != NULL ) {
                if (
                    lkconfig_SymbolViewObject__create_prompt_and_append_to_list (
                        prompt_list, prompt
                    ) != 0
                ) {
                    Py_DECREF ( prompt_list );
                    return NULL;
                }
            }
        }
    }

    return prompt_list;
}


static int lkconfig_SymbolViewObject__create_expr_and_append_to_list (
    PyObject* const l, const struct expr* const e
) {
    return lkconfig_list_append_steal_ref (
        l,
        lkconfig_ExprViewObject_new_from_struct ( e )
    );
}


static PyObject* lkconfig_SymbolViewObject_get_selects (
    lkconfig_SymbolViewObject* const self, PyObject* const args
) {
    const struct property* sel;
    PyObject* sel_list;

    sel_list = PyList_New(0);
    if ( sel_list == NULL ) { return NULL; }

    for_all_properties(self->kconfig_sym, sel, P_SELECT) {
        if ( sel->expr == NULL ) {
            PyErr_SetString ( PyExc_ValueError, "NULL expr in selects" );
            Py_DECREF ( sel_list );
            return NULL;
        }

        if (
            lkconfig_SymbolViewObject__create_expr_and_append_to_list (
                sel_list, sel->expr
            ) != 0
        ) {
            Py_DECREF ( sel_list );
            return NULL;
        }
    }

    return sel_list;
}


static void lkconfig_SymbolViewObject_dealloc (
    lkconfig_SymbolViewObject* const self
) {
    Py_CLEAR ( self->name );
    Py_TYPE(self)->tp_free ( (PyObject*) self );
}


static PyMethodDef lkconfig_SymbolViewObject_methods[] = {
    {
        "is_choice",
        (PyCFunction) lkconfig_SymbolViewObject_is_choice,
        METH_NOARGS,
        PyDoc_STR (
            "is_choice() -- checks whether the symbol represents a choice"
        )
    },
    {
        "is_tristate",
        (PyCFunction) lkconfig_SymbolViewObject_is_tristate,
        METH_NOARGS,
        PyDoc_STR (
            "is_tristate() -- checks whether the symbol is a tristate (S_TRISTATE)"
        )
    },
    {
        "is_boolean",
        (PyCFunction) lkconfig_SymbolViewObject_is_boolean,
        METH_NOARGS,
        PyDoc_STR (
            "is_boolean() -- checks whether the symbol is a boolean (S_BOOLEAN)"
        )
    },
    {
        "is_string",
        (PyCFunction) lkconfig_SymbolViewObject_is_string,
        METH_NOARGS,
        PyDoc_STR (
            "is_string() -- checks whether the symbol is a string (S_STRING)"
        )
    },
    {
        "is_int",
        (PyCFunction) lkconfig_SymbolViewObject_is_int,
        METH_NOARGS,
        PyDoc_STR (
            "is_int() -- checks whether the symbol is an int (S_INT)"
        )
    },
    {
        "is_hex",
        (PyCFunction) lkconfig_SymbolViewObject_is_hex,
        METH_NOARGS,
        PyDoc_STR (
            "is_hex() -- checks whether the symbol is a hex int (S_HEX)"
        )
    },
    {
        "is_other",
        (PyCFunction) lkconfig_SymbolViewObject_is_other,
        METH_NOARGS,
        PyDoc_STR (
            "is_other() -- checks whether the symbol is of 'other' type (S_OTHER)"
        )
    },
    {
        "get_dir_dep",
        (PyCFunction) lkconfig_SymbolViewObject_get_dir_dep,
        METH_NOARGS,
        PyDoc_STR (
            "get_dir_dep() -- returns an ExpressionView object"
        )
    },
    {
        "get_rev_dep",
        (PyCFunction) lkconfig_SymbolViewObject_get_rev_dep,
        METH_NOARGS,
        PyDoc_STR (
            "get_rev_dep() -- returns an ExpressionView object"
        )
    },
    {
        "get_prompts",
        (PyCFunction) lkconfig_SymbolViewObject_get_prompt,
        METH_NOARGS,
        PyDoc_STR (
            "get_prompts() -- returns a list of 2-tuples"
            " (prompt string, prompt visibility ExpressionView)"
        )
    },
    {
        "get_selects",
        (PyCFunction) lkconfig_SymbolViewObject_get_selects,
        METH_NOARGS,
        PyDoc_STR (
            "get_selects() -- returns a list of all selects"
        )
    },
    { NULL }
};

static PyMemberDef lkconfig_SymbolViewObject_members[] = {
    {
        "name",
        T_OBJECT_EX, offsetof(lkconfig_SymbolViewObject, name), READONLY,
        PyDoc_STR ( "symbol name" )
    },
    {
        "s_type",
        T_INT, offsetof(lkconfig_SymbolViewObject, s_type), READONLY,
        PyDoc_STR ( "symbol type" )
    },
    { NULL }
};


static PyTypeObject lkconfig_SymbolViewType = {
    PyVarObject_HEAD_INIT(NULL, 0)

    LKCONFIG_PYMOD_NAME "." lkconfig_SymbolViewName,
    sizeof (lkconfig_SymbolViewObject),
    0,                         /* tp_itemsize */
    (destructor) lkconfig_SymbolViewObject_dealloc,  /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_reserved */
    0,                         /* tp_repr */
    0,                         /* tp_as_number */
    0,                         /* tp_as_sequence */
    0,                         /* tp_as_mapping */
    0,                         /* tp_hash  */
    0,                         /* tp_call */
    0,                         /* tp_str */
    0,                         /* tp_getattro */
    0,                         /* tp_setattro */
    0,                         /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT
        /*| Py_TPFLAGS_BASETYPE*/,   /* tp_flags */
    PyDoc_STR ( "kconfig symbol view" ),  /* tp doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    lkconfig_SymbolViewObject_methods,  /* tp_methods */
    lkconfig_SymbolViewObject_members,  /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,                         /* tp_init */
    0,                         /* tp_alloc */
    0                          /* tp_new */
};


static PyObject* lkconfig_SymbolViewObject_new_from_struct (
    const struct symbol* const sym
) {
    lkconfig_SymbolViewObject* self;

    self = PyObject_NEW (
        lkconfig_SymbolViewObject, &lkconfig_SymbolViewType
    );
    if ( self == NULL ) { return NULL; }

    if ( sym->name == NULL ) {
        Py_INCREF ( Py_None );
        self->name = Py_None;
    } else {
        self->name = PyUnicode_FromString ( sym->name );
        if ( self->name == NULL ) {
            Py_DECREF ( self );
            return NULL;
        }
    }

    self->s_type = sym->type;
    self->kconfig_sym = sym;
    return (PyObject*) self;
}
