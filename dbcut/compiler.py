# -*- coding: utf-8 -*-
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects import mysql


@compiles(mysql.LONGBLOB, 'sqlite')
def compile_sqlite_longblob(type_, compiler, **kw):
    return 'BLOB'


@compiles(mysql.DATETIME, 'sqlite')
def compile_sqlite_datetime(type_, compiler, **kw):
    column = kw['type_expression']
    if column.server_default:
        if "current_timestamp" in column.server_default.arg.text:
            column.server_default.arg.text = "CURRENT_TIMESTAMP"
    return "DATETIME"


@compiles(mysql.TINYINT, 'sqlite')
@compiles(mysql.SMALLINT, 'sqlite')
def compile_sqlite_tinyint(type_, compiler, **kw):
    return "SMALLINT"


@compiles(mysql.LONGTEXT, 'sqlite')
def compile_sqlite_longtext(type_, compiler, **kw):
    return "TEXT"


@compiles(mysql.VARCHAR, 'sqlite')
def compile_sqlite_varchar(type_, compiler, **kw):
    return "VARCHAR(%s)" % type_.length


@compiles(mysql.TINYINT, 'postgresql')
@compiles(mysql.SMALLINT, 'postgresql')
def compile_postgresql_tinyint(type_, compiler, **kw):
    return "SMALLINT"


@compiles(mysql.LONGTEXT, 'postgresql')
def compile_postgresql_longtext(type_, compiler, **kw):
    return "TEXT"


@compiles(mysql.VARCHAR, 'postgresql')
def compile_postgresql_varchar(type_, compiler, **kw):
    return "VARCHAR(%s)" % type_.length


@compiles(mysql.DATETIME, 'postgresql')
def compile_postgresql_datetime(type_, compiler, **kw):
    return "TIMESTAMP WITHOUT TIME ZONE"
