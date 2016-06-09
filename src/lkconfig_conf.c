/*
 * This is -more or less- a copy of scripts/kconfig/conf.c,
 * reduced to oldconfig functionality,
 * non-interactive, and extended by a decisions PyDict.
 *
 * */

struct lkconfig_conf_vars {
    int           conf_cnt;
    struct menu*  rootEntry;
    PyObject*     conf_decisions;
    PyObject*     logger;
};

#define lkconfig_conf_get_tristate_str(tval) \
    (((tval) == yes) ? "y" : (((tval) == mod) ? "m" : "n"))


/* this is used by lkconfig_conf_main()'s config message callback */
static PyObject* lkconfig_conf_main_logger;


static int lkconfig_conf_log_set_symbol (
    struct lkconfig_conf_vars* const cvars,
    struct symbol* const sym,
    const char* const newval_str,
    const char* const oldval_str
) {
    if ( sym->name == NULL ) { return 0; }

    if ( ! sym_has_value(sym) ) {
        return lkconfig_log (
            cvars->logger, lkconfig_debug,
            "Setting symbol %s to \"%s\"",
            sym->name, newval_str
        );
    } else if ( strcmp ( newval_str, oldval_str ) != 0 ) {
        return lkconfig_log (
            cvars->logger, lkconfig_debug,
            "Setting symbol %s to \"%s\" (from \"%s\")",
            sym->name, newval_str, oldval_str
        );
    } else {
        return 0;
    }
}


static int lkconfig_conf__conf (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
);

static int lkconfig_conf__check_conf (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
);


static void lkconfig_conf_main_message_callback (
    const char* fmt, va_list ap
) {
    PyObject* exc_type;
    PyObject* exc_value;
    PyObject* exc_traceback;

    if ( lkconfig_conf_main_logger == NULL ) { return; }

    PyErr_Fetch ( &exc_type, &exc_value, &exc_traceback );
    (void) lkconfig_logv ( lkconfig_conf_main_logger, lkconfig_debug, fmt, ap );
    PyErr_Restore ( exc_type, exc_value, exc_traceback );
}

static void lkconfig_conf_main_clear_logger_and_callback (void) {
    conf_set_message_callback ( NULL );
    lkconfig_conf_main_logger = NULL;
}


static int lkconfig_conf_main (
    const char* const config_file_in,
    const char* const config_file_out,
    PyDictObject* const conf_decisions,
    PyObject* const logger
) {
    struct lkconfig_conf_vars cvars;

    cvars.conf_decisions = (PyObject*) conf_decisions;
    cvars.logger = logger;

    lkconfig_conf_main_logger = logger;
    conf_set_message_callback ( lkconfig_conf_main_message_callback );

    conf_read ( config_file_in );

    do {
        cvars.conf_cnt = 0;
        if ( lkconfig_conf__check_conf ( &cvars, &rootmenu ) < 0 ) {
            lkconfig_conf_main_clear_logger_and_callback();
            return -1;
        }
    } while ( cvars.conf_cnt );


    conf_write ( config_file_out );

    lkconfig_conf_main_clear_logger_and_callback();
    return 0;
}


static int lkconfig_conf__conf_askvalue_decisions (
    struct lkconfig_conf_vars* const cvars,
    struct symbol* const sym,
    PyObject** const entry_out
) {
    *entry_out = NULL;

    if ( ! sym_is_changable(sym) ) {
        return 0;
    }

    if ( sym->name ) {
        *entry_out = PyDict_GetItemString ( cvars->conf_decisions, sym->name );
        /* borrowed ref */
    }

    return 1;
}

static int lkconfig_conf__conf_get_tristate_decision_value (
    struct lkconfig_conf_vars* const cvars,
    struct symbol* const sym,
    PyObject* const decision_entry,
    tristate* const trival_out
) {
    long decval;

    decval = PyLong_AsLong ( decision_entry );
    switch ( decval ) {
        case 0:
            *trival_out = no;
            break;

        case 1:
            *trival_out = mod;
            break;

        case 2:
            *trival_out = yes;
            break;

        default:
            PyErr_Format (
                PyExc_ValueError,
                "bad decision value for tristate symbol %s: %d",
                sym->name, decval
            );
            return -1;
    }

    return 0;
}



static int lkconfig_conf__conf_askvalue_tristate (
    struct lkconfig_conf_vars* const cvars,
    struct symbol* const sym,
    tristate oldval,
    tristate* const newval_out
) {
    PyObject* entry;
    int ret;

    /* unless further information exists, use the default value */
    *newval_out = oldval;

    /* entry: borrowed ref */
    ret = lkconfig_conf__conf_askvalue_decisions ( cvars, sym, &entry );
    if ( ret <= 0 ) { return ret; }

    if ( entry == NULL ) {
        ;

    } else if ( PyLong_Check ( entry ) ) {
        if (
            lkconfig_conf__conf_get_tristate_decision_value (
                cvars, sym, entry, newval_out
            ) != 0
        ) {
            return -1;
        }

         if ( ! sym_tristate_within_range ( sym, *newval_out ) ) {
            PyErr_Format (
                PyExc_ValueError,
                "impossible decision value for tristate symbol %s: %d",
                sym->name, *newval_out
            );
            return -1;
        }

    } else {
        PyErr_Format (
            PyExc_ValueError,
            "bad decision value for tristate symbol %s", sym->name
        );
        return -1;
    }


    return 1;
}


static int lkconfig_conf__conf_sym (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
) {
    struct symbol *sym;
    tristate oldval;
    tristate newval;
    int ret;

    sym = menu->sym;

    oldval = sym_get_tristate_value(sym);

    ret = lkconfig_conf__conf_askvalue_tristate (
        cvars, sym, oldval, &newval
    );
    if ( ret <= 0 ) { return ret; }

    if (
        (oldval != newval) || (!sym_has_value(sym) && oldval != no)
    ) {
        if (
            lkconfig_conf_log_set_symbol (
                cvars, sym,
                lkconfig_conf_get_tristate_str(newval),
                lkconfig_conf_get_tristate_str(oldval)
            ) != 0
        ) {
            return -1;
        }
    }

    if ( sym_set_tristate_value ( sym, newval ) ) {
        return 0;
    } else {
        PyErr_Format (
            PyExc_ValueError,
            "failed to set tristate symbol %s",
            (sym->name == NULL ? "???" : sym->name)
        );
        return -1;
    }
}


static int lkconfig_conf__conf_string (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
) {
    PyObject* entry;
    PyObject* decision_value;
    struct symbol* sym;
    const char* def;
    const char* newval;
    tristate trival;
    int ret;

    sym = menu->sym;
    def = sym_get_string_value ( sym );
    newval = def;

    /* entry: borrowed ref */
    ret = lkconfig_conf__conf_askvalue_decisions ( cvars, sym, &entry );
    if ( ret <= 0 ) { return ret; }

    if ( ! sym_is_changable(sym) ) {
        return 0;
    }

    decision_value = NULL;

    if ( entry == NULL ) {
        ;

    } else if ( PyUnicode_Check ( entry ) ) {
        decision_value = PyUnicode_AsASCIIString ( entry );  /* new ref */
        if ( decision_value == NULL ) { return -1; }

        newval = PyBytes_AsString ( decision_value );
        if ( newval == NULL ) {
            Py_DECREF ( decision_value );
            return -1;
        }

    } else if ( PyLong_Check ( entry ) ) {
        if (
            lkconfig_conf__conf_get_tristate_decision_value (
                cvars, sym, entry, &trival
            ) != 0
        ) {
            return -1;
        }

        switch ( trival ) {
            case no:
                if ( def && *def ) {
                    /* non-NULL entry implies non-NULL sym->name */
                    if (
                        lkconfig_log (
                            cvars->logger, lkconfig_warning,
                            "Setting disabled string-like symbol %s",
                            sym->name
                        ) != 0
                    ) {
                        return -1;
                    }
                }
                break;

            default:
                PyErr_Format (
                    PyExc_ValueError,
                    "bad tristate decision value from string symbol %s: %d",
                    sym->name, trival
                );
                return -1;
        }

    } else {
        PyErr_Format (
            PyExc_ValueError,
            "bad decision value for string symbol %s", sym->name
        );
        return -1;
    }

    if ( lkconfig_conf_log_set_symbol ( cvars, sym, newval, def ) != 0 ) {
        newval = NULL; Py_XDECREF ( decision_value );
        return -1;
    }

    ret = sym_set_string_value ( sym, newval ) ? 0 : -1;
    if ( ret < 0 ) {
        PyErr_Format (
            PyExc_ValueError,
            "failed to string symbol %s to '%s'",
            (sym->name == NULL ? "???" : sym->name), newval
        );
    }

    newval = NULL; Py_XDECREF ( decision_value );
    return ret;
}


static int lkconfig_conf__conf_choice (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
) {
    struct symbol* sym;
    struct symbol* def_sym;
    struct menu *child;
    bool is_new;
    int cnt;
    int def;

    sym = menu->sym;
    is_new = !sym_has_value(sym);

    if ( sym_is_changable(sym) ) {
        if ( lkconfig_conf__conf_sym ( cvars, menu ) < 0 ) { return -1; }
        sym_calc_value ( sym );
        switch ( sym_get_tristate_value(sym) ) {
            case no:
                return 1;

            case mod:
                return 0;

            case yes:
                break;
        }
    } else {
        switch ( sym_get_tristate_value(sym) ) {
            case no:
                return 1;

            case mod:
                return 0;

            case yes:
                break;
        }
    }


    def_sym = sym_get_choice_value(sym);
    cnt = 0;
    def = 0;

    for ( child = menu->list; child; child = child->next ) {
        if ( !menu_is_visible(child) ) {
            continue;
        }

        if ( !child->sym ) {
            continue;
        }

        cnt++;
        if (child->sym == def_sym) {
            def = cnt;
        }
    }

    if ( cnt == 1 ) {
        goto lkconfig_conf__conf_choice_childs;
    }

    if ( !is_new ) { cnt = def; }

    cnt = def;


lkconfig_conf__conf_choice_childs:
    for ( child = menu->list; child; child = child->next ) {
        if ( !child->sym || !menu_is_visible(child) ) {
            continue;
        }

        if ( !--cnt ) {
            break;
        }
    }

    if ( !child ) {
        PyErr_SetString ( PyExc_ValueError, "choice?" );
        return -1;
    }

    sym_set_choice_value ( sym, child->sym );
    for ( child = child->list; child; child = child->next ) {
        if ( lkconfig_conf__conf ( cvars, child ) < 0 ) { return -1; }
    }
    return 1;
}


static int lkconfig_conf__conf (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
) {
    struct symbol* sym;
    struct menu*   child;

    if ( ! menu_is_visible(menu) ) {
        return 0;
    }

    sym  = menu->sym;

    if ( !sym ) {
        goto lkconfig_conf__conf_childs;
    }

    if ( sym_is_choice(sym) ) {
        if ( lkconfig_conf__conf_choice ( cvars, menu ) < 0 ) { return -1; }
        if ( sym->curr.tri != mod ) { return 0; }
        goto lkconfig_conf__conf_childs;
    }

    switch ( sym->type ) {
        case S_INT:
        case S_HEX:
        case S_STRING:
            if ( lkconfig_conf__conf_string ( cvars, menu ) < 0 ) { return -1; }
            break;

        default:
            if ( lkconfig_conf__conf_sym ( cvars, menu ) < 0 ) { return -1; }
            break;
    }


lkconfig_conf__conf_childs:
    for ( child = menu->list; child; child = child->next ) {
        if ( lkconfig_conf__conf ( cvars, child ) < 0 ) { return -1; }
    }

    return 0;
}


static int lkconfig_conf__check_conf (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
) {
    struct symbol* sym;
    struct menu*   child;

    if ( ! menu_is_visible(menu) ) {
        return 0;
    }

    sym = menu->sym;
    if ( sym && !sym_has_value(sym) ) {
        if (
            sym_is_changable(sym)
            || (
                sym_is_choice(sym)
                && sym_get_tristate_value(sym) == yes
            )
        ) {
            (cvars->conf_cnt)++;
            cvars->rootEntry = menu_get_parent_menu(menu);
            if ( lkconfig_conf__conf ( cvars, cvars->rootEntry ) < 0 ) {
                return -1;
            }

        }
    }

    for ( child = menu->list; child; child = child->next ) {
        if ( lkconfig_conf__check_conf ( cvars, child ) < 0 ) {
            return -1;
        }
    }

    return 0;
}


#undef lkconfig_conf_get_tristate_str
