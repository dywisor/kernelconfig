static void lkconfig_ExprViewObject_dealloc (
    lkconfig_ExprViewObject* const self
) {
    Py_TYPE(self)->tp_free ( (PyObject*) self );
}



static void lkconfig_ExprViewObject_get_expr__expand_none (
    PyObject** const expr_out,  /* uninitialized */
    PyObject** const sym_out    /* uninitialized */
) {
    Py_INCREF ( Py_None ); *expr_out = Py_None;
    Py_INCREF ( Py_None ); *sym_out = Py_None;
}

static int lkconfig_ExprViewObject_get_expr__expand_sym (
    const struct symbol* const sym_in,
    PyObject** const expr_out,  /* uninitialized */
    PyObject** const sym_out    /* uninitialized */
) {
    if ( sym_in == NULL ) {
        Py_INCREF ( Py_None ); *sym_out = Py_None;
    } else {
        *sym_out = lkconfig_SymbolViewObject_new_from_struct ( sym_in );
        if ( *sym_out == NULL ) { return -1; }
    }
    Py_INCREF ( Py_None ); *expr_out = Py_None;

    return 0;
}

static int lkconfig_ExprViewObject_get_expr__expand_expr (
    const struct expr* const expr_in,
    PyObject** const expr_out,  /* uninitialized */
    PyObject** const sym_out    /* uninitialized */
) {
    if ( expr_in == NULL ) {
        /* empty expression */
        lkconfig_ExprViewObject_get_expr__expand_none ( expr_out, sym_out );
        return 0;
    }

    *expr_out = lkconfig_ExprViewObject_new_from_struct ( expr_in );
    if ( *expr_out == NULL ) { return -1; }
    Py_INCREF ( Py_None ); *sym_out = Py_None;

    return 0;
}


static PyObject* lkconfig_ExprViewObject_get_expr (
    lkconfig_ExprViewObject* const self, PyObject* const noargs
) {
    PyObject* left_expr;
    PyObject* right_expr;
    PyObject* left_sym;
    PyObject* right_sym;

    if ( self->kconfig_expr == NULL ) {
        /* 5-tuple (expr_type, None, None, None, None) */
        return Py_BuildValue (
            "(iOOOO)",
            self->e_type,  /* which is E_NONE */
            Py_None, Py_None, Py_None, Py_None
        );
    }

    switch ( self->e_type ) {   /* or kconfig_expr->type, equiv. */
        case E_SYMBOL:
            /* left is a symbol, right forced to None */
            if (
                lkconfig_ExprViewObject_get_expr__expand_sym (
                    (self->kconfig_expr->left).sym, &left_expr, &left_sym
                ) != 0
            ) {
                return NULL;
            }


            lkconfig_ExprViewObject_get_expr__expand_none (
                &right_expr, &right_sym
            );
            break;

        case E_NOT:
            /* left is expr, right forced to None */
            if (
                lkconfig_ExprViewObject_get_expr__expand_expr (
                    (self->kconfig_expr->left).expr, &left_expr, &left_sym
                ) != 0
            ) {
                return NULL;
            }

            lkconfig_ExprViewObject_get_expr__expand_none (
                &right_expr, &right_sym
            );
            break;

        case E_EQUAL:
        case E_UNEQUAL:
        case E_LTH:
        case E_LEQ:
        case E_GTH:
        case E_GEQ:
        case E_RANGE:
            /* left is a symbol, right is a symbol */
            if (
                lkconfig_ExprViewObject_get_expr__expand_sym (
                    (self->kconfig_expr->left).sym, &left_expr, &left_sym
                ) != 0
            ) {
                return NULL;
            }

            if (
                lkconfig_ExprViewObject_get_expr__expand_sym (
                    (self->kconfig_expr->right).sym, &right_expr, &right_sym
                ) != 0
            ) {
                Py_DECREF ( left_expr );
                Py_DECREF ( left_sym );
                return NULL;
            }
            break;

        case E_OR:
        case E_AND:
            /* left is expr, right is expr */
            if (
                lkconfig_ExprViewObject_get_expr__expand_expr (
                    (self->kconfig_expr->left).expr, &left_expr, &left_sym
                ) != 0
            ) {
                return NULL;
            }

            if (
                lkconfig_ExprViewObject_get_expr__expand_expr (
                    (self->kconfig_expr->right).expr, &right_expr, &right_sym
                ) != 0
            ) {
                Py_DECREF ( left_expr );
                Py_DECREF ( left_sym );
                return NULL;
            }
            break;

        case E_LIST:
            /* left is expr or NULL, right is symbol */
            if (
                lkconfig_ExprViewObject_get_expr__expand_expr (
                    (self->kconfig_expr->left).expr, &left_expr, &left_sym
                ) != 0
            ) {
                return NULL;
            }

            if (
                lkconfig_ExprViewObject_get_expr__expand_sym (
                    (self->kconfig_expr->right).sym, &right_expr, &right_sym
                ) != 0
            ) {
                Py_DECREF ( left_expr );
                Py_DECREF ( left_sym );
                return NULL;
            }
            break;

        case E_NONE:
            PyErr_SetString ( PyExc_ValueError, "E_NONE expression" );
            return NULL;

        default:
            /* undefined */
            PyErr_Format ( PyExc_ValueError, "unknown type '%d'", self->e_type );
            return NULL;
    }


    /* 5-tuple (expr_type, left_expr, left_sym, right_expr, right_sym) */
    return Py_BuildValue (
        "(iNNNN)",  /* refsteal */
        self->e_type, left_expr, left_sym, right_expr, right_sym
    );
}



static PyMethodDef lkconfig_ExprViewObject_methods[] = {
    {
        "get_expr",
        (PyCFunction) lkconfig_ExprViewObject_get_expr,
        METH_NOARGS,
        PyDoc_STR (
            "get_expr()\n"
            "\n"
            "Returns a 5-tuple (expr_type, left_expr, left_sym, right_expr, right_sym),\n"
            "out which at most 3 items are not None (expr_type, one left_, one right)."
        )
    },
    { NULL }
};


static PyMemberDef lkconfig_ExprViewObject_members[] = {
    {
        "e_type",
        T_INT, offsetof(lkconfig_ExprViewObject, e_type), READONLY,
        PyDoc_STR ( "expr type (one of self.E_*)" )
    },
    { NULL }
};

static PyTypeObject lkconfig_ExprViewType = {
    PyVarObject_HEAD_INIT(NULL, 0)

    LKCONFIG_PYMOD_NAME "." lkconfig_ExprViewName,
    sizeof (lkconfig_ExprViewObject),
    0,                         /* tp_itemsize */
    (destructor) lkconfig_ExprViewObject_dealloc,  /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_reserved */
    0,                         /* tp_repr */
    0,                         /* tp_as_number */
    0,                         /* tp_as_sequence */
    0,                         /* tp_as_mapping */
    PyObject_HashNotImplemented,  /* tp_hash  */
    0,                         /* tp_call */
    0,                         /* tp_str */
    0,                         /* tp_getattro */
    0,                         /* tp_setattro */
    0,                         /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT
        /*| Py_TPFLAGS_BASETYPE*/,   /* tp_flags */
    PyDoc_STR ( "kconfig expr view" ),  /* tp doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    lkconfig_ExprViewObject_methods,  /* tp_methods */
    lkconfig_ExprViewObject_members,  /* tp_members */
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


static PyObject* lkconfig_ExprViewObject_new_from_struct (
    const struct expr* kconfig_expr
) {
    lkconfig_ExprViewObject* self;

    self = PyObject_NEW ( lkconfig_ExprViewObject, &lkconfig_ExprViewType );
    if ( self == NULL ) { return NULL; }

    self->e_type = (kconfig_expr != NULL) ? kconfig_expr->type : E_NONE;
    self->kconfig_expr = kconfig_expr;

    return (PyObject*) self;
}


static int lkconfig_ExprViewObject_cls_init ( PyTypeObject* const pycls ) {
    PyObject* d;

    d = PyDict_New();
    if ( d == NULL ) { return -1; }

#define lkconfig_add_expr_int(_name)  \
    do { \
        if ( lkconfig_dict_add_str_x_int ( d, (#_name), (_name) ) != 0 ) { \
            Py_DECREF ( d ); \
            return -1; \
        } \
    } while (0)


    lkconfig_add_expr_int ( E_NONE );
    lkconfig_add_expr_int ( E_OR );
    lkconfig_add_expr_int ( E_AND );
    lkconfig_add_expr_int ( E_NOT );
    lkconfig_add_expr_int ( E_EQUAL );
    lkconfig_add_expr_int ( E_UNEQUAL );
    lkconfig_add_expr_int ( E_LTH );
    lkconfig_add_expr_int ( E_LEQ );
    lkconfig_add_expr_int ( E_GTH );
    lkconfig_add_expr_int ( E_GEQ );
    lkconfig_add_expr_int ( E_LIST );
    lkconfig_add_expr_int ( E_SYMBOL );
    lkconfig_add_expr_int ( E_RANGE );


#undef lkconfig_add_expr_int

    pycls->tp_dict = d; d = NULL;  /* steal ref */

    return PyType_Ready(pycls);
}
