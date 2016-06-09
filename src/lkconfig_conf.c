/*
 * This is -more or less- a copy of scripts/kconfig/conf.c,
 * reduced to oldconfig functionality,
 * non-interactive, and extended by a decisions PyDict.
 *
 * */

struct lkconfig_conf_vars {
    int           conf_cnt;
    struct menu*  rootEntry;
    const char*   conf_reply;
    PyObject*     conf_decisions;
};

static void lkconfig_conf__conf (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
);

static void lkconfig_conf__check_conf (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
);

static void lkconfig_conf_main (
    const char* const config_file_in,
    const char* const config_file_out,
    PyDictObject* const conf_decisions
) {
    struct lkconfig_conf_vars cvars;

    cvars.conf_decisions = (PyObject*) conf_decisions;

    conf_read ( config_file_in );

    do {
        cvars.conf_cnt = 0;
        lkconfig_conf__check_conf ( &cvars, &rootmenu );
    } while ( cvars.conf_cnt );

    conf_write ( config_file_out );
}

static int lkconfig_conf__conf_askvalue (
    struct lkconfig_conf_vars* const cvars,
    struct symbol* const sym,
    const char* const def
) {
    PyObject* entry;
    const char* decision_value;

    cvars->conf_reply = NULL;

    if ( ! sym_is_changable(sym) ) {
        return 0;
    }

    if ( sym->name ) {
        entry = PyDict_GetItemString ( cvars->conf_decisions, sym->name );
        /* borrowed ref */
        if ( entry != NULL ) {
            decision_value = PyUnicode_AsUTF8 ( entry );
            printf(
                "There is a default for symbol %s: %s (def: %s)\n",
                sym->name, decision_value, def
            );
        } else {
            printf(
                "No default for symbol %s, using %s\n",
                sym->name, def
            );
        }
    }

    return 1;
}


static int lkconfig_conf__conf_sym (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
) {
    struct symbol *sym = menu->sym;
    tristate oldval;
    tristate newval;
    int ret;

    oldval = sym_get_tristate_value(sym);

    ret = lkconfig_conf__conf_askvalue (
        cvars, sym, sym_get_string_value(sym)
    );
    if ( ret <= 0 ) { return ret; }

    if ( cvars->conf_reply == NULL ) {
        newval = oldval;
    } else {
        switch ( cvars->conf_reply[0] ) {
            case 'n':
                newval = no;
                break;

            case 'm':
                newval = mod;
                break;

            case 'y':
                newval = yes;
                break;

            default:
                return -1;
        }
    }

    if ( sym_set_tristate_value ( sym, newval ) ) {
        return 0;
    } else {
        return -1;
    }
}


static int lkconfig_conf__conf_string (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
) {
    struct symbol* sym;
    const char* def;
    int ret;

    sym = menu->sym;
    def = sym_get_string_value ( sym );
    ret = lkconfig_conf__conf_askvalue ( cvars, sym, def );
    if ( ret <= 0 ) { return ret; }

    if ( cvars->conf_reply != NULL ) {
        def = cvars->conf_reply;
    }

    if ( sym_set_string_value ( sym, def ) ) {
        return 0;
    } else {
        return -1;
    }
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
    cvars->conf_reply = NULL;

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

    /* TODO: get cvars->conf_reply */

    if ( cvars->conf_reply == NULL ) {
        cnt = def;
    }


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
        return -1;
    }

    sym_set_choice_value ( sym, child->sym );
    for ( child = child->list; child; child = child->next ) {
        lkconfig_conf__conf ( cvars, child );
    }
    return 1;
}


static void lkconfig_conf__conf (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
) {
    struct symbol* sym;
    struct menu*   child;

    if ( ! menu_is_visible(menu) ) {
        return;
    }

    sym  = menu->sym;

    if ( !sym ) {
        goto lkconfig_conf__conf_childs;
    }

    if ( sym_is_choice(sym) ) {
        lkconfig_conf__conf_choice ( cvars, menu );
        if ( sym->curr.tri != mod ) { return; }
        goto lkconfig_conf__conf_childs;
    }

    switch ( sym->type ) {
        case S_INT:
        case S_HEX:
        case S_STRING:
            lkconfig_conf__conf_string ( cvars, menu );
            break;

        default:
            lkconfig_conf__conf_sym ( cvars, menu );
            break;
    }


lkconfig_conf__conf_childs:
    for ( child = menu->list; child; child = child->next ) {
        lkconfig_conf__conf ( cvars, child );
    }
}


static void lkconfig_conf__check_conf (
    struct lkconfig_conf_vars* const cvars, struct menu* const menu
) {
    struct symbol* sym;
    struct menu*   child;

    if ( ! menu_is_visible(menu) ) {
        return;
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
            lkconfig_conf__conf ( cvars, cvars->rootEntry );
        }
    }

    for ( child = menu->list; child; child = child->next ) {
        lkconfig_conf__check_conf ( cvars, child );
    }
}
