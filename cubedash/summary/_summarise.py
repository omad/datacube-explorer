from __future__ import absolute_import

from collections import Counter
from datetime import datetime

import pandas as pd
import structlog
from cachetools.func import lru_cache
from dateutil import tz
from geoalchemy2 import Geometry
from geoalchemy2 import shape as geo_shape
from sqlalchemy import Integer, and_, bindparam, func, select
from sqlalchemy.dialects.postgresql import TSTZRANGE

from cubedash.summary import TimePeriodOverview
from cubedash.summary._schema import DATASET_SPATIAL, FOOTPRINT_SRID, SPATIAL_REF_SYS
from datacube.drivers.postgres._schema import DATASET_TYPE
from datacube.model import Range

_LOG = structlog.get_logger()


class Summariser:
    def __init__(self, engine, log=_LOG, grouping_time_zone="Australia/Darwin") -> None:
        self._engine = engine
        self.log = log
        # Group datasets using this timezone when counting them.
        # Aus data comes from Alice Springs
        self.grouping_time_zone = grouping_time_zone
        # cache
        self._grouping_time_zone_tz = tz.gettz(self.grouping_time_zone)
        # EPSG code for all polygons to be converted to (for footprints).
        self.output_crs_epsg_code = FOOTPRINT_SRID

    def calculate_summary(self, product_name: str, time: Range) -> TimePeriodOverview:
        """
        Create a summary of the given product/time range.
        """
        log = self.log.bind(product_name=product_name, time=time)
        log.debug("summary.query")

        begin_time, end_time, where_clause = self._where(product_name, time)
        select_by_srid = (
            select(
                (
                    func.ST_SRID(DATASET_SPATIAL.c.footprint).label("srid"),
                    func.count().label("dataset_count"),
                    func.ST_Transform(
                        func.ST_Union(DATASET_SPATIAL.c.footprint),
                        self._target_srid(),
                        type_=Geometry(),
                    ).label("footprint_geometry"),
                    func.sum(DATASET_SPATIAL.c.size_bytes).label("size_bytes"),
                    func.max(DATASET_SPATIAL.c.creation_time).label(
                        "newest_dataset_creation_time"
                    ),
                )
            )
            .where(where_clause)
            .group_by("srid")
            .alias("srid_summaries")
        )

        # Union all srid groups into one summary.
        result = self._engine.execute(
            select(
                (
                    func.sum(select_by_srid.c.dataset_count).label("dataset_count"),
                    func.array_agg(select_by_srid.c.srid).label("srids"),
                    func.sum(select_by_srid.c.size_bytes).label("size_bytes"),
                    func.ST_Union(
                        select_by_srid.c.footprint_geometry,
                        type_=Geometry(srid=self._target_srid()),
                    ).label("footprint_geometry"),
                    func.max(select_by_srid.c.newest_dataset_creation_time).label(
                        "newest_dataset_creation_time"
                    ),
                    func.now().label("summary_gen_time"),
                )
            )
        )

        rows = result.fetchall()
        log.debug("summary.query.done", srid_rows=len(rows))

        assert len(rows) == 1
        row = dict(rows[0])
        row["dataset_count"] = int(row["dataset_count"]) if row["dataset_count"] else 0
        if row["footprint_geometry"] is not None:
            row["footprint_crs"] = self._get_srid_name(row["footprint_geometry"].srid)
            row["footprint_geometry"] = geo_shape.to_shape(row["footprint_geometry"])
        else:
            row["footprint_crs"] = None
        row["crses"] = None
        if row["srids"] is not None:
            row["crses"] = {self._get_srid_name(s) for s in row["srids"]}
        del row["srids"]

        # Convert from Python Decimal
        if row["size_bytes"] is not None:
            row["size_bytes"] = int(row["size_bytes"])

        has_data = row["dataset_count"] > 0

        log.debug("counter.calc")

        # Initialise all requested days as zero
        day_counts = Counter(
            {d.date(): 0 for d in pd.date_range(begin_time, end_time, closed="left")}
        )
        region_counts = Counter()
        if has_data:
            day_counts.update(
                Counter(
                    {
                        day.date(): count
                        for day, count in self._engine.execute(
                            select(
                                [
                                    func.date_trunc(
                                        "day",
                                        DATASET_SPATIAL.c.center_time.op(
                                            "AT TIME ZONE"
                                        )(self.grouping_time_zone),
                                    ).label("day"),
                                    func.count(),
                                ]
                            )
                            .where(where_clause)
                            .group_by("day")
                        )
                    }
                )
            )
            region_counts = Counter(
                {
                    item: count
                    for item, count in self._engine.execute(
                        select(
                            [
                                DATASET_SPATIAL.c.region_code.label("region_code"),
                                func.count(),
                            ]
                        )
                        .where(where_clause)
                        .group_by("region_code")
                    )
                }
            )

        summary = TimePeriodOverview(
            **row,
            timeline_period="day",
            time_range=Range(begin_time, end_time),
            timeline_dataset_counts=day_counts,
            region_dataset_counts=region_counts,
            # TODO: filter invalid from the counts?
            footprint_count=row["dataset_count"] or 0,
        )

        log.debug(
            "summary.calc.done",
            dataset_count=summary.dataset_count,
            footprints_missing=summary.dataset_count - summary.footprint_count,
        )
        return summary

    def _with_default_tz(self, d: datetime) -> datetime:
        if d.tzinfo is None:
            return d.replace(tzinfo=self._grouping_time_zone_tz)
        return d

    def _where(self, product_name, time):
        begin_time = self._with_default_tz(time.begin)
        end_time = self._with_default_tz(time.end)
        where_clause = and_(
            func.tstzrange(begin_time, end_time, "[]", type_=TSTZRANGE).contains(
                DATASET_SPATIAL.c.center_time
            ),
            DATASET_SPATIAL.c.dataset_type_ref
            == select([DATASET_TYPE.c.id]).where(DATASET_TYPE.c.name == product_name),
        )
        return begin_time, end_time, where_clause

    @lru_cache(1)
    def _target_srid(self):
        """
        Get the srid key for our target CRS (that all geometry is returned as)

        The pre-populated srid primary keys in postgis all default to the epsg code,
        but we'll do the lookup anyway to be good citizens.
        """
        return self._engine.execute(
            select([SPATIAL_REF_SYS.c.srid])
            .where(SPATIAL_REF_SYS.c.auth_name == "EPSG")
            .where(SPATIAL_REF_SYS.c.auth_srid == self.output_crs_epsg_code)
        ).scalar()

    @lru_cache()
    def _get_srid_name(self, srid):
        """
        Convert an internal postgres srid key to a string auth code: eg: 'EPSG:1234'
        """
        return self._engine.execute(
            select(
                [
                    func.concat(
                        SPATIAL_REF_SYS.c.auth_name,
                        ":",
                        SPATIAL_REF_SYS.c.auth_srid.cast(Integer),
                    )
                ]
            ).where(SPATIAL_REF_SYS.c.srid == bindparam("srid", srid, type_=Integer))
        ).scalar()
