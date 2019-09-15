# -*- coding: utf-8 -*-
from itertools import chain

import ujson as json
from sqlalchemy import MetaData
from tqdm import tqdm

from ..query import parse_query
from ..utils import to_unicode, tree_pretty_print


def parse_queries(ctx):
    queries = []
    session = ctx.src_db.session
    for dict_query in ctx.config["queries"]:
        queries.append(parse_query(dict_query.copy(), session, ctx.config))
    return queries


def get_objects_generator(ctx, query, session):

    if ctx.no_cache:
        using_cache = False
        count = query.count()
        generator = query.objects()
    else:
        if not query.is_cached or ctx.force_refresh:
            using_cache = False
            count = query.count()

            def generator_func():
                objects = []
                for obj in query.objects():
                    objects.append(obj)
                    yield obj
                query.save_to_cache(objects=objects)

            generator = generator_func()

        else:
            using_cache = True
            generator = (obj for obj in query.load_from_cache())
            # TODO: get count from cache
            count = query.count()

    def objects_generator():
        progressbar = None

        obj = next(generator, None)
        if obj is not None:
            fetch_generator = chain([obj], generator)
        else:
            fetch_generator = generator

        yield

        if not using_cache:
            progressbar = tqdm(total=count, leave=False)

        for obj in fetch_generator:
            yield obj
            if progressbar is not None:
                progressbar.update(1)

        if progressbar is not None:
            progressbar.close()

    return objects_generator(), count, using_cache


def copy_query(ctx, query, session, query_index, number_of_queries):
    objects_generator, count, using_cache = get_objects_generator(ctx, query, session)

    ctx.log("")
    ctx.log("Query %d/%d : " % ((query_index + 1), number_of_queries), nl=False)
    ctx.log(json.dumps(query.query_dict, sort_keys=False))
    ctx.log("")
    ctx.log(tree_pretty_print(query.relations_tree))
    ctx.log(" ---> Cache key : %s" % query.cache_key)
    if using_cache:
        ctx.log(" ---> Using cache ({} elements)".format(count))
    else:
        ctx.log(" ---> Executing query")

    next(objects_generator)

    if count:
        ctx.log(" ---> Fetching objects")
        for obj in objects_generator:
            session.add(obj)
        rows_count = len(list(session))
        ctx.log(" ---> Inserting {} rows".format(rows_count))
        session.commit()
    else:
        ctx.log(" ---> Nothing to do")


def sync_data(ctx):

    if ctx.profiler:
        ctx.dest_db.start_profiler()
        ctx.src_db.start_profiler()

    with ctx.dest_db.no_fkc_session() as session:
        queries = parse_queries(ctx)
        number_of_queries = len(queries)
        for query_index, query in enumerate(queries):
            copy_query(ctx, query, session, query_index, number_of_queries)

    if ctx.profiler:
        ctx.dest_db.stop_profiler()
        ctx.src_db.stop_profiler()
        ctx.dest_db.profiler_stats()
        ctx.src_db.profiler_stats()


def sync_schema(ctx):
    if ctx.drop_db:
        ctx.confirm("Remove all tables from %s" % ctx.dest_db.engine.url, default=False)
        ctx.src_db.reflect()
        # Drop destination db
        dest_metadata = MetaData(ctx.dest_db.engine)
        dest_metadata.reflect(bind=ctx.dest_db.engine)
        dest_metadata.drop_all(checkfirst=True)

        # Create all
        ctx.dest_db.reflect(bind=ctx.src_db.engine)
        ctx.dest_db.create_all(checkfirst=True)
    else:
        ctx.src_db.reflect()
        ctx.dest_db.reflect(bind=ctx.src_db.engine)
        ctx.dest_db.create_all(checkfirst=True)


def sync_db(ctx):
    sync_schema(ctx)
    sync_data(ctx)


def inspect_db(ctx):
    infos = dict()
    for table_name, size in ctx.src_db.count_all(estimate=True):
        infos[table_name] = {"src_db_size": size, "dest_db_size": 0, "diff": size}
    for table_name, size in ctx.dest_db.count_all():
        if table_name not in infos:
            infos[table_name] = {"src_db_size": 0}
        infos[table_name]["dest_db_size"] = size
        diff = infos[table_name]["src_db_size"] - size
        infos[table_name]["diff"] = diff

    headers = ["Table", "Source estimated size", "Destination size", "Diff"]
    rows = [
        (
            k,
            to_unicode(infos[k]["src_db_size"]),
            to_unicode(infos[k]["dest_db_size"]),
            to_unicode(infos[k]["diff"]),
        )
        for k in infos.keys()
    ]
    if ctx.sort:
        rows = sorted(rows, key=lambda x: x[0])
    return rows, headers
